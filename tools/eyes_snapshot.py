"""Run the eyes on live view (or saved frames) and save overlay screenshots.

Live mode only works with a bridge started --read-only (this tool never changes the camera).

Usage:
  python tools/eyes_snapshot.py <out_dir> --live [--seconds 8]
  python tools/eyes_snapshot.py <out_dir> --files a.jpg b.jpg ...
Writes clean / zebras / false_color / faces / regions / assist screenshots,
an overview contact sheet, and report.json.
"""
import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.eyes import CameraContext, Eyes, context_from_settings  # noqa: E402
from agent.overlay import render  # noqa: E402
from agent.sony_values import load_enums  # noqa: E402

MODES = ["clean", "zebras", "false_color", "faces", "regions", "assist"]
TITLES = {"clean": "Live view (as received)", "zebras": "Zebras", "false_color": "False color",
          "faces": "Face boxes", "regions": "Regions (light sources / changed)", "assist": "All together"}


def contact_sheet(images):
    tiles = []
    for mode in MODES:
        tile = cv2.resize(images[mode], (512, 288), interpolation=cv2.INTER_AREA)
        cv2.rectangle(tile, (0, 264), (512, 288), (0, 0, 0), -1)
        cv2.putText(tile, TITLES[mode], (8, 281), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(tile)
    return np.vstack([np.hstack(tiles[0:3]), np.hstack(tiles[3:6])])


def save_all(out, bgr, report, ctx, eyes, extra):
    tm = eyes.tone_model(report.tone)
    images = {m: render(bgr, report, ctx, tm, m, extra) for m in MODES}
    for m, img in images.items():
        cv2.imwrite(str(out / ("%s.jpg" % m)), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    cv2.imwrite(str(out / "overview.jpg"), contact_sheet(images), [cv2.IMWRITE_JPEG_QUALITY, 90])


def run_live(out, seconds):
    from agent.bridge_client import BridgeClient
    client = BridgeClient()
    status = client.status()
    if not status.get("read_only"):
        sys.exit("Refusing to run: the bridge is not in read-only mode (start it with --read-only).")
    enums = load_enums()
    props = client.settings()
    ctx = context_from_settings(props, enums)
    eyes = Eyes()
    last, frames, analysis_ms, kept = -1, 0, [], None
    t_start = time.monotonic()
    while time.monotonic() - t_start < seconds:
        header, jpeg = client.frame(after=last, timeout_ms=1000)
        if jpeg is None:
            continue
        last = header["frame_no"]
        bgr = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        report = eyes.analyze(bgr, ctx)
        frames += 1
        analysis_ms.append(report.ms)
        # Keep the frame with the most faces (latest wins), for the screenshots.
        if kept is None or len(report.faces) >= len(kept[1].faces):
            kept = (bgr, report)
    elapsed = time.monotonic() - t_start
    end_status = client.status()
    client.close()
    stats = {"frames_analyzed": frames, "fps": round(frames / elapsed, 1),
             "analysis_ms_median": round(statistics.median(analysis_ms), 1) if analysis_ms else None,
             "analysis_ms_max": round(max(analysis_ms), 1) if analysis_ms else None,
             "bridge_read_only_start_end": [status["read_only"], end_status["read_only"]]}
    return ctx, eyes, kept, stats


def run_files(paths):
    ctx = CameraContext(tone="unknown", tone_source="from picture only (no camera settings)")
    eyes, kept = Eyes(), None
    for p in paths:
        bgr = cv2.imread(str(p))
        kept = (bgr, eyes.analyze(bgr, ctx))
    return ctx, eyes, kept, {"frames_analyzed": len(paths)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--seconds", type=float, default=8)
    ap.add_argument("--files", nargs="*")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    ctx, eyes, (bgr, report), stats = run_live(out, args.seconds) if args.live else run_files(args.files)
    extra = ["Eyes: %s fps, %s ms/frame" % (stats["fps"], stats["analysis_ms_median"])] if "fps" in stats else []
    save_all(out, bgr, report, ctx, eyes, extra)
    (out / "report.json").write_text(json.dumps({"context": asdict(ctx), "stats": stats, "report": asdict(report)}, indent=1))
    print(json.dumps({"context": asdict(ctx), "stats": stats}, indent=1))
    summary = {k: getattr(report, k) for k in ("tone", "key_stops", "clipped_pct", "near_clip_pct", "crushed_pct",
                                              "light_source_regions", "faces", "color", "change", "motion", "ms")}
    for k, v in summary.items():
        print("  %-22s %s" % (k, json.dumps(v, default=str)))
    print("Saved screenshots in", out)


if __name__ == "__main__":
    main()
