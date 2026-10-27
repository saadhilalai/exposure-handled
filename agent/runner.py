"""The agent loop: eyes → brain → safety gate → bridge, one live-view frame at a time.

Dry run (the default) never sends a change: proposals are shown and logged as "would
change". Live mode hands each proposal to SafetyGate.change_setting(), the only way the
agent changes the camera, and only for settings the director approved
(config/safe_ranges.json "change_allowed": today ISO only). The brain still plans the
other levers and shows them as advice ("Would change, not approved yet: ...").

Kill switch: kill() locks the bridge over its own connection, so it gets through even
while a change is in flight, and stops the loop. A change already sent finishes
(~0.15 s); nothing after it is sent, and the bridge refuses every change until it's
restarted. A lock from another terminal (tools/kill_switch.py) stops the runner too.
Runaway guard: more than MAX_CHANGES_PER_MIN changes in a minute trips the kill switch.
Any other refused or unconfirmed change pauses the agent until the operator resumes.

Operator controls (keyboard or dashboard): Auto on/off (off = the agent only suggests),
Lock (hold every setting now, the same lock that happens while recording), the look,
and "this face looks right" (agent/faces.py).

Step 7 recording switch (iso_while_recording, off by default): lets the agent change ISO,
and only ISO, while the camera records. Only for a live Step 7 agent take (a take name
like S1_R3_A_agent), and only if the bridge was also started with --allow-iso-while-recording.

Rehearsal recording switch (exposure_while_recording, off by default; director's decision): every
approved exposure setting (ISO, aperture, shutter, WB) may change while the camera records. Only for a
live rehearsal agent take (REH_..._agent, label "rehearsal"), with the exposure switch on, and only if
the bridge was started with --allow-exposure-while-recording. It can never be used in a Step 7 take.
"""
import json
import re
import threading
import time
from collections import deque
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from agent.brain import Brain, Output, cam_state_from_settings, observation_from_report
from agent.bridge_client import BridgeClient
from agent.eyes import Eyes, context_from_settings
from agent.faces import FaceBook
from agent.looks import LOOKS
from agent.safety import SafetyGate, load_ranges
from agent.sony_values import describe_value, load_enums

WATCHED = ("IsoSensitivity", "FNumber", "ShutterSpeed", "WhiteBalance", "Colortemp", "RecordingState",
           "MovieShootingMode", "Movie_Recording_FrameRateSetting", "PictureProfile", "PictureProfile_Gamma")
SUMMARY = ("IsoSensitivity", "ShutterSpeed", "FNumber", "WhiteBalance", "Colortemp")
SETTINGS_EVERY_S = 0.25      # re-read the camera's settings (catches recording and hand changes)
STATUS_EVERY_S = 1.0         # re-read the bridge status (catches a lock from another terminal)
MAX_CHANGES_PER_MIN = 20     # runaway guard: a smooth agent needs far fewer
AGENT_TAKE = re.compile(r"S[1-6]_\w+_agent")   # Step 7 run-sheet names, e.g. S1_R3_A_agent, S1_BONUS_A_agent
REHEARSAL_TAKE = re.compile(r"REH_\w+")          # rehearsal takes, e.g. REH_sunset_A_agent; never Step 7 data
REHEARSAL_AGENT_TAKE = re.compile(r"REH_\w+_agent")
ADVICE_REPEAT_S = 10.0       # show the same advice again only after this long
WOULD_REPEAT_S = 10.0
HISTORY_EVERY_S = 0.25       # exposure history for the dashboard chart
HISTORY_S = 90


class RunnerError(Exception):
    pass


def approved_settings(ranges, exposure=False):
    """Settings the director approved for live changes. Without the exposure switch: ISO only."""
    return {name for name, rule in ranges.items()
            if rule.get("change_allowed") and (exposure or rule.get("switch") != "allow_exposure")}


class AgentRunner:
    def __init__(self, socket_path, session_dir, look="cinematic", live=False, eyes=None, ranges=None,
                 clock=time.monotonic, on_event=None, auto=True, faces=None, iso_while_recording=False, take=None,
                 exposure=False, exposure_while_recording=False, label=None, watch_locked=False):
        """auto=False starts a live session with Auto off: it suggests until the operator turns Auto on.
        iso_while_recording: the Step 7 switch (see above). take: the run-sheet name of this take.
        exposure: aperture, shutter and WB may change too (needs a bridge started with --allow-exposure).
        exposure_while_recording: the rehearsal switch (see above). label: "rehearsal" keeps this data apart.
        watch_locked: watch-only, and keep watching a locked bridge (the Pi after a kill: the phone still sees the
        picture until it's armed again). Never with live=True."""
        if watch_locked and live:
            raise RunnerError("watch_locked is for watching only")
        self.watch_locked = watch_locked
        self.bridge_locked = False
        self.socket_path = socket_path
        self.client = BridgeClient(socket_path)
        self.kill_client = BridgeClient(socket_path)          # its own connection, for the kill switch
        self.session = Path(session_dir)
        self.session.mkdir(parents=True, exist_ok=True)
        self.look = look
        self.live = live
        self.eyes = eyes or Eyes()
        self.ranges = ranges if ranges is not None else load_ranges()
        self.exposure = exposure
        self.allowed = approved_settings(self.ranges, exposure)
        self.iso_while_recording = iso_while_recording
        self.exposure_while_recording = exposure_while_recording
        self.take = take
        self.label = label
        self.gate = SafetyGate(self.client, self.session / "changes.jsonl", self.ranges,
                               iso_while_recording=iso_while_recording, exposure=exposure,
                               exposure_while_recording=exposure_while_recording)
        self.enums = load_enums()
        self.clock = clock
        self.on_event = on_event or (lambda kind, text: None)
        self.killed = False
        self.kill_reason = None
        self.paused = not auto                  # Auto off: proposals are only shown
        self.held = False                       # Lock: hold every setting (operator)
        self.hold_status = "Locked by you: holding every setting"     # what the status line says while held
        self.stop_requested = False
        self.problems = 0                       # problems logged by the operator this session
        self.book = faces if faces is not None else FaceBook()
        self.lock = threading.RLock()           # the dashboard reads state from other threads
        self.events = deque(maxlen=200)
        self.history = deque(maxlen=int(HISTORY_S / HISTORY_EVERY_S))
        self.bgr = None
        self.shift = 0.0                        # picture brightness change since the last sample (stops)
        self.changes = []                       # changes the agent made (and the camera confirmed)
        self.change_times = deque()
        self.shown_advice = {}
        self.active_limits, self.logged_limits = set(), {}
        self.last_would = (None, -1e9)
        self.last_status = None
        self.frame_no = -1
        self.frames = 0
        self.eyes_ms = deque(maxlen=48)
        self.report = self.output = self.jpeg = None
        self.restorable = []
        self.was_recording = None             # logged when the camera starts or stops recording
        self.fps = None

    # ------------------------------------------------------------ logging
    def _log(self, event, **fields):
        entry = {"time": datetime.now().isoformat(timespec="milliseconds"),
                 "t": round(self.clock() - self.t0, 3) if hasattr(self, "t0") else 0.0, "event": event, **fields}
        with (self.session / "runner_log.jsonl").open("a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def _event(self, kind, text, **fields):
        self._log(kind, text=text, **fields)
        with self.lock:
            self.events.append({"t": round(self.clock() - self.t0, 2) if hasattr(self, "t0") else 0.0,
                                "kind": kind, "text": text})
        self.on_event(kind, text)

    def _text(self, name, props=None):
        props = props if props is not None else self.props
        return describe_value(name, props[name]["current"], self.enums) if name in props else "?"

    # -------------------------------------------------------------- start
    def start(self):
        status = self.client.status()
        self.bridge = status
        if not status.get("connected"):
            raise RunnerError("the bridge has no camera connected")
        self.bridge_locked = bool(status.get("locked"))
        if self.bridge_locked and self.watch_locked:
            pass                                  # watching only: nothing can be sent, and the bridge refuses anyway
        elif status.get("locked") and status.get("lock_file"):
            raise RunnerError("the kill switch is still on from before (it outlives restarts): unlock it first")
        elif status.get("locked"):
            raise RunnerError("the bridge is locked (kill switch was used): restart the bridge first")
        if self.live and status.get("read_only"):
            raise RunnerError("live mode needs a bridge started WITHOUT --read-only")
        if self.iso_while_recording and self.exposure_while_recording:
            raise RunnerError("use one recording switch, not both")
        if self.iso_while_recording:
            if not self.live:
                raise RunnerError("the recording switch only makes sense in a live agent take")
            if not (self.take and AGENT_TAKE.fullmatch(self.take)):
                raise RunnerError("the recording switch is for Step 7 agent takes only: give the take name, "
                                  "e.g. --take S1_R3_A_agent")
            if not status.get("iso_while_recording"):
                raise RunnerError("the bridge wasn't started with --allow-iso-while-recording, so it would refuse "
                                  "anyway (both switches must be on)")
        if self.label == "rehearsal" and not (self.take and REHEARSAL_TAKE.fullmatch(self.take)):
            raise RunnerError("rehearsal takes are named REH_..., e.g. --take REH_sunset_A_agent, so they never mix "
                              "with Step 7 data")
        if self.label != "rehearsal" and self.take and REHEARSAL_TAKE.fullmatch(self.take):
            raise RunnerError("REH_ take names are for rehearsals: add --rehearsal")
        if self.exposure_while_recording:
            if not self.live:
                raise RunnerError("the recording switch only makes sense in a live agent take")
            if not self.exposure:
                raise RunnerError("the rehearsal recording switch needs the exposure switch on too")
            if not (self.label == "rehearsal" and self.take and REHEARSAL_AGENT_TAKE.fullmatch(self.take)):
                raise RunnerError("the rehearsal recording switch is for rehearsal agent takes only: "
                                  "--rehearsal --take REH_..._agent")
            if not status.get("exposure_while_recording"):
                raise RunnerError("the bridge wasn't started with --allow-exposure-while-recording, so it would refuse "
                                  "anyway (both switches must be on)")
        if self.exposure and self.live and not status.get("allow_exposure"):
            raise RunnerError("the bridge wasn't started with --allow-exposure, so it would refuse aperture, shutter "
                              "and WB (both switches must be on)")
        self.t0 = self.clock()
        self.start_props = self.client.settings()
        (self.session / "settings_start.json").write_text(json.dumps(self.start_props, indent=1))
        self.props = {n: self.start_props[n] for n in WATCHED if n in self.start_props}
        self._rebuild()
        self.brain = self._new_brain(self.look)
        self.t_settings = self.t_status = self.t_tick = self.t_history = self.clock()
        mode = "LIVE" if self.live else "DRY RUN"
        self._event("start", "%s on %s · look: %s · may change: %s · camera: %s" % (
            mode, status.get("model", "?"), self.brain.look.name, ", ".join(sorted(self.allowed)) or "nothing",
            self.summary()), mode=mode, look=self.brain.look.key, allowed=sorted(self.allowed), bridge=status,
            take=self.take, iso_while_recording=self.iso_while_recording, exposure=self.exposure,
            exposure_while_recording=self.exposure_while_recording, label=self.label,
            settings={n: self._text(n) for n in SUMMARY},
            people=[{k: p[k] for k in ("name", "target")} for p in self.book.summary()])   # face targets in effect

    def _new_brain(self, look):
        return Brain(look, allowed=self.allowed,
                     allow_while_recording=self.iso_while_recording or self.exposure_while_recording)

    def _rebuild(self):
        self.ctx = context_from_settings(self.props, self.enums)
        self.cam = cam_state_from_settings(self.props, self.enums)

    def summary(self):
        wb = self._text("WhiteBalance")
        if wb == "ColorTemp":
            wb = "%dK" % self.props["Colortemp"]["current"]
        return "ISO %d · %s · f/%g · WB %s%s" % (self.cam.iso, self._text("ShutterSpeed"), self.cam.fnumber, wb,
                                                 " · RECORDING" if self.cam.recording else "")

    # ---------------------------------------------------------------- loop
    def run(self, seconds=None):
        t_end = None if seconds is None else self.clock() + seconds
        while self.step():
            if t_end is not None and self.clock() >= t_end:
                break

    def step(self):
        """One live-view frame through eyes → brain → (safety gate → bridge). False = stop."""
        if self.killed or self.stop_requested:
            return False
        try:
            now = self.clock()
            if now - self.t_status >= STATUS_EVERY_S:
                self.t_status = now
                locked = bool(self.client.status().get("locked"))
                if locked and self.watch_locked:
                    self.bridge_locked = True
                elif locked and not self.killed:
                    self._killed_from_outside()
                    return False
            if now - self.t_settings >= SETTINGS_EVERY_S:
                self.t_settings = now
                self.props.update(self.client.get(*WATCHED))
                self._rebuild()
                self._watch_recording()
            header, jpeg = self.client.frame(after=self.frame_no, timeout_ms=1000)
        except Exception as e:                       # bridge gone or camera unplugged
            self._event("error", "Lost the bridge or camera (%s): stopped. Nothing more will be sent." % e)
            return False
        if jpeg is None:
            self._status("No live view: %s" % header.get("error", "?"))
            return True
        self.frame_no = header["frame_no"]
        bgr = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if bgr is None:
            return True
        t = self.clock()
        report = self.eyes.analyze(bgr, self.ctx)
        self.book.label(bgr, report.faces, t)              # known people get their own face target
        with self.lock:
            self.jpeg, self.bgr, self.report = jpeg, bgr, report
        self.frames += 1
        self.shift += (report.change or {}).get("exposure_shift_stops", 0.0)
        self.eyes_ms.append(report.ms)
        if self.held:                                    # Lock: the brain is paused, nothing is proposed
            out = Output(None, [], self.hold_status)
        else:
            out = self.brain.update(observation_from_report(report, t), self.cam)
        self.output = out
        self._advice(out.advice, t)
        self._limits(out.limits, t)
        if t - self.t_history >= HISTORY_EVERY_S:
            self._sample(t)
        if out.proposal is not None:
            self._act(out.proposal, t)
        self._status(out.status)
        if t - self.t_tick >= 1.0:
            self._tick(t)
        return not (self.killed or self.stop_requested)

    def _act(self, p, t):
        if self.killed:
            return
        if not self.live or self.paused or p.setting not in self.allowed:
            self.brain.not_applied()
            why = "dry run" if not self.live else "paused" if self.paused else "not approved"
            if (p.setting, p.raw) != self.last_would[0] or t - self.last_would[1] >= WOULD_REPEAT_S:
                self.last_would = ((p.setting, p.raw), t)
                self._event("would_change", "Would change (%s): %s" % (why, p.reason), setting=p.setting,
                            raw=p.raw, reason=p.reason)
            return
        recent = [x for x in self.change_times if t - x < 60]
        if len(recent) >= MAX_CHANGES_PER_MIN:
            self.kill("Runaway guard: %d changes in under a minute" % len(recent))
            return
        reply = self.gate.change_setting(p.setting, p.raw, p.reason)
        if self.killed:
            return
        if reply.get("ok"):
            self.props[p.setting] = dict(self.props[p.setting], current=reply.get("camera_reports", p.raw))
            self._rebuild()
            if reply.get("changed") is False:          # the camera already had it (changed by hand just now)
                self._log("already_set", setting=p.setting, raw=p.raw)
                return
            self.change_times.append(t)
            n = len(self.changes) + 1
            (self.session / "frames").mkdir(exist_ok=True)
            (self.session / "frames" / ("change_%03d.jpg" % n)).write_bytes(self.jpeg)
            self.changes.append({"t": t, "setting": p.setting, "from": p.from_text, "to": p.to_text,
                                 "reason": p.reason, "ms_confirmed": reply.get("ms_confirmed")})
            self._event("change", "%s  (confirmed in %s ms)" % (p.reason, _ms(reply.get("ms_confirmed"))),
                        setting=p.setting, old=p.from_text, new=p.to_text, reason=p.reason)
            return
        error = reply.get("error", "camera didn't confirm the change")
        if "kill switch" in error:
            self._killed_from_outside()
        elif "recording" in error:
            self._event("refused", "Not changed (camera started recording): %s" % p.reason)
        else:
            self.paused = True
            self._event("pause", "PAUSED: %s was refused (%s). Check the camera, then resume." % (p.to_text, error))

    def _advice(self, advice, t):
        for a in advice:
            same = re.sub(r"[-+]?[0-9][0-9.,]*|[⅓⅔]", "#", a)     # "face -0.9" and "face -0.8" are the same advice
            if t - self.shown_advice.get(same, -1e9) >= ADVICE_REPEAT_S:
                self._event("advice", a)
            self.shown_advice[same] = t

    def _limits(self, limits, t):
        """A limit goes in the decisions feed when it starts; the dashboard shows it for as long as it lasts."""
        for x in limits:
            if x["text"] not in self.active_limits and t - self.logged_limits.get(x["text"], -1e9) >= ADVICE_REPEAT_S:
                self.logged_limits[x["text"]] = t
                self._event("limit", "%s %s" % (x["text"], x["detail"]), settings=sorted(x["tiles"]))
        self.active_limits = {x["text"] for x in limits}

    def _status(self, text):
        quiet = re.sub(r"waiting [0-9.]+ s", "waiting", text)
        if quiet != self.last_status:
            self.last_status = quiet
            self._log("status", text=quiet)
        self.on_event("status_line", text)

    def _tick(self, t):
        self.fps = round(self.frames / max(1e-6, t - self.t_tick), 1)
        r = self.report
        self._log("tick", fps=self.fps, eyes_ms=round(float(np.median(self.eyes_ms)), 1), key=r.key_stops,
                  face=r.faces[0]["stops"] if r.faces else None, headroom=r.headroom_stops,
                  clipped_important=r.clipped_important_pct, camera=self.summary(), paused=self.paused)
        self.frames, self.t_tick = 0, t

    def _watch_recording(self):
        """Log the moment the camera starts or stops recording (the blind-test clips are cut from the mark,
        so the time from Rec start to each mark must be in the log)."""
        rec = bool(self.cam.recording)
        if rec == self.was_recording:
            return
        first, self.was_recording = self.was_recording is None, rec
        if first and not rec:
            return
        self._event("rec", "Camera already recording at the start" if first else
                    "Camera started recording" if rec else "Camera stopped recording", recording=rec)

    def _sample(self, t):
        """4 times a second: one row for the chart and for metrics.csv (what Step 7 measures)."""
        r, face = self.report, (self.report.faces[0] if self.report.faces else None)
        row = {"t": round(t - self.t0, 2), "key": r.key_stops, "face": face and face["stops"],
               "target": face.get("target", self.brain.look.face_target) if face else None,
               "headroom": r.headroom_stops, "clipped": r.clipped_important_pct, "iso": self.cam.iso,
               "shift": round(self.shift, 3), "state": self.state(), "who": face.get("name") if face else None}
        with self.lock:
            self.history.append(row)
        path = self.session / "metrics.csv"
        new = not path.exists()
        with path.open("a") as f:
            if new:
                f.write(",".join(row) + "\n")
            f.write(",".join("" if v is None else str(v) for v in row.values()) + "\n")
        self.shift = 0.0
        self.t_history = t

    # ------------------------------------------------------------ controls
    def kill(self, why="Kill switch"):
        """Stop now: lock the bridge (no more changes until it's restarted) and end the loop."""
        if self.killed:
            return
        self.killed, self.kill_reason = True, why
        reply = self.gate.kill(self.kill_client, why)
        self._event("kill", "%s: stopped, bridge %s. The camera is yours." % (
            why, "locked" if reply.get("locked") else "NOT confirmed locked (%s)" % reply.get("error")))

    def _killed_from_outside(self):
        self.killed, self.kill_reason = True, "bridge locked from outside"
        self.gate.killed = True
        self._event("kill", "The bridge was locked (kill switch from another terminal): stopped. The camera is yours.")

    def toggle_pause(self):
        self.set_auto(self.paused)

    def set_auto(self, on):
        """Auto on: the agent makes approved changes (live sessions only). Off: it only suggests."""
        if self.killed or (on and not self.live) or on == (not self.paused):
            return
        self.paused = not on
        self._event("pause", "Auto ON: the agent changes %s" % ", ".join(sorted(self.allowed)) if on
                    else "Auto OFF: suggesting only, no changes")

    def hold(self, on):
        """Lock: hold every setting as it is now (like the recording lock), until unlocked."""
        if on != self.held and not self.killed:
            self.held = on
            self.brain.pending = None            # after unlocking, problems must last their full wait again
            self._event("lock", "LOCKED by you: holding every setting" if on else "Unlocked")

    def remember_face(self, name=None):
        """'This face looks right': the biggest face, at its exposure over the last second."""
        with self.lock:
            report, bgr = self.report, self.bgr
            recent = [h["face"] for h in self.history if h["face"] is not None and h["t"] >= self.history[-1]["t"] - 1.0] \
                if self.history else []
        faces = [f for f in (report.faces if report else []) if "raw" in f]
        if not faces:
            raise RunnerError("no face in frame")
        stops = float(np.median(recent)) if recent else faces[0]["stops"]
        person = self.book.remember(name, bgr, faces[0], stops)
        self._event("face", "%s: this face looks right at %+.1f st. I'll hold %s there." % (
            person["name"], person["target"], person["name"]), person=person["id"], name=person["name"], target=person["target"])
        return person

    def forget_face(self, person_id):
        names = [p["name"] for p in self.book.people if p["id"] == person_id]
        self.book.forget(person_id)
        if names:
            self._event("face", "Forgot %s (back to the look's face target)" % names[0])

    def state(self):
        """One word for the dashboard badge."""
        if self.killed:
            return "KILLED"
        if self.held:
            return "LOCKED"
        auto = self.live and not self.paused
        if self.cam.recording and not ((self.iso_while_recording or self.exposure_while_recording) and auto):
            return "RECORDING"
        return "AUTO" if auto else "SUGGESTING"

    def snapshot(self):
        """Everything the dashboard shows, as plain JSON-ready values."""
        with self.lock:
            r, out = self.report, self.output
            look = self.brain.look
            snap = {
                "t": round(self.clock() - self.t0, 2), "frame_no": self.frame_no, "fps": self.fps,
                "eyes_ms": round(float(np.median(self.eyes_ms)), 1) if self.eyes_ms else None,
                "mode": "live" if self.live else "dry run", "fake": bool(self.bridge.get("fake")),
                "model": self.bridge.get("model"), "state": self.state(), "auto": self.live and not self.paused and not self.killed,
                "held": self.held, "killed": self.killed, "kill_reason": self.kill_reason,
                "bridge_locked": self.bridge_locked or self.killed,
                "recording": self.cam.recording, "iso_while_recording": self.iso_while_recording, "take": self.take,
                "exposure_while_recording": self.exposure_while_recording, "label": self.label,
                "problems": self.problems,
                "approved": sorted(self.allowed), "changes": len(self.changes),
                "look": {"key": look.key, "name": look.name, "description": look.description,
                         "aperture": look.aperture, "face_target": look.face_target, "max_clip_pct": look.max_clip_pct},
                "looks": [{"key": k, "name": v.name} for k, v in LOOKS.items()],
                "camera": {"iso": self._text("IsoSensitivity"), "shutter": self._text("ShutterSpeed"),
                           "fnumber": "f/%g" % self.cam.fnumber, "wb": self.ctx.wb, "wb_kelvin": self.ctx.wb_kelvin,
                           "frame_rate": self.ctx.frame_rate, "recording": self.cam.recording,
                           "tone": self.ctx.tone_source},
                "status": out.status if out else "Starting", "advice": list(dict.fromkeys(out.advice)) if out else [],
                "limits": out.limits if out and not self.killed else [],
                "events": list(self.events)[-80:], "history": list(self.history),
                "people": self.book.summary(), "faces_available": self.book.available,
            }
            if r is not None:
                snap["eyes"] = {
                    "frame": [r.width, r.height], "key": r.key_stops, "headroom": r.headroom_stops,
                    "clipped": r.clipped_pct, "clipped_important": r.clipped_important_pct,
                    "clipped_practical": r.clipped_practical_pct, "near_clip": r.near_clip_pct,
                    "crushed": r.crushed_pct, "light_sources": r.light_source_regions,
                    "faces": [{k: f.get(k) for k in ("box", "stops", "clipping", "name", "target")} for f in r.faces],
                    "color": {k: r.color.get(k) for k in ("light_estimate_k", "warm_cool", "green_magenta", "confidence")},
                }
        return snap

    def set_look(self, key):
        if key in LOOKS and key != self.brain.look.key:
            self.brain = self._new_brain(key)
            self._event("look", "Look: %s" % self.brain.look.name, look=key)

    def stop(self):
        self.stop_requested = True

    def mark(self, label="light change"):
        """The operator marks a scene event (Step 7: settle time is measured from here)."""
        self._event("mark", "Mark: %s" % label, label=label)

    def problem(self, note=""):
        """The operator logs a problem the moment it happens (flicker, slow, wrong call, confusing screen...).
        Saved with what the agent saw and was doing, to problems.jsonl in the session folder."""
        note = (note or "").strip()[:300]
        with self.lock:
            self.problems += 1
            r, out = self.report, self.output
            entry = {"time": datetime.now().isoformat(timespec="milliseconds"), "t": round(self.clock() - self.t0, 2),
                     "note": note, "frame_no": self.frame_no, "state": self.state(), "look": self.brain.look.key,
                     "camera": {n: self._text(n) for n in SUMMARY}, "recording": self.cam.recording,
                     "status": out.status if out else None, "advice": list(out.advice) if out else [],
                     "key_stops": round(r.key_stops, 2) if r else None,
                     "faces": [round(f["stops"], 2) for f in r.faces] if r else [],
                     "fps": self.fps, "recent_events": list(self.events)[-12:]}
        with (self.session / "problems.jsonl").open("a") as f:
            f.write(json.dumps(entry) + "\n")
        self._event("problem", "Problem logged" + (": " + note if note else " (no note)"), note=note)

    # ---------------------------------------------------------------- end
    def finish(self):
        """Session end: snapshot the settings again and list what changed. Returns the differences."""
        try:
            # A fresh connection: if the loop was interrupted mid-answer (Ctrl-C), the old one is out of step.
            self.client.close()
            self.client = self.gate.client = BridgeClient(self.socket_path)
            end = self.client.settings()
        except Exception as e:
            self._event("end", "Couldn't read the camera at the end (%s)" % e)
            return []
        (self.session / "settings_end.json").write_text(json.dumps(end, indent=1))
        by_agent = {c["setting"] for c in self.changes}
        diffs = []
        for name in SUMMARY:
            if name in self.start_props and name in end and self.start_props[name]["current"] != end[name]["current"]:
                diffs.append({"setting": name, "start": self._text(name, self.start_props), "now": self._text(name, end),
                              "start_raw": self.start_props[name]["current"],
                              "by": "agent" if name in by_agent else "by hand"})
        # only a live session offers to put settings back: a dry run (a camera-auto or manual take) never sends anything
        self.restorable = [d for d in diffs if d["setting"] in self.allowed] if self.live and not self.killed else []
        self._event("end", "Session end: %d change(s) by the agent; settings different from the start: %s" % (
            len(self.changes), ", ".join("%s %s → %s (%s)" % (d["setting"], d["start"], d["now"], d["by"])
                                         for d in diffs) or "none"), diffs=diffs)
        return diffs

    def restore(self):
        """Put approved settings back to where the session started (through the safety gate). Live sessions only."""
        results = []
        if not self.live:
            return results
        for d in self.restorable:
            reply = self.gate.change_setting(d["setting"], d["start_raw"],
                                             "Session end: restoring your starting %s" % d["start"])
            results.append((d, reply))
            self._event("restore", "%s back to %s: %s" % (d["setting"], d["start"],
                                                          "done" if reply.get("ok") else reply.get("error")))
        return results

    def close(self):
        for c in (self.client, self.kill_client):
            try:
                c.close()
            except Exception:
                pass


def _ms(v):
    return "?" if v is None else "%d" % round(v)
