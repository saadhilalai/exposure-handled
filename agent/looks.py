"""Look presets: what the director picks. Every number is a starting point the director can tune.

Exposure numbers are stops vs 18% grey as the eyes measure them. In S-Log3,
0 = Sony's reference exposure (grey at 41% IRE). Many cinematographers rate
S-Log3 a little brighter for cleaner shadows; that's the "+" on some targets.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Look:
    key: str
    name: str
    description: str
    aperture: float                    # the f-stop this look wants
    aperture_range: tuple              # f-stops the brain may use to control exposure
    aperture_last_resort: float        # may close to this ONLY to stop important clipping no ND fixed
    iso_policy: str                    # "base_first": stay on base ISOs (800/4000) when possible; "free"
    face_priority: bool                # expose for faces when there are faces
    face_target: float                 # where a face should sit (stops vs grey)
    key_window: tuple                  # acceptable scene exposure when there's no face (stops)
    max_clip_pct: float                # important highlights allowed to clip (% of frame)
    react_after_s: float               # a problem must last this long before acting (ignores walk-bys)
    max_step: float                    # biggest single change (stops)
    min_gap_s: float                   # least time between two changes
    shutter_180: bool                  # hold a 180-degree shutter (video looks)


LOOKS = {
    "cinematic": Look(
        key="cinematic", name="Cinematic 24p (shallow)",
        description="Shallow depth at f/2.8 and a 180-degree shutter define the look, so they stay put. "
                    "Brightness is handled with base ISO and your ND; the agent asks for ND rather than "
                    "stopping down. Slow, small moves so changes never show on screen.",
        aperture=2.8, aperture_range=(2.8, 2.8), aperture_last_resort=4.0, iso_policy="base_first",
        face_priority=True, face_target=0.5, key_window=(-1.0, 1.0), max_clip_pct=0.5,
        react_after_s=1.5, max_step=1 / 3, min_gap_s=1.0, shutter_180=True),
    "run_and_gun": Look(
        key="run_and_gun", name="Run and gun",
        description="Deeper focus (f/5.6) so a moving subject stays sharp, and quick reactions. ISO is the "
                    "main lever, then aperture between f/4 and f/8. Accepts a little more clipping to keep up.",
        aperture=5.6, aperture_range=(4.0, 8.0), aperture_last_resort=8.0, iso_policy="free",
        face_priority=True, face_target=0.5, key_window=(-0.5, 0.7), max_clip_pct=1.5,
        react_after_s=0.5, max_step=2 / 3, min_gap_s=0.5, shutter_180=True),
    "interview": Look(
        key="interview", name="Interview (face priority)",
        description="The face is everything: it holds the face at its target and moves slowly so the "
                    "exposure never pumps during an answer. Background windows may clip a little; the face may not.",
        aperture=4.0, aperture_range=(2.8, 5.6), aperture_last_resort=5.6, iso_policy="base_first",
        face_priority=True, face_target=0.5, key_window=(-1.5, 1.5), max_clip_pct=2.0,
        react_after_s=2.0, max_step=1 / 3, min_gap_s=2.0, shutter_180=True),
    "low_light": Look(
        key="low_light", name="Low light",
        description="Wide open at f/2.8 and ISO up to 12800, preferring the high base ISO 4000. Accepts a "
                    "darker, moodier key instead of pushing noise, and says when it simply needs more light.",
        aperture=2.8, aperture_range=(2.8, 2.8), aperture_last_resort=2.8, iso_policy="base_first",
        face_priority=True, face_target=0.5, key_window=(-2.0, 0.5), max_clip_pct=1.0,
        react_after_s=1.0, max_step=1 / 3, min_gap_s=1.0, shutter_180=True),
    "photo_portrait": Look(
        key="photo_portrait", name="Photo portrait",
        description="Stills portrait: shallow f/2.8 (up to f/4), exposure set for the face. Shutter is left to "
                    "you, because the approved shutter range is for video only.",
        aperture=2.8, aperture_range=(2.8, 4.0), aperture_last_resort=4.0, iso_policy="base_first",
        face_priority=True, face_target=0.5, key_window=(-1.0, 1.0), max_clip_pct=0.5,
        react_after_s=1.0, max_step=1 / 3, min_gap_s=1.0, shutter_180=False),
}
