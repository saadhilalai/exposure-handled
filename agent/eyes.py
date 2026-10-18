"""The agent's eyes: measure one live-view frame the way a cinematographer looks at it.

Per frame:
  - brightness histogram, % clipped, % near clip, % crushed
  - exposure in stops vs 18% grey, judged by REGION (8x6 grid). The scene's "key"
    is the middle value of the regions, with light sources (screens, lamps,
    windows) left out, so one bright or changing area can't fool it.
  - change vs the previous frame: the middle region change = real exposure shift;
    regions that changed differently = something moved / a screen changed
  - faces (YuNet detector) and how bright each face is, in stops
  - color: leftover color cast, and the light's color temperature when the
    camera's white balance is a known Kelvin value
  - motion: how much of the picture moved

Whether the picture is log (S-Log3) or normal comes from the camera's own
settings first; a guess from the picture is only a fallback.
"""
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from agent.sony_values import describe_value, fmt_fnumber, fmt_iso, fmt_shutter
from agent.tone import ToneModel, load_calibration

MODEL_FILE = Path(__file__).resolve().parent.parent / "models" / "face_detection_yunet_2023mar.onnx"

LOG_SHOOTING_MODES = {"FlexibleISO", "CineEI", "CineEIQuick"}
GRID_ROWS, GRID_COLS = 6, 8
WORK_W, WORK_H = 256, 144                 # analysis size for regions (cells of 32x24 px)
LUMA_WEIGHTS = np.array([0.0722, 0.7152, 0.2126], dtype=np.float32)  # B, G, R (Rec.709)

# Chromaticities used to turn camera RGB into a color temperature.
PRIMARIES = {
    "slog3": ((0.766, 0.275), (0.225, 0.800), (0.089, -0.087)),   # S-Gamut3.Cine
    "rec709": ((0.640, 0.330), (0.300, 0.600), (0.150, 0.060)),   # Rec.709
}
D65 = (0.3127, 0.3290)
D65_CCT = 6504.0


@dataclass
class CameraContext:
    tone: str                 # "slog3" or "rec709"
    tone_source: str          # how we know, in plain words
    iso: str = "?"
    shutter: str = "?"
    fnumber: str = "?"
    wb: str = "?"
    wb_kelvin: Optional[int] = None   # only when WB is set to a Kelvin value
    frame_rate: str = "?"
    recording: bool = False


def context_from_settings(props, enums):
    """Build the camera context from the bridge's settings dict ({name: property})."""
    def val(name):
        return props[name]["current"] if name in props else None

    def text(name):
        return describe_value(name, val(name), enums) if name in props else None

    shooting_mode, profile, gamma = text("MovieShootingMode"), text("PictureProfile"), text("PictureProfile_Gamma")
    if shooting_mode in LOG_SHOOTING_MODES:
        tone, source = "slog3", "camera: Log shooting (%s) records S-Log3" % shooting_mode
    elif profile not in (None, "Off") and gamma in ("S_Log3", "S_Log2"):
        tone, source = "slog3", "camera: Picture Profile %s, gamma %s" % (profile, gamma)
    elif shooting_mode is None and gamma is None:
        tone, source = "unknown", "camera settings not available"
    else:
        tone, source = "rec709", "camera: no log (Picture Profile %s, gamma %s)" % (profile, gamma)

    wb = text("WhiteBalance") or "?"
    wb_kelvin = val("Colortemp") if wb == "ColorTemp" and val("Colortemp") not in (None, 0, 0xFFFF) else None
    return CameraContext(
        tone=tone, tone_source=source,
        iso=fmt_iso(val("IsoSensitivity")) if val("IsoSensitivity") is not None else "?",
        shutter=fmt_shutter(val("ShutterSpeed")) if val("ShutterSpeed") is not None else "?",
        fnumber=fmt_fnumber(val("FNumber")) if val("FNumber") is not None else "?",
        wb="%dK" % wb_kelvin if wb_kelvin else wb, wb_kelvin=wb_kelvin,
        frame_rate=(text("Movie_Recording_FrameRateSetting") or "?").replace("_", "."),
        recording=val("RecordingState") not in (None, 0),
    )


def guess_tone_from_picture(luma):
    """Fallback only: flat, lifted pictures are probably log."""
    lo, hi = np.percentile(luma, [0.5, 99.5])
    if lo >= 7 and hi <= 230 and hi - lo < 200:
        return "slog3", "picture looks flat (darkest %.0f, brightest %.0f): probably log" % (lo, hi)
    return "rec709", "picture has normal contrast: probably not log"


@dataclass
class FrameReport:
    width: int
    height: int
    tone: str
    tone_source: str
    histogram: list                      # 64 bins of brightness (0-255 in steps of 4)
    clipped_pct: float                   # at the clip level: no detail left
    near_clip_pct: float                 # within half a stop of clipping
    crushed_pct: float                   # 6+ stops under grey (log) / at black (normal)
    key_stops: float                     # scene exposure vs 18% grey, light sources left out
    region_stops: list                   # 6x8 grid, stops vs grey
    light_source_regions: list           # [(row, col)] much brighter than the rest
    practical_regions: list = field(default_factory=list)   # small light sources (lamps, screens): may clip
    clipped_practical_pct: float = 0.0   # clipping inside practicals (allowed)
    clipped_important_pct: float = 0.0   # all other clipping: skies, windows, faces, walls (protected)
    headroom_stops: float = 0.0          # how far the brightest important area can rise before clipping
    faces: list = field(default_factory=list)
    color: dict = field(default_factory=dict)
    change: Optional[dict] = None        # vs previous frame: exposure shift + changed regions
    motion: Optional[dict] = None
    ms: float = 0.0


def rgb_to_xyz_matrix(primaries, white):
    cols = [[x / y, 1.0, (1 - x - y) / y] for x, y in primaries]
    p = np.array(cols).T
    w = np.array([white[0] / white[1], 1.0, (1 - white[0] - white[1]) / white[1]])
    return p * np.linalg.solve(p, w)


def small_clusters(mask, max_size):
    """Regions of `mask` that belong to a connected group (4-neighbour) of at most `max_size` regions."""
    rows, cols = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = np.zeros_like(mask, dtype=bool)
    for r0, c0 in np.argwhere(mask):
        if seen[r0, c0]:
            continue
        stack, group = [(r0, c0)], []
        seen[r0, c0] = True
        while stack:
            r, c = stack.pop()
            group.append((r, c))
            for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if 0 <= nr < rows and 0 <= nc < cols and mask[nr, nc] and not seen[nr, nc]:
                    seen[nr, nc] = True
                    stack.append((nr, nc))
        if len(group) <= max_size:
            for r, c in group:
                out[r, c] = True
    return out


def biggest_agreeing_group(deltas, tolerances):
    """The exposure shift is what the biggest group of regions agrees on.

    A real exposure change (ISO, iris, light) moves every region together. A hand,
    a person or a screen changes only some regions, so the unchanged ones form the
    biggest agreeing group, even if they're less than half the picture.
    Returns (shift in stops, number of regions in the group).
    """
    best_count, best_spread, best_members = -1, 0.0, None
    for candidate in deltas:
        members = np.abs(deltas - candidate) <= tolerances
        count = int(members.sum())
        spread = float(np.abs(deltas[members] - candidate).sum())
        if count > best_count or (count == best_count and spread < best_spread):
            best_count, best_spread, best_members = count, spread, members
    return float(np.median(deltas[best_members])), best_count


def mccamy_cct(x, y):
    n = (x - 0.3320) / (0.1858 - y)
    return 449 * n ** 3 + 3525 * n ** 2 + 6823.3 * n + 5520.33


class Eyes:
    def __init__(self, calibration=None, face_model=MODEL_FILE, face_every=3):
        self.calibration = calibration or load_calibration()
        self.tones = {}
        self.face_model = Path(face_model)
        self.face_every = face_every
        self.detector = None
        self.frame_count = 0
        self.last_faces = []
        self.prev = None

    def tone_model(self, tone):
        if tone not in self.tones:
            self.tones[tone] = ToneModel(tone, self.calibration)
        return self.tones[tone]

    def analyze(self, bgr, ctx, compare=True):
        t0 = time.perf_counter()
        h, w = bgr.shape[:2]
        luma = cv2.transform(bgr, LUMA_WEIGHTS.reshape(1, 3)) if bgr.ndim == 3 else bgr
        if luma.ndim == 3:
            luma = luma[..., 0]

        tone, tone_source = ctx.tone, ctx.tone_source
        if tone == "unknown":
            tone, tone_source = guess_tone_from_picture(luma)
        tm = self.tone_model(tone)

        # Whole-picture numbers (full resolution, so small clipped highlights count).
        counts = np.bincount(luma.ravel(), minlength=256)
        total = luma.size
        near_level = tm.level_for_stops(tm.clip_stops - 0.5)
        crush_level = tm.level_for_stops(-6.0) if tone == "slog3" else tm.floor_level + 1
        clipped_pct = counts[tm.clip_level - 1:].sum() * 100.0 / total
        near_pct = counts[near_level:tm.clip_level - 1].sum() * 100.0 / total
        crushed_pct = counts[:crush_level + 1].sum() * 100.0 / total

        # Regions.
        small = cv2.resize(bgr, (WORK_W, WORK_H), interpolation=cv2.INTER_AREA).astype(np.float32)
        small_luma = small @ LUMA_WEIGHTS
        cells = small_luma.reshape(GRID_ROWS, WORK_H // GRID_ROWS, GRID_COLS, WORK_W // GRID_COLS)
        cells = cells.transpose(0, 2, 1, 3).reshape(GRID_ROWS, GRID_COLS, -1)
        cell_median = np.median(cells, axis=2)
        cell_p90 = np.percentile(cells, 90, axis=2)
        region_stops = tm.to_stops(cell_median)
        all_key = float(np.median(region_stops))
        light_source = (region_stops > all_key + 3.0) | (cell_p90 >= tm.clip_level - 1)
        rest = region_stops[~light_source]
        key = float(np.median(rest)) if rest.size >= 6 else all_key

        # Small light sources (practicals, screens) may clip; big bright areas (sky, windows) may not.
        practical = small_clusters(light_source, max_size=4)
        clipped_full = luma >= tm.clip_level - 1
        hh, ww = h - h % GRID_ROWS, w - w % GRID_COLS
        region_clip = clipped_full[:hh, :ww].reshape(GRID_ROWS, hh // GRID_ROWS, GRID_COLS, ww // GRID_COLS).mean(axis=(1, 3))
        clipped_practical = float(region_clip[practical].sum() * 100.0 / region_clip.size)
        cell_p99 = np.percentile(cells, 99, axis=2)
        important = ~practical
        highlight = float(tm.to_stops(cell_p99[important]).max()) if important.any() else float(tm.to_stops(cell_p99).max())

        report = FrameReport(
            width=w, height=h, tone=tone, tone_source=tone_source,
            histogram=counts.reshape(64, 4).sum(axis=1).tolist(),
            clipped_pct=round(float(clipped_pct), 2), near_clip_pct=round(float(near_pct), 2),
            crushed_pct=round(float(crushed_pct), 2), key_stops=round(key, 2),
            region_stops=np.round(region_stops, 2).tolist(),
            light_source_regions=[tuple(map(int, rc)) for rc in np.argwhere(light_source)],
            practical_regions=[tuple(map(int, rc)) for rc in np.argwhere(practical)],
            clipped_practical_pct=round(clipped_practical, 2),
            clipped_important_pct=round(max(0.0, float(clipped_pct) - clipped_practical), 2),
            headroom_stops=round(tm.clip_stops - highlight, 2),
        )
        report.faces = self._faces(bgr, luma, tm)
        report.color = self._color(small, small_luma, tm, ctx, crush_level)
        if compare and self.prev is not None:
            report.change, report.motion = self._compare(small_luma, region_stops, light_source, tm)
        self.prev = {"luma": small_luma, "stops": region_stops, "light": light_source}
        self.frame_count += 1
        report.ms = round((time.perf_counter() - t0) * 1000, 1)
        return report

    def _faces(self, bgr, luma, tm):
        if not self.face_model.exists():
            return []
        if self.frame_count % self.face_every:
            return self.last_faces
        h, w = luma.shape
        det_w = 640
        det_h = int(round(h * det_w / w))
        if self.detector is None:
            self.detector = cv2.FaceDetectorYN.create(str(self.face_model), "", (det_w, det_h), 0.7, 0.3, 50)
        self.detector.setInputSize((det_w, det_h))
        _, found = self.detector.detect(cv2.resize(bgr, (det_w, det_h), interpolation=cv2.INTER_AREA))
        scale = w / det_w
        faces = []
        for f in (found if found is not None else []):
            x, y, fw, fh = (f[:4] * scale).tolist()
            # Measure the middle of the face (skip hair and background at the edges).
            ix0, iy0 = int(max(0, x + 0.2 * fw)), int(max(0, y + 0.2 * fh))
            ix1, iy1 = int(min(w, x + 0.8 * fw)), int(min(h, y + 0.85 * fh))
            patch = luma[iy0:iy1, ix0:ix1]
            if patch.size == 0:
                continue
            level = float(np.median(patch))
            faces.append({"box": [round(x), round(y), round(fw), round(fh)], "score": round(float(f[14]), 2),
                          "level": round(level, 1), "stops": round(float(tm.to_stops(level)), 2),
                          "clipping": bool(np.percentile(patch, 95) >= tm.clip_level - 1),
                          # YuNet's row scaled to this frame (box + 5 landmarks + score), for face signatures
                          "raw": [round(v, 1) for v in (f[:14] * scale).tolist()] + [round(float(f[14]), 3)]})
        faces.sort(key=lambda f: -f["box"][2] * f["box"][3])
        self.last_faces = faces
        return faces

    def _color(self, small, small_luma, tm, ctx, crush_level):
        usable = (small_luma > crush_level) & (small_luma < tm.clip_level - 3)
        if usable.sum() < 200:
            return {"note": "not enough usable pixels for a color estimate"}
        rgb = small[usable][:, ::-1]                    # BGR -> RGB
        lin = tm.to_linear(rgb).astype(np.float64)
        hi, lo = lin.max(axis=1), lin.min(axis=1)
        neutralish = (hi - lo) / (hi + 1e-9) < 0.6
        share_neutral = float(neutralish.mean())
        if neutralish.sum() >= 200:
            lin = lin[neutralish]
        r, g, b = lin.mean(axis=0)                     # "grey world": the average should be neutral
        primaries = PRIMARIES["slog3" if tm.tone == "slog3" else "rec709"]
        xyz = rgb_to_xyz_matrix(primaries, D65) @ np.array([r, g, b])
        x, y = xyz[0] / xyz.sum(), xyz[1] / xyz.sum()
        cct = mccamy_cct(x, y)
        mired_shift = 1e6 / cct - 1e6 / D65_CCT          # + means the picture looks warmer than neutral
        out = {
            "method": "grey world on usable pixels (assumes the scene averages to neutral)",
            "picture_cct_k": int(round(cct)),
            "mired_shift": round(float(mired_shift), 1),
            "warm_cool": "warm" if mired_shift > 15 else "cool" if mired_shift < -15 else "neutral",
            "green_magenta": "green" if g / ((r + b) / 2) > 1.05 else "magenta" if g / ((r + b) / 2) < 0.95 else "neutral",
            "neutral_pixel_share": round(share_neutral, 2),
        }
        if ctx.wb_kelvin:
            out["light_estimate_k"] = int(round(1e6 / (1e6 / ctx.wb_kelvin + mired_shift)))
        else:
            out["light_estimate_k"] = None
            out["why_no_kelvin"] = "camera WB is %s, not a Kelvin value, so only the leftover cast is known" % ctx.wb
        calibrated = "GUESS" not in str(self.calibration.get(tm.tone, {}).get("status", ""))
        out["confidence"] = "low" if share_neutral < 0.5 or not calibrated else "medium"
        return out

    def _compare(self, small_luma, region_stops, light_source, tm):
        prev = self.prev
        delta = region_stops - prev["stops"]
        # How far a region can wobble from noise alone: at least 0.08 st, more in deep
        # shadow where one 8-bit level is a big jump in stops.
        level = np.clip(np.rint(np.median(prev["luma"].reshape(GRID_ROWS, WORK_H // GRID_ROWS, GRID_COLS,
                                                               WORK_W // GRID_COLS), axis=(1, 3))), 0, 254).astype(int)
        tolerance = np.maximum(0.08, 1.5 * (tm.stops_lut[level + 1] - tm.stops_lut[level]))
        steady = ~(light_source | prev["light"])
        if steady.sum() < 6:
            steady = np.ones_like(steady)
        shift, group = biggest_agreeing_group(delta[steady], tolerance[steady])
        local = np.abs(delta - shift) > np.maximum(0.35, 2 * tolerance)
        # Motion: pixels that changed more than the overall brightness change explains.
        diff = small_luma - prev["luma"]
        moved = np.abs(diff - np.median(diff)) > 8
        moved_cells = moved.reshape(GRID_ROWS, WORK_H // GRID_ROWS, GRID_COLS, WORK_W // GRID_COLS).mean(axis=(1, 3))
        change = {"exposure_shift_stops": round(shift, 3),
                  "agreeing_regions": int(group),
                  "changed_regions": [tuple(map(int, rc)) for rc in np.argwhere(local)]}
        motion = {"moving_pct": round(float(moved.mean() * 100), 2),
                  "moving_regions": [tuple(map(int, rc)) for rc in np.argwhere(moved_cells > 0.2)]}
        return change, motion


def report_dict(report):
    return asdict(report)
