"""Step 7 blind test: the private rating page, and the counting the plan froze.

Anonymous by design: each rater gets a link with a random code; no names or emails are
asked for or stored, and nothing records who got which link. Every rater sees the scenes
in their own random order with their own random A/B/C labels; the clips are served under
neutral addresses, so the page never knows which method made which clip. Answers are saved
in sessions/step7-blind/ (never in the repo).

  python tools/rater_server.py prepare clips.json      copy the 21 exported clips in under random names
  python tools/rater_server.py links 15                 make 15 anonymous links
  python tools/rater_server.py share                    put it online (HTTPS) and print the links to send
  python tools/rater_server.py serve [--host 0.0.0.0]   or: this Mac only / the same Wi-Fi only
  python tools/rater_server.py results                  count it: only raters who finished every scene

Online (director: "host it online so friends can rate from anywhere"): `share` runs
the page on this Mac and opens a temporary Cloudflare tunnel (cloudflared, no account) to it.
The address is a random https://....trycloudflare.com and lasts as long as `share` runs, so
keep it running, and the Mac awake, until the ratings are in. The page stays the only way in:
no file list, unknown codes get "not found", nothing is cached on the way.

clips.json: {"sets": [{"id": "S1_A", "clips": {"agent": "path.mp4", "fx2auto": "...", "manual": "..."}}, ...]}
"""
import argparse
import json
import os
import random
import re
import secrets
import shutil
import signal
import statistics
import subprocess
import sys
import threading
import time
import urllib.request
from collections import Counter
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "sessions" / "step7-blind"
PAGE = ROOT / "rater"
SHARED = ROOT / "dashboard"                 # fonts and the S4D mark
LABELS = ["A", "B", "C"]
METHODS = ["agent", "fx2auto", "manual"]
TOKEN = re.compile(r"[a-z0-9]{10}")
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".png": "image/png", ".woff2": "font/woff2"}
MAX_ANSWERS_PER_RATER = 60               # 7 scenes, changed a few times at most; more is someone playing with it
CHUNK = 256 * 1024                       # clips are streamed, never read into memory whole
CSP = ("default-src 'self'; media-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
       "form-action 'none'")
TUNNEL_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
DNS_HEAD_START_S = 20     # a new address needs ~10 s to reach public DNS; asking sooner gets "not found" cached here
COUNT_RULE = "only raters who finished every scene count (director, decided before any ratings)"


class Study:
    def __init__(self, data=DATA):
        self.data = Path(data)
        self.manifest = json.loads((self.data / "manifest.json").read_text())
        self.sets = {s["id"]: s for s in self.manifest["sets"]}
        self.public = {s["public"]: s["id"] for s in self.manifest["sets"]}     # the page only sees random codes
        raters = self.data / "raters.json"
        self.tokens = set(json.loads(raters.read_text())["tokens"]) if raters.exists() else set()
        self.lock = threading.Lock()
        answers = self.data / "answers.jsonl"
        self.per_rater = Counter(json.loads(a)["rater"] for a in answers.read_text().splitlines()) \
            if answers.exists() else Counter()

    def plan(self, token):
        """This rater's scene order and A/B/C labels (the same every time they open the link)."""
        rng = random.Random("%s:%s" % (self.manifest["seed"], token))
        order = list(self.manifest["sets"])
        rng.shuffle(order)
        out = []
        for s in order:
            methods = sorted(s["clips"])
            rng.shuffle(methods)
            out.append({"id": s["id"], "public": s["public"], "labels": dict(zip(LABELS, methods))})
        return out

    def answered(self, token):
        path = self.data / "answers.jsonl"
        if not path.exists():
            return set()
        return {a["set"] for a in map(json.loads, path.read_text().splitlines()) if a["rater"] == token}

    def answer(self, token, body):
        plan = {p["id"]: p["labels"] for p in self.plan(token)}
        set_id, best, ratings = self.public.get(body.get("set")), body.get("best"), body.get("ratings") or {}
        if set_id not in plan or best not in LABELS or set(ratings) != set(LABELS) or \
                not all(isinstance(v, int) and 1 <= v <= 5 for v in ratings.values()):
            raise ValueError("incomplete answer")
        labels = plan[set_id]
        entry = {"time": datetime.now().isoformat(timespec="seconds"), "rater": token, "set": set_id,
                 "best": labels[best], "ratings": {labels[k]: v for k, v in ratings.items()}, "shown_as": labels}
        with self.lock:
            if self.per_rater[token] >= MAX_ANSWERS_PER_RATER:
                raise ValueError("too many answers from this link")
            self.per_rater[token] += 1
            with (self.data / "answers.jsonl").open("a") as f:
                f.write(json.dumps(entry) + "\n")


def prepare(clips_json, data=DATA):
    spec = json.loads(Path(clips_json).read_text())
    (data / "clips").mkdir(parents=True, exist_ok=True)
    sets = []
    for s in spec["sets"]:
        if sorted(s["clips"]) != METHODS:
            sys.exit("set %s needs exactly: %s" % (s["id"], ", ".join(METHODS)))
        files = {}
        for method, src in s["clips"].items():
            name = secrets.token_hex(6) + Path(src).suffix.lower()      # random name: the file can't give it away
            shutil.copyfile(src, data / "clips" / name)
            files[method] = name
        sets.append({"id": s["id"], "public": secrets.token_hex(5), "clips": files})
    (data / "manifest.json").write_text(json.dumps({"seed": secrets.token_hex(8), "sets": sets}, indent=1))
    print("prepared %d sets in %s" % (len(sets), data))


def make_links(n, base, data=DATA):
    path = data / "raters.json"
    tokens = json.loads(path.read_text())["tokens"] if path.exists() else []
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    new = ["".join(secrets.choice(alphabet) for _ in range(10)) for _ in range(n)]
    path.write_text(json.dumps({"note": "Anonymous codes only. Don't write down who got which.",
                                "tokens": tokens + new}, indent=1))
    for t in new:
        print("%s/r/%s" % (base.rstrip("/"), t))
    return new


# ------------------------------------------------------------------- counting
def last_answers(data=DATA):
    path = data / "answers.jsonl"
    latest = {}
    for a in map(json.loads, path.read_text().splitlines() if path.exists() else []):
        latest[(a["rater"], a["set"])] = a                 # a rater may change an answer: the last one counts
    return list(latest.values())


def rater_means(answers, method):
    by_rater = {}
    for a in answers:
        by_rater.setdefault(a["rater"], []).append(a["ratings"][method])
    return {r: statistics.fmean(v) for r, v in by_rater.items()}


def interval(values, boot=10000, seed=7):
    """95% interval of the mean, resampling raters (bootstrap)."""
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(boot))
    return round(means[int(0.025 * boot)], 3), round(means[int(0.975 * boot) - 1], 3)


def count(data=DATA, boot=10000):
    """The plan's counting, over the raters who answered every scene. A rater who stopped partway
    isn't counted at all (director's rule, set before any ratings came in)."""
    scenes = {s["id"] for s in json.loads((data / "manifest.json").read_text())["sets"]}
    every = last_answers(data)
    answered = {}
    for a in every:
        answered.setdefault(a["rater"], set()).add(a["set"])
    finished = {r for r, done in answered.items() if done >= scenes}
    answers = [a for a in every if a["rater"] in finished]
    raters = sorted(finished)
    picks = {m: sum(a["best"] == m for a in answers) for m in METHODS}
    per_set = {}
    for a in answers:
        per_set.setdefault(a["set"], {m: 0 for m in METHODS})[a["best"]] += 1
    means = {m: rater_means(answers, m) for m in METHODS}
    out = {"rule": COUNT_RULE, "raters": len(raters), "answers": len(answers),
           "not_counted": {"raters": len(answered) - len(finished), "answers": len(every) - len(answers)},
           "picks": picks, "picks_per_set": per_set,
           "mean_rating": {m: round(statistics.fmean(means[m].values()), 2) if means[m] else None for m in METHODS},
           "interval": {m: interval(list(means[m].values()), boot) if len(means[m]) > 1 else None for m in METHODS}}
    for other in ("fx2auto", "manual"):
        diffs = [means["agent"][r] - means[other][r] for r in raters if r in means["agent"] and r in means[other]]
        lo_hi = interval(diffs, boot) if len(diffs) > 1 else None
        beats = bool(lo_hi and picks["agent"] > picks[other] and lo_hi[0] > 0)
        out["agent_vs_" + other] = {"picks": [picks["agent"], picks[other]], "rating_difference_interval": lo_hi,
                                    "verdict": "agent better" if beats else "no clear difference"}
    return out


# ---------------------------------------------------------------------- serving
class Handler(BaseHTTPRequestHandler):
    study = None
    server_version = "camera-agent-rater"

    def log_message(self, *args):          # no request log: no IP addresses kept
        pass

    def headers_out(self, code, ctype, length, extra=()):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")            # also keeps clips out of the tunnel's cache
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("Content-Security-Policy", CSP)
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()

    def send(self, code, body, ctype="application/json", extra=()):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.headers_out(code, ctype, len(data), extra)
        if self.command != "HEAD":
            self.wfile.write(data)

    def token(self, t):
        return t if TOKEN.fullmatch(t or "") and t in self.study.tokens else None

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "r" and self.token(parts[1]):
            return self.send(200, (PAGE / "index.html").read_bytes(), TYPES[".html"])
        if len(parts) == 3 and parts[0] == "api" and parts[2] == "plan" and self.token(parts[1]):
            done = self.study.answered(parts[1])
            sets = [{"id": p["public"], "labels": LABELS, "done": p["id"] in done} for p in self.study.plan(parts[1])]
            return self.send(200, {"sets": sets})
        if len(parts) == 4 and parts[0] == "clip" and self.token(parts[1]):
            return self.clip(parts[1], parts[2], parts[3])
        if len(parts) == 2 and parts[0] in ("fonts", "brand"):
            path = (SHARED / parts[0] / parts[1]).resolve()
        elif len(parts) == 2 and parts[0] == "static":
            path = (PAGE / parts[1]).resolve()
        else:
            return self.send(404, {"error": "not found"})
        if path.suffix in TYPES and path.is_file() and path.parent in (SHARED / "fonts", SHARED / "brand", PAGE):
            return self.send(200, path.read_bytes(), TYPES[path.suffix])
        return self.send(404, {"error": "not found"})

    def clip(self, token, public_id, label):
        set_id = self.study.public.get(public_id)
        labels = {p["id"]: p["labels"] for p in self.study.plan(token)}.get(set_id)
        if not labels or label not in labels:
            return self.send(404, {"error": "not found"})
        path = self.study.data / "clips" / self.study.sets[set_id]["clips"][labels[label]]
        size = path.stat().st_size
        rng = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if rng and (rng.group(1) or rng.group(2)):              # phones (Safari) need byte ranges for video
            start = int(rng.group(1)) if rng.group(1) else max(0, size - int(rng.group(2)))
            end = min(size - 1, int(rng.group(2))) if rng.group(1) and rng.group(2) else size - 1
            if start >= size or start > end:
                return self.send(416, b"", "video/mp4", [("Content-Range", "bytes */%d" % size)])
            return self.stream(206, path, start, end, [("Content-Range", "bytes %d-%d/%d" % (start, end, size))])
        return self.stream(200, path, 0, size - 1)

    def stream(self, code, path, start, end, extra=()):
        self.headers_out(code, "video/mp4", end - start + 1, [("Accept-Ranges", "bytes")] + list(extra))
        if self.command == "HEAD":
            return
        left = end - start + 1
        try:
            with path.open("rb") as f:
                f.seek(start)
                while left > 0:
                    chunk = f.read(min(CHUNK, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass                                  # the viewer skipped ahead or closed the page

    def do_POST(self):
        parts = urlparse(self.path).path.strip("/").split("/")
        if not (len(parts) == 3 and parts[0] == "api" and parts[2] == "answer" and self.token(parts[1])):
            return self.send(404, {"error": "not found"})
        try:
            body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 4000)) or b"{}")
            self.study.answer(parts[1], body if isinstance(body, dict) else {})
        except (ValueError, json.JSONDecodeError) as e:
            return self.send(400, {"ok": False, "error": str(e)})
        return self.send(200, {"ok": True})


def serve(study, host="127.0.0.1", port=8766):
    handler = type("H", (Handler,), {"study": study})
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def share(study, port=0, data=DATA):
    """Online: this page on this Mac only, plus a temporary Cloudflare tunnel (HTTPS) as the one way in."""
    exe = shutil.which("cloudflared")
    if not exe:
        sys.exit("cloudflared isn't installed. Install it with: brew install cloudflared")
    if not study.tokens:
        sys.exit("no links yet: run `links 15` first")
    def stop(*_):
        raise KeyboardInterrupt
    # Ctrl-C, closing the terminal, or `kill` all take it offline: the tunnel must never outlive this program.
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, stop)
    server = serve(study, "127.0.0.1", port)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    local = "http://127.0.0.1:%d" % server.server_address[1]
    tunnel = subprocess.Popen([exe, "tunnel", "--no-autoupdate", "--url", local],
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
            print("The tunnel didn't start (no internet?). Nothing is online.")
            return
        threading.Thread(target=lambda: [None for _ in tunnel.stderr], daemon=True).start()   # keep the pipe drained
        print("Got %s. Giving it %d s to reach the internet's address books, then checking it..." % (base, DNS_HEAD_START_S),
              flush=True)
        time.sleep(DNS_HEAD_START_S)
        works = reachable(base + "/static/rater.css")
        print("Checked over the internet: it works." if works else
              "Couldn't confirm it from this Mac yet (its DNS can lag a minute or two). Try a link on a phone on "
              "mobile data before sending them.")
        links = ["%s/r/%s" % (base, t) for t in sorted(study.tokens)]
        (data / "links.txt").write_text("\n".join(links) + "\n")
        print("Online at %s (from this Mac: %s). Ctrl-C takes it offline.\n" % (base, local))
        print("Send one link per person (also saved in %s; don't note who got which):" % (data / "links.txt"))
        print("\n".join(links), flush=True)
        tunnel.wait()
        print("The tunnel stopped, so the links no longer work. Run share again and send the new links.")
    except KeyboardInterrupt:
        print("\nOffline.")
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["prepare", "links", "share", "serve", "results"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--host", default="127.0.0.1", help="0.0.0.0 lets phones on the same Wi-Fi open it")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--base", help="address to put in the links (default http://<host>:<port>)")
    args = ap.parse_args()
    data = Path(args.data)
    data.mkdir(parents=True, exist_ok=True)
    if args.command == "prepare":
        prepare(args.arg, data)
    elif args.command == "links":
        make_links(int(args.arg or 10), args.base or "http://%s:%d" % (args.host, args.port), data)
    elif args.command == "share":
        share(Study(data), args.port, data)
    elif args.command == "results":
        result = count(data)
        (data / "results.json").write_text(json.dumps(result, indent=1))
        print(json.dumps(result, indent=1))
    else:
        server = serve(Study(data), args.host, args.port)
        print("Rating page on http://%s:%d/r/<code> (Ctrl-C stops it)" % (args.host, server.server_address[1]))
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()


if __name__ == "__main__":
    main()
