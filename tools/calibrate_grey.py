"""Grey card / white paper calibration of the live-view brightness scale. Read-only.

The director changes ISO by hand between captures; this tool only reads.

  capture <dir> <label>   ~2 s of frames: measure the middle of the picture + read ISO/shutter/iris/meter
  black <dir>             same, with the lens cap on (where black sits)
  fit <dir>               work out B (levels per stop), black, A (where 18% grey lands), clip level
  apply <dir>             write the fitted numbers into config/liveview_calibration.json (backup kept)

Why this works with plain white paper: B is the change per stop, which is the same
for any matte surface. A comes from black + B + Sony's published S-Log3 curve,
not from the card's own brightness.
"""
import argparse
import json
import shutil
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.bridge_client import BridgeClient  # noqa: E402
from agent.eyes import LUMA_WEIGHTS  # noqa: E402
from agent.sony_values import describe_value, load_enums  # noqa: E402
from agent.tone import CALIBRATION_FILE, CODE_PER_STOP, load_calibration  # noqa: E402

PATCH = 0.30          # middle 30% of width and height
SECONDS = 2.0


def shutter_seconds(raw):
    num, den = raw >> 16, raw & 0xFFFF
    return num / den if den else None


def measure_patch(bgr):
    h, w = bgr.shape[:2]
    y0, y1 = int(h * (0.5 - PATCH / 2)), int(h * (0.5 + PATCH / 2))
    x0, x1 = int(w * (0.5 - PATCH / 2)), int(w * (0.5 + PATCH / 2))
    patch = bgr[y0:y1, x0:x1].astype(np.float32)
    luma = patch @ LUMA_WEIGHTS
    ph, pw = luma.shape
    sub = [float(np.median(luma[i * ph // 3:(i + 1) * ph // 3, j * pw // 3:(j + 1) * pw // 3]))
           for i in range(3) for j in range(3)]
    return {
        "luma": float(np.median(luma)),
        "rgb": [float(np.median(patch[..., c])) for c in (2, 1, 0)],
        "p99": float(np.percentile(luma, 99)),
        "evenness_levels": round(max(sub) - min(sub), 2),   # big = uneven light or glare
        "texture_levels": round(float(np.std(luma)), 2),    # big = edges/print/texture in the patch
    }


def capture(folder, label):
    client = BridgeClient()
    if not client.status().get("read_only"):
        sys.exit("Refusing to run: start the bridge with --read-only.")
    enums = load_enums()
    props = client.get("IsoSensitivity", "ShutterSpeed", "FNumber", "MeteredManualLevel",
                       "MovieShootingMode", "WhiteBalance", "Colortemp", "RecordingState")
    samples, last, t_end = [], -1, time.monotonic() + SECONDS
    keep = None
    while time.monotonic() < t_end:
        header, jpeg = client.frame(after=last, timeout_ms=1000)
        if jpeg is None:
            continue
        last = header["frame_no"]
        bgr = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        samples.append(measure_patch(bgr))
        keep = bgr
    client.close()
    meter = props["MeteredManualLevel"]["current"]
    meter = meter - (1 << 64) if meter >= 1 << 63 else meter        # it's a signed number
    result = {
        "label": label, "time": datetime.now().isoformat(timespec="seconds"), "frames": len(samples),
        "iso": props["IsoSensitivity"]["current"] & 0xFFFFFF,
        "shutter_s": shutter_seconds(props["ShutterSpeed"]["current"]),
        "f_number": props["FNumber"]["current"] / 100,
        "camera_meter": meter,
        "settings_text": "%s %s %s" % tuple(describe_value(n, props[n]["current"], enums)
                                           for n in ("IsoSensitivity", "ShutterSpeed", "FNumber")),
        "log_mode": describe_value("MovieShootingMode", props["MovieShootingMode"]["current"], enums),
        "white_balance": describe_value("WhiteBalance", props["WhiteBalance"]["current"], enums),
        "wb_kelvin": props["Colortemp"]["current"] if "Colortemp" in props else None,
        "recording": props["RecordingState"]["current"] != 0,
        "patch_luma": round(statistics.median(s["luma"] for s in samples), 2),
        "patch_rgb": [round(statistics.median(s["rgb"][c] for s in samples), 1) for c in range(3)],
        "patch_p99": round(statistics.median(s["p99"] for s in samples), 1),
        "evenness_levels": statistics.median(s["evenness_levels"] for s in samples),
        "texture_levels": statistics.median(s["texture_levels"] for s in samples),
        "frame_to_frame_spread": round(max(s["luma"] for s in samples) - min(s["luma"] for s in samples), 2),
    }
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(folder / ("%s.jpg" % label)), keep)
    with (folder / "captures.jsonl").open("a") as f:
        f.write(json.dumps(result) + "\n")
    warnings = []
    if result["evenness_levels"] > 4:
        warnings.append("light looks uneven across the card/paper (or glare): %.1f levels" % result["evenness_levels"])
    if result["texture_levels"] > 6:
        warnings.append("the middle of the picture isn't plain (edges, print or texture)")
    if result["recording"]:
        warnings.append("camera is RECORDING")
    print(json.dumps(result))
    for w in warnings:
        print("WARNING:", w)
    return result


def fit(folder, exclude=()):
    rows = [json.loads(line) for line in (Path(folder) / "captures.jsonl").read_text().splitlines()]
    rows = [r for r in rows if r["label"] not in exclude]
    black = [r for r in rows if r["label"].startswith("black")]
    lit = [r for r in rows if not r["label"].startswith("black")]
    if len(lit) < 2:
        sys.exit("Need at least two lit captures at different exposures.")
    ref = lit[0]
    for r in lit:
        r["ev"] = (np.log2(r["iso"] / ref["iso"]) + np.log2(r["shutter_s"] / ref["shutter_s"])
                   - 2 * np.log2(r["f_number"] / ref["f_number"]))
    # Clip: a clipped capture is perfectly flat (no texture, no unevenness), or stops rising.
    lit.sort(key=lambda r: r["ev"])
    flat = [r for r in lit if r["evenness_levels"] <= 0.5 and r["texture_levels"] <= 3
            and r["patch_p99"] - r["patch_luma"] <= 3]
    clip_level = round(statistics.median(r["patch_luma"] for r in flat)) if flat else None
    for a, b in zip(lit, lit[1:]):
        if clip_level is None and b["ev"] - a["ev"] >= 0.9 and b["patch_luma"] - a["patch_luma"] < 3:
            clip_level = round(max(a["patch_luma"], b["patch_luma"]))
    usable = [r for r in lit if r not in flat and 25 < r["patch_luma"] < (clip_level - 8 if clip_level else 212)]
    if len(usable) < 2:
        sys.exit("Need at least two captures between shadows and clipping.")
    ev = np.array([r["ev"] for r in usable])
    lv = np.array([r["patch_luma"] for r in usable])
    slope, intercept = np.polyfit(ev, lv, 1)
    residuals = (lv - (slope * ev + intercept)).round(2).tolist()
    result = {"levels_per_stop": round(float(slope), 2), "points_used": len(usable),
              "points": [(r["label"], round(float(r["ev"]), 2), r["patch_luma"]) for r in usable],
              "residuals_levels": residuals, "clip_level": clip_level,
              "excluded": list(exclude), "clipped_captures": [r["label"] for r in flat]}
    meters = [(r["ev"], r["camera_meter"]) for r in usable if -4000 < r["camera_meter"] < 4000 and r["camera_meter"] != 0]
    if len(meters) >= 2:
        m_slope = np.polyfit([m[0] for m in meters], [m[1] for m in meters], 1)[0]
        result["camera_meter_units_per_stop"] = round(float(m_slope), 1)
    if black:
        black_level = statistics.median(r["patch_luma"] for r in black)
        alpha = slope / CODE_PER_STOP                 # 8-bit levels per S-Log3 code value
        beta = black_level - alpha * 95.0             # S-Log3 black = code 95
        result.update({"floor_level": round(black_level, 1),
                       "grey_level": round(alpha * 420.0 + beta, 1),
                       "code_to_8bit": {"alpha": round(float(alpha), 4), "beta": round(float(beta), 2)}})
        guess = load_calibration()["slog3"]
        result["compare_with_guess"] = {"grey_level": guess["grey_level"], "levels_per_stop": guess["levels_per_stop"]}
    (Path(folder) / "fit.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))
    return result


def apply(folder):
    result = json.loads((Path(folder) / "fit.json").read_text())
    cal = load_calibration()
    backup = CALIBRATION_FILE.with_suffix(".before-%s.json" % datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy(CALIBRATION_FILE, backup)
    s = cal["slog3"]
    stamp = "MEASURED (calibrate_grey.py, %s)" % Path(folder).name.split("_", 2)[-1]
    for key in ("grey_level", "levels_per_stop", "clip_level", "floor_level"):
        if result.get(key) is not None:
            s[key] = result[key]
            s["status"][key] = stamp
    CALIBRATION_FILE.write_text(json.dumps(cal, indent=2) + "\n")
    print("Updated", CALIBRATION_FILE, "(backup:", backup.name + ")")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["capture", "black", "fit", "apply"])
    ap.add_argument("folder")
    ap.add_argument("label", nargs="?")
    ap.add_argument("--exclude", nargs="*", default=[])
    a = ap.parse_args()
    if a.action == "capture":
        capture(a.folder, a.label or "lit")
    elif a.action == "black":
        capture(a.folder, "black")
    elif a.action == "fit":
        fit(a.folder, a.exclude)
    else:
        apply(a.folder)


if __name__ == "__main__":
    main()
