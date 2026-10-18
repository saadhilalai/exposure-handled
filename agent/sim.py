"""Camera + scene simulator: tests the brain with no camera connected.

A scene is described at a reference exposure (ISO 800, f/2.8, 1/48, no ND) in the
units the eyes measure: stops vs 18% grey. The simulated camera applies the brain's
proposals with the delays measured on the real FX2 in Step 3: a change lands about
0.15 s after it's sent and shows in the picture about 0.3 s after.
"""
import math
import random
from dataclasses import dataclass, field
from typing import Callable, Optional

from agent.brain import Brain, CamState, Observation
from agent.tone import ToneModel, load_calibration

FX2_ISOS = [200, 250, 320, 400, 500, 640, 800, 1000, 1250, 1600, 2000, 2500, 3200, 4000, 5000, 6400,
            8000, 10000, 12800, 16000, 20000, 25600, 32000, 40000, 51200, 64000, 80000, 102400]
SIGMA_28_70_F = [2.8, 3.2, 3.5, 4.0, 4.5, 5.0, 5.6, 6.3, 7.1, 8.0, 9.0, 10.0, 11.0, 13.0, 14.0, 16.0, 18.0, 20.0, 22.0]
FX2_SHUTTERS = [1 / d for d in (30, 40, 48, 50, 60, 80, 96, 100, 120, 125, 160, 200, 250, 320, 400, 500, 640, 800, 1000)]
CLIP_STOPS = ToneModel("slog3", load_calibration()).clip_stops
LAND_S, SHOW_S = 0.15, 0.15          # sent -> camera (0.15 s) -> picture (another 0.15 s)


@dataclass
class SceneState:
    key: float                       # scene exposure at reference settings
    face: Optional[float] = None     # largest face, or None
    highlight: float = 3.0           # brightest important area (sky, window, wall)
    highlight_area: float = 5.0      # its size, % of frame
    light_k: Optional[int] = None    # light color, if the simulated color estimate is trusted


def ramp(t, t0, t1, a, b):
    if t <= t0:
        return a
    if t >= t1:
        return b
    return a + (b - a) * (t - t0) / (t1 - t0)


class SimCamera:
    def __init__(self, iso=800, fnumber=2.8, shutter_s=1 / 48, fps=23.976, nd=0.0, recording=False,
                 log_mode="FlexibleISO", wb_mode="ColorTemp", wb_kelvin=5600):
        self.iso, self.fnumber, self.shutter_s, self.fps = iso, fnumber, shutter_s, fps
        self.nd, self.recording, self.log_mode = nd, recording, log_mode
        self.wb_mode, self.wb_kelvin = wb_mode, wb_kelvin
        self.queue = []
        self.ev_log = [(-1e9, self.ev())]

    def ev(self):
        return (math.log2(self.iso / 800) + math.log2(self.shutter_s * 48)
                - 2 * math.log2(self.fnumber / 2.8) - self.nd)

    def request(self, t, p):
        value = {"IsoSensitivity": lambda r: r, "FNumber": lambda r: r / 100,
                 "ShutterSpeed": lambda r: 1 / (r & 0xFFFF), "Colortemp": lambda r: r}[p.setting](p.raw)
        self.queue.append((t + LAND_S, p.setting, value))

    def step(self, t):
        for item in [q for q in self.queue if q[0] <= t]:
            _, setting, value = item
            if setting == "IsoSensitivity":
                self.iso = value
            elif setting == "FNumber":
                self.fnumber = value
            elif setting == "ShutterSpeed":
                self.shutter_s = value
            elif setting == "Colortemp":
                self.wb_kelvin = value
            self.queue.remove(item)
            self.ev_log.append((t, self.ev()))

    def picture_ev(self, t):
        """The exposure the picture shows at time t (the camera's state SHOW_S ago)."""
        shown = self.ev_log[0][1]
        for when, ev in self.ev_log:
            if when <= t - SHOW_S:
                shown = ev
        return shown

    def state(self):
        return CamState(iso=self.iso, fnumber=self.fnumber, shutter_s=self.shutter_s, fps=self.fps,
                        log_mode=self.log_mode, wb_mode=self.wb_mode, wb_kelvin=self.wb_kelvin,
                        recording=self.recording, iso_options=FX2_ISOS, f_options=SIGMA_28_70_F,
                        shutter_options=FX2_SHUTTERS)


def measure(s, ev, t, rng, noise=0.03):
    """What the eyes would report for scene state `s` at picture exposure `ev`."""
    hl = s.highlight + ev       # the brightest part of the bright area (like the eyes' 99th percentile)
    # The bright area spans about a stop below its brightest part, so it clips progressively
    # once its brightest part reaches the clip point (same meaning of "headroom" as the eyes).
    clipped = s.highlight_area * min(1.0, max(0.0, (hl - CLIP_STOPS) / 1.0 + (0.01 if hl >= CLIP_STOPS else 0)))
    face = None if s.face is None else s.face + ev + rng.gauss(0, noise)
    return Observation(t=t, key=s.key + ev + rng.gauss(0, noise), face=face,
                       face_clipping=face is not None and face >= CLIP_STOPS - 0.2,
                       clipped_important=round(clipped, 2), headroom=round(CLIP_STOPS - min(hl, CLIP_STOPS), 2),
                       light_k=s.light_k, color_confidence="medium" if s.light_k else "low")


@dataclass
class Run:
    log: list = field(default_factory=list)          # (t, picture_ev, obs, output)
    changes: list = field(default_factory=list)      # (t, proposal)
    advice: list = field(default_factory=list)       # (t, text), first time each text appears

    def exposure_changes(self):
        return [(t, p) for t, p in self.changes if p.setting in ("IsoSensitivity", "FNumber")]

    def reversals(self, window=5.0):
        ex = self.exposure_changes()
        return sum(1 for (t0, a), (t1, b) in zip(ex, ex[1:])
                   if a.stops * b.stops < 0 and t1 - t0 < window)

    def seconds_clipping(self, limit, dt):
        return sum(dt for _, _, obs, _ in self.log if obs.clipped_important > limit)


def simulate(scene: Callable[[float], SceneState], cam: SimCamera, brain: Brain, seconds, fps=24.0, seed=1,
             recording: Optional[Callable[[float], bool]] = None, operator_nd_delay: Optional[float] = None):
    """Run the closed loop. `operator_nd_delay`: a simulated camera op who adds the advised ND after N s."""
    rng = random.Random(seed)
    run, seen_advice, nd_asked = Run(), set(), None
    dt = 1.0 / fps
    for i in range(int(seconds * fps)):
        t = i * dt
        if recording:
            cam.recording = recording(t)
        cam.step(t)
        obs = measure(scene(t), cam.picture_ev(t), t, rng)
        out = brain.update(obs, cam.state())
        run.log.append((t, cam.picture_ev(t), obs, out))
        if out.proposal:
            run.changes.append((t, out.proposal))
            cam.request(t, out.proposal)
        for a in out.advice:
            if a not in seen_advice:
                seen_advice.add(a)
                run.advice.append((t, a))
        nd_text = next((a for a in out.advice if "of ND" in a), None)
        if operator_nd_delay is not None and nd_text:
            nd_asked = nd_asked if nd_asked is not None else t
            if t - nd_asked >= operator_nd_delay:
                amount = nd_text.split(" stops of ND")[0].split(" ")[-1]
                cam.nd += parse_stops(amount)
                cam.ev_log.append((t, cam.ev()))
                nd_asked = None
        elif not nd_text:
            nd_asked = None
    return run


def parse_stops(text):
    whole = "".join(ch for ch in text if ch.isdigit())
    return (int(whole) if whole else 0) + (1 / 3 if "⅓" in text else 2 / 3 if "⅔" in text else 0)
