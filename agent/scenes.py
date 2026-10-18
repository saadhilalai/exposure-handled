"""Fake scenes for the simulator: the Step 7 situations plus stress tests.

Values are stops vs 18% grey at the reference exposure (ISO 800, f/2.8, 1/48, no ND).
"""
import math
from dataclasses import dataclass, field
from typing import Callable, Optional

from agent.sim import SceneState, ramp


@dataclass
class SceneSpec:
    name: str
    look: str
    seconds: float
    scene: Callable
    expect: str                                  # what a good operator would do
    camera: dict = field(default_factory=dict)   # SimCamera starting settings
    recording: Optional[Callable] = None
    operator_nd_delay: Optional[float] = None
    event_t: Optional[float] = None              # when the scene changes (for settle time)


SCENES = [
    SceneSpec("static", "cinematic", 20,
              lambda t: SceneState(key=-0.3, face=0.9, highlight=3.0, highlight_area=5),
              "Nothing to fix: no changes at all."),
    SceneSpec("walk_by_window", "cinematic", 20,
              lambda t: SceneState(key=-0.3, face=0.9, highlight=6.5 if 8 <= t < 9 else 3.0,
                                   highlight_area=12 if 8 <= t < 9 else 5),
              "A window flashes into frame for 1 s (someone walks past): ignore it."),
    SceneSpec("person_walks_through", "cinematic", 20,
              lambda t: SceneState(key=-2.3 if 8 <= t < 9.2 else -0.3,
                                   face=None if 8 <= t < 9.2 else 0.9, highlight=3.0, highlight_area=5),
              "Someone crosses in front of the lens for 1.2 s: ignore it."),
    SceneSpec("flicker_bait", "cinematic", 40,
              lambda t: SceneState(key=-0.3, face=0.2 + 0.15 * math.sin(2 * math.pi * t / 3),
                                   highlight=3.0, highlight_area=5),
              "Face wobbles right at the edge of 'too dark': at most one change, never back and forth."),
    SceneSpec("sunset", "cinematic", 120,
              lambda t: SceneState(key=ramp(t, 10, 110, 0.0, -3.0), face=ramp(t, 10, 110, 1.0, -2.0),
                                   highlight=ramp(t, 10, 110, 4.5, 1.5), highlight_area=30),
              "Light falls 3 stops over 100 s: small steps up, always the same direction, base ISO preferred."),
    SceneSpec("backlit_window_face", "interview", 30,
              lambda t: SceneState(key=0.0, face=-0.5, highlight=6.5, highlight_area=20),
              "Big window behind a darker face: protect the window and tell the operator to light the face.",
              camera={"fnumber": 4.0}),
    SceneSpec("shade_to_sun", "run_and_gun", 30,
              lambda t: (SceneState(key=-0.3, face=0.9, highlight=3.0, highlight_area=10) if t < 8 else
                         SceneState(key=3.5, face=4.7, highlight=7.0, highlight_area=25)),
              "Subject walks from shade into sun (+3.8 stops): bring it down quickly, then ask for ND.",
              camera={"iso": 3200, "fnumber": 5.6}, event_t=8),
    SceneSpec("tungsten_interior", "cinematic", 30,
              lambda t: SceneState(key=-3.0, face=-2.0, highlight=2.0, highlight_area=2, light_k=3200),
              "Dim tungsten room, WB still on 5600K: lift the face with ISO (prefer base 4000), set WB to 3200K."),
    SceneSpec("low_light", "low_light", 30,
              lambda t: SceneState(key=-6.0, face=-5.0, highlight=-1.0, highlight_area=2),
              "Very dark: go to ISO 12800 and then say it needs more light.",
              camera={"iso": 4000}),
    SceneSpec("bright_day_no_nd", "cinematic", 30,
              lambda t: SceneState(key=3.0, face=4.0, highlight=7.0, highlight_area=25),
              "Bright day at f/2.8 base ISO: ask for ND; if nobody adds it, close to f/4 as a last resort."),
    SceneSpec("bright_day_with_operator", "cinematic", 30,
              lambda t: SceneState(key=3.0, face=4.0, highlight=7.0, highlight_area=25),
              "Same, but the operator adds the advised ND after 3 s: no aperture change needed.",
              operator_nd_delay=3.0),
    SceneSpec("recording_lock", "cinematic", 120,
              lambda t: SceneState(key=ramp(t, 10, 110, 0.0, -3.0), face=ramp(t, 10, 110, 1.0, -2.0),
                                   highlight=ramp(t, 10, 110, 4.5, 1.5), highlight_area=30),
              "Sunset again, but recording from 20 s to 100 s: no changes while rolling.",
              recording=lambda t: 20 <= t < 100),
    SceneSpec("cine_ei", "cinematic", 30,
              lambda t: SceneState(key=-2.5, face=-1.0, highlight=2.0, highlight_area=2),
              "Cine EI mode: recorded ISO is locked to base, so never touch ISO.",
              camera={"log_mode": "CineEI"}),
    SceneSpec("wrong_shutter_start", "cinematic", 15,
              lambda t: SceneState(key=-0.3, face=0.9, highlight=3.0, highlight_area=5),
              "Camera starts at 1/160 (like after your shoot): put it on 180° (1/48), then fix exposure.",
              camera={"shutter_s": 1 / 160}),
]
