"""Tone curves: turn a live-view pixel (0-255) into "stops above or below 18% grey".

S-Log3 is Sony's published curve (10-bit code values):
    reflectance x >= 0.01125:  code = 420 + 261.5 * log10((x + 0.01) / 0.19)
    below that (the "toe"):    code = 95 + x * (171.2102946929 - 95) / 0.01125
So 18% grey = code 420, 90% white = code ~598, black = code 95, and one stop is
about 78.7 code values in the log part.

The live-view JPEG is 8-bit, and how Sony squeezes S-Log3 into it is NOT documented.
We model it with two numbers kept in config/liveview_calibration.json:
    A = 8-bit value where 18% grey lands
    B = 8-bit levels per stop (in the log part of the curve)
Starting guess: legal-range S-Log3 stretched to 0-255 (A = 103.6, B = 22.9).
The grey card test measures the real A and B.
"""
import json
import math
from pathlib import Path

import numpy as np

CALIBRATION_FILE = Path(__file__).resolve().parent.parent / "config" / "liveview_calibration.json"

GREY = 0.18
CODE_PER_STOP = 261.5 * math.log10(2)  # ~78.72 code values per stop in S-Log3's log section
TOE_CUT = 0.01125
TOE_TOP_CODE = 171.2102946929


def slog3_code(x):
    """Scene reflectance (0.18 = grey) -> S-Log3 10-bit code value."""
    if x >= TOE_CUT:
        return 420.0 + 261.5 * math.log10((x + 0.01) / 0.19)
    return 95.0 + x * (TOE_TOP_CODE - 95.0) / TOE_CUT


def slog3_reflectance(code):
    """S-Log3 10-bit code value -> scene reflectance (inverse of slog3_code)."""
    if code >= TOE_TOP_CODE:
        return 0.19 * 10 ** ((code - 420.0) / 261.5) - 0.01
    return (code - 95.0) * TOE_CUT / (TOE_TOP_CODE - 95.0)


def load_calibration(path=CALIBRATION_FILE):
    return json.loads(Path(path).read_text())


class ToneModel:
    """Converts 8-bit live-view values to stops relative to 18% grey, for one tone (log or normal)."""

    def __init__(self, tone, calibration):
        self.tone = tone
        cal = calibration[tone if tone in calibration else "rec709"]
        self.cal = cal
        self.clip_level = cal["clip_level"]      # 8-bit value where highlights stop (measured)
        self.floor_level = cal["floor_level"]    # 8-bit value of black
        self.stops_lut = self._build_lut()       # 256 entries: value -> stops vs grey
        self.clip_stops = float(self.stops_lut[min(255, self.clip_level)])

    def _build_lut(self):
        lut = np.empty(256, dtype=np.float32)
        for v in range(256):
            lut[v] = self._stops(v)
        return lut

    def _stops(self, v):
        floor = self.cal["floor_level"]
        if self.tone == "slog3":
            a, b = self.cal["grey_level"], self.cal["levels_per_stop"]
            code = 420.0 + (v - a) / b * CODE_PER_STOP          # back to S-Log3 code space
            code = max(code, 95.0 + 0.5)                          # below black: clamp just above black
            x = max(slog3_reflectance(code), 1e-6)
            return math.log2(x / GREY)
        # Normal (Rec.709-like) picture profiles: approximate with the BT.709 curve.
        e = max(v, floor + 0.5) / 255.0
        lin = e / 4.5 if e < 0.081 else ((e + 0.099) / 1.099) ** (1 / 0.45)
        return math.log2(max(lin, 1e-6) / GREY)

    def to_stops(self, values):
        """8-bit values (any numpy shape, or a number) -> stops vs 18% grey."""
        idx = np.clip(np.rint(values), 0, 255).astype(np.int32)
        return self.stops_lut[idx]

    def level_for_stops(self, stops):
        """Inverse, for drawing: the 8-bit value where `stops` lands."""
        return int(np.searchsorted(self.stops_lut, stops))

    def to_linear(self, values):
        """8-bit values -> linear light (1.0 = 100% reflectance), per channel. For color estimates."""
        return GREY * np.power(2.0, self.to_stops(values))
