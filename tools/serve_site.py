"""Preview the project website (site/) on this Mac only. Nothing is published.

Like `python -m http.server`, plus byte ranges, which browsers need to stream and loop the clips.
Port 8780 by default (8765 is robot-walker's server, 8770 is the dashboard's).

Usage: python tools/serve_site.py [--port 8780]   then open http://127.0.0.1:8780/
"""
import argparse
import functools
import os
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"
CHUNK = 256 * 1024


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")          # a draft: always show the latest edit
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def do_GET(self):
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        path = self.translate_path(self.path)
        if not m or not os.path.isfile(path):
            return super().do_GET()
        size = os.path.getsize(path)
        start = int(m[1]) if m[1] else max(0, size - int(m[2] or 0))
        end = min(int(m[2]), size - 1) if m[1] and m[2] else size - 1
        if start >= size or start > end:
            self.send_response(416)
            self.send_header("Content-Range", "bytes */%d" % size)
            self.end_headers()
            return
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        try:
            with open(path, "rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = f.read(min(CHUNK, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass                                                 # the browser moved on; that's normal for video

    def log_message(self, *args):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8780)
    args = ap.parse_args()
    ThreadingHTTPServer.request_queue_size = 128   # the page asks for many files at once; the default 5 drops some
    server = ThreadingHTTPServer(("127.0.0.1", args.port), functools.partial(Handler, directory=str(SITE)))
    print("Site preview: http://127.0.0.1:%d/  (Ctrl-C to stop)" % args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
