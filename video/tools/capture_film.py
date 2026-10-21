"""Render the film's 3D shots with the website's own camera (site/js/camera3d.js), one frame at a time.

The moves are scripted on the film's timeline in video/tools/capture.html (shots: viewfinder, inside, kill, snap;
the viewfinder is the site's simulator rather than the 3D camera). Each shot is
rendered in a fresh page at 3840x2160, 30 fps, and encoded to video/film/assets/3d/<shot>.mp4 (not in git).
Everything here is an illustration: the composition tags it so.

Needs ffmpeg and Playwright's Chrome. Serves the repo itself on 127.0.0.1 (port 8791) while it runs.
Usage:
    python video/tools/capture_film.py                 # all shots
    python video/tools/capture_film.py inside --frames 10 --out /tmp/x.mp4     # a quick test
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
OUT = ROOT / "video" / "film" / "assets" / "3d"
PORT, FPS, SCALE = 8791, 30, 2


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def capture(browser, name, frames=None, out=None):
    page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=SCALE)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:%d/video/tools/capture.html" % PORT, wait_until="load")
    page.wait_for_function("window.ready === true", timeout=30000)
    vf = name == "viewfinder"                      # the simulator's picture, not the 3D camera
    if vf:
        page.evaluate("() => window.setupVF()")
        span = {"from": 0, "to": 7.4}
    else:
        page.evaluate("(s) => window.setup(s)", SCALE)
        span = page.evaluate("([n, f]) => window.begin(n, f)", [name, FPS])
    n = frames or round((span["to"] - span["from"]) * FPS)
    out = Path(out) if out else OUT / (name + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
                            "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                            str(out)], stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(n):
        data = page.evaluate("([i, f]) => window.%s(i, f, 0.94)" % ("vfFrame" if vf else "frame"), [i, FPS])
        enc.stdin.write(base64.b64decode(data.split(",", 1)[1]))
        if i % 60 == 0:
            print("  %s: frame %d/%d (%.2f s/frame)" % (name, i, n, (time.time() - t0) / (i + 1)), flush=True)
    enc.stdin.close(); enc.wait()
    page.close()
    if errors:
        raise SystemExit("page errors in %s: %s" % (name, errors[:3]))
    print("wrote %s: %d frames from film time %.1f s, %.1f s to render" % (out.relative_to(ROOT) if out.is_relative_to(ROOT) else out,
                                                                          n, span["from"], time.time() - t0))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shots", nargs="*", default=["viewfinder", "inside", "kill", "snap"])
    ap.add_argument("--frames", type=int, help="render only this many frames (a test)")
    ap.add_argument("--out", help="output file (one shot only)")
    args = ap.parse_args()
    httpd = serve()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", args=["--ignore-gpu-blocklist", "--enable-gpu-rasterization"])
            for name in args.shots:
                capture(browser, name, args.frames, args.out)
            browser.close()
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main()
