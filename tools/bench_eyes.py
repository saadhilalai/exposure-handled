"""How fast are the eyes on this computer? Uses saved frames only (no camera).

Run it on the Mac and later on the Pi 5 to compare like for like.
Usage: python tools/bench_eyes.py <folder of .jpg frames> [--threads 1]
"""
import argparse
import glob
import platform
import statistics
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.eyes import CameraContext, Eyes  # noqa: E402


def median_ms(fn, n):
    times = []
    for i in range(n):
        t = time.perf_counter()
        fn(i)
        times.append((time.perf_counter() - t) * 1000)
    return statistics.median(times)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--threads", type=int, default=1)
    args = ap.parse_args()
    cv2.setNumThreads(args.threads)
    files = sorted(glob.glob(str(Path(args.folder) / "*.jpg")))[:60]
    if not files:
        sys.exit("no .jpg frames in " + args.folder)
    jpegs = [Path(f).read_bytes() for f in files]
    frames = [cv2.imdecode(np.frombuffer(j, np.uint8), cv2.IMREAD_COLOR) for j in jpegs]
    n = len(frames)
    ctx = CameraContext(tone="slog3", tone_source="bench")
    decode = median_ms(lambda i: cv2.imdecode(np.frombuffer(jpegs[i], np.uint8), cv2.IMREAD_COLOR), n)
    no_faces = Eyes(face_model="none")
    eyes = median_ms(lambda i: no_faces.analyze(frames[i], ctx), n)
    every = Eyes(face_every=1)
    with_faces = median_ms(lambda i: every.analyze(frames[i], ctx), n)
    face = with_faces - eyes
    average = decode + eyes + face / 3          # default: faces every 3rd frame
    print("machine: %s %s, OpenCV threads: %d, frames: %d" % (platform.machine(), platform.processor() or "", args.threads, n))
    print("JPEG decode %.1f ms | eyes without faces %.1f ms | one face detection %.1f ms" % (decode, eyes, face))
    print("average per frame (faces every 3rd frame): %.1f ms -> up to %.0f fps (live view is 24 fps = 41.7 ms budget)"
          % (average, 1000 / average))


if __name__ == "__main__":
    main()
