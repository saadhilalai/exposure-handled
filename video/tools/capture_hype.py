"""Render the hype cut's 3D shots with the website's own camera (site/js/camera3d.js), one frame at a time.

The moves are keyed in beats of the music in video/tools/capture_hype.html (shots: orbit, lens, dive, decide, swarm,
kill, slam, vf), so pass the track's tempo. Each frame averages a few sub-frames over a 180° shutter (motion blur).
Output: video/hype/assets/3d/<shot>.mp4 (not in git), 30 fps. Everything here is an illustration: the cut tags it so.

Needs ffmpeg and Playwright's Chrome. Serves the repo itself on 127.0.0.1 (port 8792) while it runs.
Usage:
    python video/tools/capture_hype.py --bpm 128                      # all shots, 1920x1080 (the draft)
    python video/tools/capture_hype.py --bpm 128 --scale 2 --sub 6    # 3840x2160, smoother blur (the final)
    python video/tools/capture_hype.py dive --bpm 128 --stills 0,4,8  # a few frames as JPEGs, to check framing
"""
import argparse
import base64
import functools
import http.server
import subprocess
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "video" / "hype" / "assets" / "3d"
PORT, FPS = 8792, 30
ALL = ["orbit", "lens", "dive", "decide", "swarm", "kill", "slam", "vf"]


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def capture(browser, name, a):
    page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=a.scale)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    url = "http://127.0.0.1:%d/video/tools/capture_hype.html" % PORT
    for attempt in range(3):                       # a cold Chrome sometimes stalls on the first load: try again
        page.goto(url, wait_until="load")
        try:
            page.wait_for_function("window.ready === true", timeout=30000)
            break
        except Exception:
            if attempt == 2:
                raise
            print("  %s: page not ready, reloading" % name, flush=True)
    size = page.evaluate("([s, b]) => window.setup(s, b)", [a.scale, a.bpm])
    span = page.evaluate("([n, f]) => window.begin(n, f)", [name, FPS])
    n = round(span["seconds"] * FPS)
    t0 = time.time()
    if a.stills is not None:                       # a few beats as JPEGs (frames are rendered in order up to the last)
        want = {round(float(b) * span["seconds"] / span["beats"] * FPS): b for b in a.stills.split(",")}
        a_out = Path(a.out or OUT / "stills"); a_out.mkdir(parents=True, exist_ok=True)
        for i in range(max(want) + 1):
            data = page.evaluate("([i, f, s]) => window.frame(i, f, 0.9, s)", [i, FPS, 1 if i not in want else a.sub])
            if i in want:
                (a_out / ("%s_b%s.jpg" % (name, want[i]))).write_bytes(base64.b64decode(data.split(",", 1)[1]))
        print("  %s: stills at beats %s -> %s (%.1f s)" % (name, a.stills, a_out, time.time() - t0))
    else:
        out = Path(a.out) if a.out else OUT / (name + ".mp4")
        out.parent.mkdir(parents=True, exist_ok=True)
        enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
                                "-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                                str(out)], stdin=subprocess.PIPE)
        for i in range(n):
            data = page.evaluate("([i, f, s]) => window.frame(i, f, 0.94, s)", [i, FPS, a.sub])
            enc.stdin.write(base64.b64decode(data.split(",", 1)[1]))
            if i % 60 == 0:
                print("  %s: frame %d/%d (%.2f s/frame)" % (name, i, n, (time.time() - t0) / (i + 1)), flush=True)
        enc.stdin.close(); enc.wait()
        print("wrote %s: %d frames, %dx%d, %.1f s to render" % (out.relative_to(ROOT) if out.is_relative_to(ROOT) else out,
                                                                n, size["w"], size["h"], time.time() - t0), flush=True)
    page.close()
    if errors:
        raise SystemExit("page errors in %s: %s" % (name, errors[:3]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shots", nargs="*", default=ALL)
    ap.add_argument("--bpm", type=float, required=True, help="the music's tempo: every move is keyed in beats")
    ap.add_argument("--scale", type=int, default=1, help="1 = 1920x1080, 2 = 3840x2160")
    ap.add_argument("--sub", type=int, default=4, help="sub-frames averaged per frame (motion blur)")
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--stills", help="comma-separated beats: save just those frames as JPEGs")
    ap.add_argument("--out", help="output file (one shot) or folder (--stills)")
    a = ap.parse_args()
    httpd = serve()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", args=["--ignore-gpu-blocklist", "--enable-gpu-rasterization"])
            for name in a.shots:
                capture(browser, name, a)
            browser.close()
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main()
