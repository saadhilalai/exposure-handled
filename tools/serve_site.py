"""Preview the project website (site/). Nothing is published.

Like `python -m http.server`, plus byte ranges, which browsers need to stream and loop the clips.
Port 8780 by default (8765 is robot-walker's server, 8770 is the dashboard's).

Usage:
  python tools/serve_site.py [--port 8780]   this Mac only: open http://127.0.0.1:8780/
  python tools/serve_site.py --share         a temporary private link for testing on a phone (like the rating
                                             page): a Cloudflare quick tunnel to a secret path. Ctrl-C or `kill`
                                             takes it offline, and the link dies with it.
"""
import argparse
import functools
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"
CHUNK = 256 * 1024
TUNNEL_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
DNS_HEAD_START_S = 20     # a new address needs ~10 s to reach public DNS; asking sooner gets "not found" cached here


class Handler(SimpleHTTPRequestHandler):
    prefix = None          # share mode: only /p/<secret>/... answers; everything else is "not found"

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")          # a draft: always show the latest edit
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("X-Robots-Tag", "noindex, nofollow")  # a draft: never in search, even if a link leaks
        self.send_header("Referrer-Policy", "no-referrer")     # links out (GitHub, LinkedIn) never carry the secret
        super().end_headers()

    def list_directory(self, path):
        self.send_error(404)                                    # no folder listings

    def gate(self):
        """Share mode: strip the secret prefix, or answer 404. Returns False when it has answered."""
        if not self.prefix:
            return True
        if self.path.split("?")[0] == self.prefix:
            self.send_response(301); self.send_header("Location", self.prefix + "/"); self.end_headers()
            return False
        if not self.path.startswith(self.prefix + "/"):
            self.send_error(404)
            return False
        self.path = self.path[len(self.prefix):]
        return True

    def do_HEAD(self):
        if self.gate():
            super().do_HEAD()

    def do_GET(self):
        if not self.gate():
            return
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


def reachable(url, tries=24, every=5.0):
    """Does the public address answer yet? (Up to about 2 minutes.)"""
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=8) as r:
                if r.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(every)
    return False


def share():
    """A temporary private link: this Mac serves the site under a secret path, through a Cloudflare quick tunnel."""
    exe = shutil.which("cloudflared")
    if not exe:
        sys.exit("cloudflared isn't installed. Install it with: brew install cloudflared")
    def stop(*_):
        raise KeyboardInterrupt
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):    # the tunnel must never outlive this program
        signal.signal(sig, stop)
    Handler.prefix = "/p/" + secrets.token_hex(8)
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(SITE)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    local = "http://127.0.0.1:%d" % server.server_address[1]
    # http2 runs over TCP, which school Wi-Fi and phone hotspots let through; the default (QUIC, UDP) is often blocked
    tunnel = subprocess.Popen([exe, "tunnel", "--no-autoupdate", "--protocol", "http2", "--url", local],
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    awake = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())]) if shutil.which("caffeinate") else None
    try:
        base = None
        for line in tunnel.stderr:                # cloudflared prints the address it was given
            m = TUNNEL_URL.search(line)
            if m:
                base = m.group(0)
                break
        if not base:
            print("The tunnel didn't start (no internet?). Nothing is online.", flush=True)
            return
        threading.Thread(target=lambda: [None for _ in tunnel.stderr], daemon=True).start()   # keep the pipe drained
        link = base + Handler.prefix + "/"
        print("Got %s. Giving it %d s to reach the internet's address books, then checking it..." % (base, DNS_HEAD_START_S), flush=True)
        time.sleep(DNS_HEAD_START_S)
        works = reachable(link)
        print("Checked over the internet: it works." if works else
              "Couldn't confirm it from this Mac yet (its DNS can lag a minute or two). Try it on the phone on mobile data.", flush=True)
        print("PRIVATE LINK: %s\n(from this Mac: %s%s/). Ctrl-C or kill takes it offline." % (link, local, Handler.prefix), flush=True)
        tunnel.wait()
        print("The tunnel stopped, so the link no longer works. Run --share again for a new one.", flush=True)
    except KeyboardInterrupt:
        print("\nOffline.", flush=True)
    finally:
        tunnel.terminate()
        try:
            tunnel.wait(timeout=10)
        except subprocess.TimeoutExpired:
            tunnel.kill()
        server.shutdown()
        server.server_close()
        if awake:
            awake.terminate()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8780)
    ap.add_argument("--share", action="store_true", help="a temporary private link through a Cloudflare tunnel")
    args = ap.parse_args()
    ThreadingHTTPServer.request_queue_size = 128   # the page asks for many files at once; the default 5 drops some
    if args.share:
        return share()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), functools.partial(Handler, directory=str(SITE)))
    print("Site preview: http://127.0.0.1:%d/  (Ctrl-C to stop)" % args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
