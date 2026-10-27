"""The dashboard: a small web server that shows the runner and lets the operator steer it.

Python's standard library only, so it runs the same on the Pi. Listens on 127.0.0.1
(this computer only) unless told otherwise.

  GET  /                     the page (files in dashboard/)
  GET  /api/state            everything on screen, as JSON (the page asks 4 times a second)
  GET  /api/frame.jpg        next live-view frame: ?mode=clean|zebras|false_color&after=<frame no>
  POST /api/kill             kill switch (no body)
  POST /api/auto  {"on": true|false}      POST /api/lock {"on": true|false}
  POST /api/look  {"key": "interview"}    POST /api/face {"name": "Saad"}   POST /api/forget {"id": "..."}
  POST /api/mark  {"label": "light change"}   (Step 7: marks a scene event)
  POST /api/problem {"note": "..."}           (logs a problem right now, with what the agent saw)

Every POST must carry the header "X-Camera-Agent: 1". A browser won't add a custom header
for another website without asking this server first (and it never says yes), so a random
web page can't press the buttons. The Host header is checked too, against DNS tricks.

With a PIN (on the Pi, where the phone reaches it over Wi-Fi; see agent/pin.py):
  POST /api/pair {"pin": "123456"}   pairs this phone (a cookie). Until then the page is the PIN screen,
                                     and /api/* answers 401, except the kill switch, which always works.
Without a PIN (the Mac), nothing changes.

On the Pi (tools/pi_agent.py) the runner changes when the phone arms or disarms: `actions` adds those buttons,
`extra_state` adds the Pi's own state to /api/state as "pi", and between runners /api/state answers 503.
"""
import json
import threading
from http.cookies import CookieError, SimpleCookie
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import cv2

from agent.overlay import false_color, zebras

ROOT = Path(__file__).resolve().parent.parent
PAGE_DIR = ROOT / "dashboard"
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".png": "image/png", ".woff2": "font/woff2", ".svg": "image/svg+xml", ".txt": "text/plain; charset=utf-8"}
MODES = ("clean", "zebras", "false_color")
COOKIE = "ca_pair"


class Dashboard:
    def __init__(self, runner, host="127.0.0.1", port=8770, guard=None, names=(), actions=None, extra_state=None):
        self.runner, self.host, self.port = runner, host, port
        self.actions, self.extra_state = dict(actions or {}), extra_state
        self.on_seen = None                  # the Pi: called on every request from a paired phone (its heartbeat)
        self.guard = guard if guard is not None and guard.enabled else None   # agent.pin.PinGuard, or no PIN
        self.cache = {}                      # mode -> (frame_no, jpeg bytes), shared by every viewer
        self.cache_lock = threading.Lock()
        handler = type("Handler", (_Handler,), {"dash": self})
        self.server = ThreadingHTTPServer((host, port), handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]            # port 0 = any free port (tests)
        self.allowed_hosts = {"%s:%d" % (h, self.port) for h in ("127.0.0.1", "localhost", host, *names)}

    def start(self):
        self.started = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def stop(self):
        if getattr(self, "started", False):          # shutdown() waits for serve_forever, so only if it ran
            self.server.shutdown()
        self.server.server_close()

    @property
    def url(self):
        return "http://%s:%d/" % ("127.0.0.1" if self.host in ("0.0.0.0", "") else self.host, self.port)

    def frame(self, mode, after, timeout=1.0):
        """The next frame newer than `after`, drawn in `mode`. Returns (frame_no, jpeg) or (None, None)."""
        r = self.runner
        if r is None:                               # between runners on the Pi
            return None, None
        deadline = time.monotonic() + timeout
        while r.frame_no <= after and time.monotonic() < deadline and not r.killed:
            time.sleep(0.01)
        with r.lock:
            no, jpeg, bgr, report = r.frame_no, r.jpeg, r.bgr, r.report
        if jpeg is None:
            return None, None
        if mode == "clean":
            return no, jpeg
        with self.cache_lock:
            if self.cache.get(mode, (None,))[0] == no:
                return self.cache[mode]
        tm = r.eyes.tone_model(report.tone)
        img = zebras(bgr, tm) if mode == "zebras" else false_color(bgr, tm)
        out = (no, cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 82])[1].tobytes())
        with self.cache_lock:
            self.cache[mode] = out
        return out

    def control(self, action, body):
        r = self.runner
        if action in self.actions:
            return self.actions[action](body)
        if r is None:
            return 503, {"ok": False, "error": "the agent is starting: try again in a moment"}
        if action == "kill":
            r.kill("Kill switch (dashboard)")
        elif action == "auto":
            if body.get("on") and not r.live:
                return 409, {"ok": False, "error": "Dry run: start with --live to let the agent change settings"}
            r.set_auto(bool(body.get("on")))
        elif action == "lock":
            r.hold(bool(body.get("on")))
        elif action == "look":
            if body.get("key") not in ("cinematic", "run_and_gun", "interview", "low_light", "photo_portrait"):
                return 400, {"ok": False, "error": "unknown look"}
            r.set_look(body["key"])
        elif action == "face":
            try:
                person = r.remember_face((body.get("name") or "").strip()[:40] or None)
            except Exception as e:
                return 409, {"ok": False, "error": str(e)}
            return 200, {"ok": True, "person": {k: person[k] for k in ("id", "name", "target")}}
        elif action == "mark":
            r.mark(str(body.get("label") or "light change")[:40])
        elif action == "problem":
            r.problem(str(body.get("note") or "")[:300])
        elif action == "forget":
            r.forget_face(str(body.get("id", "")))
        else:
            return 404, {"ok": False, "error": "unknown action"}
        return 200, {"ok": True}


class _Handler(BaseHTTPRequestHandler):
    dash = None
    server_version = "camera-agent"

    def log_message(self, *args):          # quiet: the runner has its own log
        pass

    def _send(self, code, body, ctype="application/json", extra=()):
        data = body if isinstance(body, bytes) else json.dumps(body, default=float).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _paired(self):
        if self.dash.guard is None:
            return True
        try:
            morsel = SimpleCookie(self.headers.get("Cookie", "")).get(COOKIE)
        except CookieError:
            return False
        return self.dash.guard.is_paired(morsel.value if morsel else "")

    def _host_ok(self):
        if self.dash.host in ("0.0.0.0", ""):   # opened up on purpose (Pi + phone); see docs
            return True
        return self.headers.get("Host", "") in self.dash.allowed_hosts

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"ok": False, "error": "wrong host"})
        url = urlparse(self.path)
        if not self._paired():
            if url.path.startswith("/api/"):
                return self._send(401, {"ok": False, "error": "pair this phone first"})
            if url.path in ("/", "/index.html"):
                url = url._replace(path="/pair.html")
        elif url.path.startswith("/api/") and self.dash.on_seen:
            self.dash.on_seen()
        if url.path == "/api/state":
            extra = self.dash.extra_state() if self.dash.extra_state else None
            r = self.dash.runner
            if r is None or not hasattr(r, "t0"):
                body = {"ok": False, "error": (extra or {}).get("message") or "the agent is starting"}
                return self._send(503, dict(body, pi=extra) if extra else body)
            snap = r.snapshot()
            if extra:
                snap["pi"] = extra
            return self._send(200, snap)
        if url.path == "/api/frame.jpg":
            if self.dash.runner is None:
                return self._send(503, {"ok": False, "error": "no live view yet"})
            q = parse_qs(url.query)
            mode = q.get("mode", ["clean"])[0]
            try:
                after = int(q.get("after", ["-1"])[0])
            except ValueError:
                after = -1
            no, jpeg = self.dash.frame(mode if mode in MODES else "clean", after)
            if jpeg is None:
                return self._send(503, {"ok": False, "error": "no live view yet"})
            return self._send(200, jpeg, "image/jpeg", [("X-Frame-No", str(no))])
        path = (PAGE_DIR / (url.path.lstrip("/") or "index.html")).resolve()
        if PAGE_DIR.resolve() not in path.parents or not path.is_file() or path.suffix not in TYPES:
            return self._send(404, {"ok": False, "error": "not found"})
        return self._send(200, path.read_bytes(), TYPES[path.suffix])

    def do_POST(self):
        if not self._host_ok() or self.headers.get("X-Camera-Agent") != "1":
            return self._send(403, {"ok": False, "error": "refused"})
        url = urlparse(self.path)
        if not url.path.startswith("/api/"):
            return self._send(404, {"ok": False, "error": "not found"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(min(length, 10000)) or b"{}") if length else {}
        except (ValueError, json.JSONDecodeError):
            return self._send(400, {"ok": False, "error": "bad request"})
        action, body = url.path[len("/api/"):], body if isinstance(body, dict) else {}
        if action == "pair":
            if self.dash.guard is None:
                return self._send(404, {"ok": False, "error": "no PIN on this dashboard"})
            token, error = self.dash.guard.pair(str(body.get("pin") or ""))
            if not token:
                return self._send(403, {"ok": False, "error": error})
            cookie = "%s=%s; Path=/; Max-Age=31536000; HttpOnly; SameSite=Strict" % (COOKIE, token)
            return self._send(200, {"ok": True}, extra=[("Set-Cookie", cookie)])
        if action != "kill" and not self._paired():          # the kill switch works for anyone on the network
            return self._send(401, {"ok": False, "error": "pair this phone first"})
        if self.dash.on_seen and self._paired():
            self.dash.on_seen()
        code, reply = self.dash.control(action, body)
        return self._send(code, reply)
