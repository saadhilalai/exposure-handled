"""The cinematographer: decides exposure the way a DP would, one small explained step at a time.

It never touches the camera. update() returns at most ONE proposed change (with a
one-line reason) plus advice for things only a person can do (ND, light, WB lock).
Whatever runs the agent hands proposals to SafetyGate.change_setting(), which checks
the director's ranges again, and the bridge checks a third time.

Rules, in order:
  0. Recording -> no changes (unless the director allows it).
  1. Shutter: hold 180 degrees (1/(2 x frame rate)) for video looks.
  2. Aperture: comes from the look.
  3. Exposure: protect important highlights first, then faces, then the scene key.
     ISO fills the gap (staying on base ISOs 800/4000 when possible), then aperture
     inside the look's range, then ND advice (the agent can't turn the ND).
  4. White balance: only between takes, only when the color estimate is trustworthy.
Smoothness: 1/3-stop dead band, wait before reacting (walk-bys), wait for each change
to settle, no back-and-forth, small steps.
"""
import json
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from agent.looks import LOOKS
from agent.safety import RANGES_FILE

BASE_ISOS = (800, 4000)       # FX2 S-Log3, read from the camera's own menu text (Step 3)
SETTLE_S = 0.6                # a change shows in the picture ~0.3 s after it's sent (Step 3)
REVERSAL_WINDOW_S = 5.0
DEAD_BAND = 0.3               # stops; about a third of a stop
ND_LAST_RESORT_AFTER_S = 5.0  # cinematic: if ND advice is ignored and highlights still clip
CEILING_S = 60.0              # after darkening for clipping, don't go back up to that exposure for this long


def cam_ev(cam):
    """The camera's exposure in stops (bigger = brighter picture)."""
    return math.log2(cam.iso) - 2 * math.log2(cam.fnumber) + math.log2(cam.shutter_s)


def frac_stops(x):
    """1.666 -> '1⅔', 0.333 -> '⅓', 2.0 -> '2'."""
    thirds = int(round(abs(x) * 3))
    whole, rest = divmod(thirds, 3)
    s = ("%d" % whole if whole else "") + {0: "", 1: "⅓", 2: "⅔"}[rest]
    return s or "0"


def fmt_shutter_s(s):
    return "1/%d" % round(1 / s) if s < 0.4 else '%g"' % s


@dataclass
class Ranges:
    """Director-approved limits (config/safe_ranges.json)."""
    iso: tuple = (800, 12800)
    fnumber: tuple = (2.8, 11.0)
    shutter_s: tuple = (1 / 100, 1 / 48)
    kelvin: tuple = (2800, 7500)

    @classmethod
    def from_file(cls, path=RANGES_FILE):
        s = json.loads(open(path).read())["settings"]
        return cls(iso=(s["IsoSensitivity"]["min_iso"], s["IsoSensitivity"]["max_iso"]),
                   fnumber=(s["FNumber"]["min_f"], s["FNumber"]["max_f"]),
                   shutter_s=(s["ShutterSpeed"]["min_seconds"], s["ShutterSpeed"]["max_seconds"]),
                   kelvin=(s["Colortemp"]["min_k"], s["Colortemp"]["max_k"]))


@dataclass
class CamState:
    iso: int
    fnumber: float
    shutter_s: float
    fps: float
    log_mode: str = "FlexibleISO"          # FlexibleISO / CineEI / CineEIQuick / Off
    wb_mode: str = "AWB"
    wb_kelvin: Optional[int] = None
    recording: bool = False
    iso_options: list = field(default_factory=list)
    f_options: list = field(default_factory=list)
    shutter_options: list = field(default_factory=list)    # seconds


FRAME_RATES = {"23_98p": 23.976, "24p": 24.0, "24_00p": 24.0, "25p": 25.0, "29_97p": 29.97, "30p": 30.0,
               "50p": 50.0, "59_94p": 59.94, "60p": 60.0, "100p": 100.0, "119_88p": 119.88, "120p": 120.0}


def cam_state_from_settings(props, enums):
    """Real camera settings (bridge/probe format: {name: property}) -> CamState."""
    from agent.sony_values import describe_value

    def cur(name):
        return props[name]["current"] if name in props else None

    def text(name):
        return describe_value(name, cur(name), enums) if name in props else None

    def options(name):
        p = props.get(name, {})
        return p.get("set_values") or p.get("values") or []

    shutter = cur("ShutterSpeed")
    wb = text("WhiteBalance") or "AWB"
    return CamState(
        iso=cur("IsoSensitivity") & 0xFFFFFF, fnumber=cur("FNumber") / 100,
        shutter_s=(shutter >> 16) / (shutter & 0xFFFF),
        fps=FRAME_RATES.get(text("Movie_Recording_FrameRateSetting"), 23.976),
        log_mode=text("MovieShootingMode") or "Off", wb_mode=wb,
        wb_kelvin=cur("Colortemp") if wb == "ColorTemp" else None,
        recording=cur("RecordingState") not in (None, 0),
        iso_options=[v for v in options("IsoSensitivity") if not v >> 24],
        f_options=[v / 100 for v in options("FNumber") if v < 0xFFF0],
        shutter_options=[(v >> 16) / (v & 0xFFFF) for v in options("ShutterSpeed") if v & 0xFFFF and v != 0xFFFFFFFF])


@dataclass
class Observation:
    t: float
    key: float
    face: Optional[float] = None
    face_clipping: bool = False
    clipped_important: float = 0.0
    clipped_practical: float = 0.0
    headroom: float = 5.0
    light_k: Optional[int] = None
    color_confidence: str = "low"


def observation_from_report(report, t):
    face = report.faces[0] if report.faces else None
    return Observation(t=t, key=report.key_stops, face=face["stops"] if face else None,
                       face_clipping=bool(face and face.get("clipping")),
                       clipped_important=report.clipped_important_pct,
                       clipped_practical=report.clipped_practical_pct, headroom=report.headroom_stops,
                       light_k=report.color.get("light_estimate_k"),
                       color_confidence=report.color.get("confidence", "low"))


@dataclass
class Proposal:
    setting: str          # Sony name, e.g. IsoSensitivity
    raw: int              # value as Sony encodes it
    from_text: str
    to_text: str
    reason: str           # the one plain-English line
    stops: float = 0.0    # exposure effect (+ brighter)


@dataclass
class Output:
    proposal: Optional[Proposal]
    advice: list
    status: str


def would(p):
    """A proposal for a setting the director hasn't approved, as advice."""
    return "Would change, not approved yet: " + p.reason


def iso_raw(iso):
    return int(iso)


def f_raw(f):
    return int(round(f * 100))


def shutter_raw(s):
    return (1 << 16) | int(round(1 / s))


def median(values):
    v = sorted(values)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


class Brain:
    def __init__(self, look="cinematic", ranges=None, allow_while_recording=False, out_of_range="warn",
                 allowed=None):
        """out_of_range: what to do when ISO or aperture starts OUTSIDE the director's ranges.
        "warn" (director's decision, 2026-10-17): pause exposure changes and say so.
        "bring_in": propose the nearest approved value, even if that's a big jump.
        allowed: Sony setting names the brain may actually change (None = all). Anything else
        becomes advice ("Would change, not approved yet: ...") and the brain moves on."""
        self.look = LOOKS[look] if isinstance(look, str) else look
        self.ranges = ranges or Ranges.from_file()
        self.allow_while_recording = allow_while_recording
        self.out_of_range = out_of_range
        self.allowed = None if allowed is None else set(allowed)
        self.history = deque()
        self.pending = None                  # (kind, sign, since)
        self.last_change_t = -1e9
        self.last_change_sign = 0
        self.nd_advice_since = None
        self.highlight_guard_until = -1e9
        self.ceiling = None                  # (camera EV that clipped, scene level then, time)
        self.cap = None                      # brightening allowed by the ceiling this frame (stops)

    # ------------------------------------------------------------------ main
    def update(self, obs, cam):
        self.history.append(obs)
        while self.history and obs.t - self.history[0].t > 3.0:
            self.history.popleft()
        if cam.recording and not self.allow_while_recording:
            self.pending = None
            return Output(None, [], "Locked: recording. No changes until you cut.")
        settling = obs.t - self.last_change_t < max(SETTLE_S, self.look.min_gap_s)

        self._pending_advice = None
        not_approved = []
        p = self._shutter_rule(cam, obs)
        if p and not self.may(p.setting):
            not_approved.append(would(p))
            p = None
        if p:
            if settling:
                return Output(None, [], "Waiting for the last change to settle")
            return self._commit(p, obs.t, -1 if p.stops < 0 else 0)
        shutter_advice = [self._pending_advice] if self._pending_advice else []
        outside = self._outside_ranges(cam)
        if outside:
            if self.out_of_range != "bring_in" or not self.may(outside[0][2].setting):
                return Output(None, not_approved + shutter_advice + [o[0] for o in outside],
                              "Paused: %s outside your approved range" % " and ".join(o[1] for o in outside))
            if settling:
                return Output(None, [], "Waiting for the last change to settle")
            return self._commit(outside[0][2], obs.t, 0)
        p = self._aperture_rule(cam, obs)
        if p and not self.may(p.setting):
            not_approved.append(would(p))
            p = None
        if p:
            if settling:
                return Output(None, [], "Waiting for the last change to settle")
            return self._commit(p, obs.t, 0)
        out = self._exposure(cam, obs, settling)
        out.advice = not_approved + shutter_advice + out.advice
        return out

    def may(self, setting):
        """May the brain actually change this setting (director's approval)?"""
        return self.allowed is None or setting in self.allowed

    def _outside_ranges(self, cam):
        """[(advice text, short name, proposal to bring it in)] for ISO / aperture outside the director's ranges."""
        out = []
        lo, hi = self.ranges.iso
        if not lo <= cam.iso <= hi:
            new = min(max(cam.iso, lo), hi)
            out.append(("ISO %d is outside your approved %d-%d: I won't change exposure until it's inside "
                        "(set it by hand, or allow me to bring it in)" % (cam.iso, lo, hi), "ISO",
                        Proposal("IsoSensitivity", iso_raw(new), "ISO %d" % cam.iso, "ISO %d" % new,
                                 "ISO %d is outside your approved %d-%d: moving to %d" % (cam.iso, lo, hi, new),
                                 math.log2(new / cam.iso))))
        lo, hi = self.ranges.fnumber
        if not lo - 0.05 <= cam.fnumber <= hi + 0.05:
            new = min(max(cam.fnumber, lo), hi)
            out.append(("f/%g is outside your approved f/%g-f/%g: I won't change exposure until it's inside"
                        % (cam.fnumber, lo, hi), "aperture",
                        Proposal("FNumber", f_raw(new), "f/%g" % cam.fnumber, "f/%g" % new,
                                 "f/%g is outside your approved f/%g-f/%g: moving to f/%g" % (cam.fnumber, lo, hi, new),
                                 2 * math.log2(cam.fnumber / new))))
        return out

    def _commit(self, p, t, sign):
        self.last_change_t = t
        self.last_change_sign = sign
        self.pending = None
        return Output(p, [], p.reason)

    # ------------------------------------------------------------ 1. shutter
    def _shutter_target(self, cam):
        want = 1 / (2 * cam.fps)
        lo, hi = self.ranges.shutter_s
        options = [s for s in cam.shutter_options if lo - 1e-6 <= s <= hi + 1e-6] or [min(max(want, lo), hi)]
        return min(options, key=lambda s: abs(math.log2(s / want)))

    def _shutter_rule(self, cam, obs):
        if not self.look.shutter_180:
            return None
        target = self._shutter_target(cam)
        if abs(math.log2(cam.shutter_s / target)) < 0.05:
            return None
        stops = math.log2(target / cam.shutter_s)
        if stops > 0 and obs.headroom - stops < 1 / 3 and self.may("ShutterSpeed"):
            # The slower shutter would push highlights into clipping: make room with ISO first.
            lo, hi = self.ranges.iso
            room_iso = [i for i in cam.iso_options if lo <= i <= hi and i <= cam.iso / 2 ** (stops - (obs.headroom - 1 / 3))]
            if lo <= cam.iso <= hi and room_iso and cam.log_mode not in ("CineEI", "CineEIQuick"):
                new = max(room_iso)
                if new < cam.iso:
                    return Proposal("IsoSensitivity", iso_raw(new), "ISO %d" % cam.iso, "ISO %d" % new,
                                    "Making room for a 180° shutter (%s is %s stops brighter): ISO %d → %d first" % (
                                        fmt_shutter_s(target), frac_stops(stops), cam.iso, new), math.log2(new / cam.iso))
            self._pending_advice = ("180° shutter (%s) needs about %s stops less light first: add ND%s" % (
                fmt_shutter_s(target), frac_stops(stops - max(0.0, obs.headroom - 1 / 3)),
                "" if lo <= cam.iso <= hi else " (ISO is outside your range, so I can't make room with it)"))
            return None
        note = "" if abs(target - 1 / (2 * cam.fps)) / target < 0.03 else " (closest inside the approved range)"
        return Proposal("ShutterSpeed", shutter_raw(target), fmt_shutter_s(cam.shutter_s), fmt_shutter_s(target),
                        "180° shutter for %gp: %s → %s%s; exposure follows next" % (
                            round(cam.fps, 2), fmt_shutter_s(cam.shutter_s), fmt_shutter_s(target), note), stops)

    # ----------------------------------------------------------- 2. aperture
    def _f_options(self, cam):
        lo, hi = self.ranges.fnumber
        return sorted(f for f in cam.f_options if lo - 0.01 <= f <= hi + 0.01)

    def _aperture_rule(self, cam, obs):
        lo, hi = self.look.aperture_range
        f = cam.fnumber
        if lo - 0.05 <= f <= hi + 0.05:
            return None
        if hi < f <= self.look.aperture_last_resort + 0.05:
            # Closed down as a last resort: only reopen when it won't clip.
            if obs.headroom - 2 * math.log2(f / hi) < 1 / 3 or obs.clipped_important > self.look.max_clip_pct:
                return None
        target = min(self._f_options(cam) or [self.look.aperture], key=lambda x: abs(math.log2(x / self.look.aperture)))
        if abs(math.log2(target / f)) < 0.05:
            return None
        stops = 2 * math.log2(f / target)
        return Proposal("FNumber", f_raw(target), "f/%g" % f, "f/%g" % target,
                        "%s look wants f/%g: f/%g → f/%g; exposure follows next" % (
                            self.look.name.split(" (")[0], self.look.aperture, f, target), stops)

    # ----------------------------------------------------------- 3. exposure
    def _recent(self, seconds=0.5):
        t_end = self.history[-1].t
        return [o for o in self.history if t_end - o.t <= seconds] or [self.history[-1]]

    def _exposure(self, cam, obs, settling):
        look = self.look
        self.cap = None
        recent = self._recent()
        key = median([o.key for o in recent])
        faces = [o.face for o in recent if o.face is not None]
        face = median(faces) if look.face_priority and len(faces) >= 0.6 * len(recent) else None
        face_clipping = sum(o.face_clipping for o in recent) > len(recent) / 2
        clipped = median([o.clipped_important for o in recent])
        headroom = median([o.headroom for o in recent])
        advice = []

        lo, hi = look.key_window
        if face is not None:
            exposure_err = look.face_target - face
        else:
            exposure_err = lo - key if key < lo else hi - key if key > hi else 0.0
        total = None                       # full amount needed, for ND/light advice

        if clipped > look.max_clip_pct or face_clipping:
            kind = "highlights"
            what = "Face clipping" if face_clipping else "Highlights clipping %.1f%% (limit %.1f%%)" % (clipped, look.max_clip_pct)
            D = -max(1 / 3, look.max_step)
            total = min(D, exposure_err)    # clipped detail can't be measured: at least this much
            if face is not None and face < look.face_target - DEAD_BAND and not face_clipping:
                advice.append("Face is %s stop under, but bright areas clip: add light on the face, or reframe "
                              "the bright area out" % frac_stops(look.face_target - face))
        else:
            if face is not None:
                kind = "face"
                what = "Face %+.1f st (target %+.1f)" % (face, look.face_target)
            else:
                kind = "key"
                what = "Scene %+.1f st (window %+.1f to %+.1f)" % (key, lo, hi)
            D = exposure_err
            if D > 0:
                # Recently darkened for clipping? Then keep a bigger safety margin for a while.
                margin = 2 / 3 if obs.t < self.highlight_guard_until else 1 / 3
                room = headroom - margin
                if room < D:
                    if room < DEAD_BAND:
                        advice.append("%s, but brightening would clip the brightest area (%.1f st headroom): "
                                      "add light to the subject instead" % (what, headroom))
                    D = max(0.0, room)
                self.cap = self._ceiling_room(cam, key, obs.t)
                if self.cap is not None and self.cap < D:
                    if self.cap < DEAD_BAND <= D:           # (headroom advice already covers smaller D)
                        advice.append("%s, but going brighter clipped the bright area a moment ago: "
                                      "add light to the subject instead" % what)
                    D = max(0.0, self.cap)

        if abs(D) < DEAD_BAND:
            self.pending = None
            self.nd_advice_since = None
            wb = self._white_balance(cam, obs, settling)
            if wb and not self.may(wb.setting):
                advice.append(would(wb))
            elif wb:
                return self._commit(wb, obs.t, 0)
            if abs(exposure_err) >= DEAD_BAND:                  # held short of the target by clipping
                status = "Holding: %s; any brighter would clip" % what
            else:
                status = "Exposure good: scene %+.1f st%s" % (key, ", face %+.1f st" % face if face is not None else "")
            return Output(None, advice + self._wb_advice(cam), status)

        sign = 1 if D > 0 else -1
        react = look.react_after_s       # same for every problem, so a walk-by never triggers a change
        if self.pending is None or self.pending[:2] != (kind, sign):
            self.pending = (kind, sign, obs.t)
        waited = obs.t - self.pending[2]
        if waited < react:
            return Output(None, advice, "%s: waiting %.1f s to be sure it's not a passing change" % (what, react - waited))
        if (self.last_change_sign == -sign and obs.t - self.last_change_t < REVERSAL_WINDOW_S
                and abs(D) < 2 * DEAD_BAND and kind != "highlights"):
            return Output(None, advice, "%s: holding, to avoid undoing the last change" % what)
        if settling:
            return Output(None, advice, "Waiting for the last change to settle")

        step = max(-look.max_step, min(look.max_step, D))
        proposal, more = self._levers(cam, step, total if total is not None else D, kind, what, headroom)
        advice += more
        if proposal is None:
            return Output(None, advice, advice[-1] if advice else what + ": nothing left to adjust on the camera")
        if kind == "highlights":
            self.highlight_guard_until = obs.t + 15.0
            self.ceiling = (cam_ev(cam), key - cam_ev(cam), obs.t)
        out = self._commit(proposal, obs.t, sign)
        out.advice = advice
        return out

    def _ceiling_room(self, cam, key, t):
        """Stops of brightening left before the exposure that clipped last time (None = no limit).
        If the light itself has dropped since then (measured), the limit moves up by that much."""
        if self.ceiling is None:
            return None
        ev_clipped, scene_then, since = self.ceiling
        if t - since > CEILING_S:
            self.ceiling = None
            return None
        return ev_clipped + (scene_then - (key - cam_ev(cam))) - cam_ev(cam) - 1 / 3

    def _levers(self, cam, step, D, kind, what, headroom):
        """Turn an exposure change (stops) into ONE camera change, or advice."""
        look, advice = self.look, []
        iso_ok = cam.log_mode not in ("CineEI", "CineEIQuick") and self.may("IsoSensitivity")   # Cine EI: ISO locked to base
        isos = sorted(i for i in cam.iso_options if self.ranges.iso[0] <= i <= self.ranges.iso[1])
        fs = self._f_options(cam) if self.may("FNumber") else []
        lo_f, hi_f = look.aperture_range

        if step > 0:
            if iso_ok and isos and cam.iso < isos[-1]:
                new = self._choose_iso(cam.iso, step, D, isos, headroom)
                if new != cam.iso:
                    return self._iso_proposal(cam.iso, new, what), advice
            wider = [f for f in fs if lo_f - 0.05 <= f < cam.fnumber - 0.05]
            if wider:
                new_f = min(wider, key=lambda f: abs(2 * math.log2(cam.fnumber / f) - step))
                return self._f_proposal(cam.fnumber, new_f, what), advice
            advice.append("Too dark by about %s stops at ISO %d, f/%g: add light, or take ND off if any is fitted"
                          % (frac_stops(D), cam.iso, cam.fnumber))
            return None, advice

        # Darker.
        if iso_ok and isos and cam.iso > isos[0]:
            if look.iso_policy == "base_first" and cam.iso in BASE_ISOS and abs(D) <= 2 / 3 and kind != "highlights":
                return None, ["Holding base ISO %d: %s stop brighter than target, highlights safe" % (cam.iso, frac_stops(D))]
            new = self._choose_iso(cam.iso, step, D, isos, headroom)
            if new != cam.iso:
                return self._iso_proposal(cam.iso, new, what), advice
        narrower = [f for f in fs if cam.fnumber + 0.05 < f <= hi_f + 0.05]
        if narrower:
            new_f = min(narrower, key=lambda f: abs(2 * math.log2(f / cam.fnumber) + step))
            return self._f_proposal(cam.fnumber, new_f, what), advice

        at_look = abs(cam.fnumber - look.aperture) < 0.05
        advice.append("Too bright at ISO %d and f/%g%s: add %s %s stops of ND" % (
            cam.iso, cam.fnumber, " (the look's aperture)" if at_look else "",
            "at least" if kind == "highlights" else "about", frac_stops(D)))
        if kind == "highlights":
            now = self.history[-1].t
            self.nd_advice_since = self.nd_advice_since or now
            last = [f for f in fs if hi_f + 0.05 < f <= look.aperture_last_resort + 0.05 and f > cam.fnumber + 0.05]
            if last and now - self.nd_advice_since >= ND_LAST_RESORT_AFTER_S:
                new_f = min(last)
                p = self._f_proposal(cam.fnumber, new_f, what)
                p.reason = "%s and no ND added: last resort, closing to f/%g" % (what, new_f)
                return p, advice
        else:
            self.nd_advice_since = None
        return None, advice

    def _choose_iso(self, iso, step, D, isos, headroom):
        want = iso * 2 ** step
        if self.look.iso_policy == "base_first":
            if step > 0 and iso < 4000 <= isos[-1] and want >= 2000:
                extra = math.log2(4000 / want)
                # Only if the WHOLE jump keeps the brightest important area 2/3 stop below clipping.
                jump = math.log2(4000 / iso)
                if extra <= 2 / 3 and headroom - jump >= 2 / 3 and (self.cap is None or jump <= self.cap + 0.05):
                    return 4000                     # high base ISO: cleaner than 2500-3200
            if step < 0 and want <= 800 * 2 ** (1 / 3) and 800 in isos:
                return 800
        direction = [i for i in isos if (i > iso if step > 0 else i < iso)]
        if not direction:
            return iso
        return min(direction, key=lambda i: abs(math.log2(i / want)))

    def _iso_proposal(self, old, new, what):
        stops = math.log2(new / old)
        tag = " (base ISO)" if new in BASE_ISOS else ""
        return Proposal("IsoSensitivity", iso_raw(new), "ISO %d" % old, "ISO %d" % new,
                        "%s: ISO %d → %d%s" % (what, old, new, tag), stops)

    def _f_proposal(self, old, new, what):
        stops = 2 * math.log2(old / new)
        verb = "opening" if new < old else "closing"
        return Proposal("FNumber", f_raw(new), "f/%g" % old, "f/%g" % new,
                        "%s: %s to f/%g" % (what, verb, new), stops)

    # ------------------------------------------------------ 4. white balance
    def _wb_advice(self, cam):
        if cam.wb_mode == "AWB":
            return ["WB is on Auto and can drift mid-shot: set a Kelvin value before rolling"]
        return []

    def _white_balance(self, cam, obs, settling):
        if cam.wb_mode != "ColorTemp" or not cam.wb_kelvin or settling:
            return None
        trusted = [o.light_k for o in self.history if o.light_k and o.color_confidence in ("medium", "high")]
        if len(trusted) < max(3, 0.8 * len(self.history)) or self.history[-1].t - self.history[0].t < 2.5:
            return None
        light = median(trusted)
        if abs(1e6 / light - 1e6 / cam.wb_kelvin) < 20:        # within ~20 mired: leave it
            return None
        lo, hi = self.ranges.kelvin
        target = int(round(min(max(light, lo), hi) / 100.0) * 100)
        if target == cam.wb_kelvin:
            return None
        return Proposal("Colortemp", target, "%dK" % cam.wb_kelvin, "%dK" % target,
                        "Light measures about %dK, WB is %dK: setting %dK" % (light, cam.wb_kelvin, target))
