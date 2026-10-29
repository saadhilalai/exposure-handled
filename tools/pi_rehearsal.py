"""Rehearse the Pi's phone controls on this Mac, with the fake camera. The same controller, dashboard, PIN and
arming rules as on the Pi (agent/pi_controller.py); only the camera and the Pi's two bridge services are
stand-ins. The made-up scene is 2 stops too dark, so once armed with Auto on, the agent raises ISO.

  python tools/pi_rehearsal.py           try it by hand in a browser at http://127.0.0.1:8772/ (the PIN is printed)
  python tools/pi_rehearsal.py --check   go through the first-arm steps by itself, as the phone would: PASS/FAIL

Nothing here talks to a real camera.
"""
import argparse
import json
import secrets
import shutil
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent.config import parse  # noqa: E402
from agent.dashboard import Dashboard  # noqa: E402
from agent.eyes import Eyes  # noqa: E402
from agent.pi_controller import PiController  # noqa: E402
from agent.pin import PinGuard, hash_pin  # noqa: E402
from tools.fake_bridge import FakeCamera, serve  # noqa: E402

TOO_DARK = -2.0


class FakeServices:
    """Stands in for the Pi's two bridge services: each start() restarts the fake camera in that mode."""

    def __init__(self, cfg):
        self.cfg, self.server, self.cam = cfg, None, None
        cfg.run_dir.mkdir(parents=True, exist_ok=True)

    def start(self, armed):
        self.stop()
        self.cam = FakeCamera(scene_offset=TOO_DARK, read_only=not armed, lock_file=self.cfg.lock_file,
                              allow_exposure=armed and self.cfg.allow_exposure)
        self.server = serve(self.cam, self.cfg.socket_path)

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        self.cfg.socket_path.unlink(missing_ok=True)


class Pi:
    """The controller and the dashboard, running as they do on the Pi."""

    def __init__(self, cfg, guard, services, port, faces):
        self.cfg, self.services = cfg, services
        eyes = None if faces else Eyes(face_model=ROOT / "no-face-model")
        self.c = PiController(cfg, services, guard, eyes=eyes, wait_s=10.0, poll_s=0.05)
        self.dash = Dashboard(None, host="127.0.0.1", port=port, guard=guard).start()
        self.c.attach(self.dash)
        self.thread = threading.Thread(target=self.c.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.c.stop_event.set()
        self.thread.join(timeout=10)
        self.dash.stop()


class Phone:
    """Talks to the dashboard the way the phone's page does (the custom header, the pairing cookie)."""

    def __init__(self, url):
        self.url, self.cookie = url.rstrip("/"), None

    def call(self, path, body=None, paired=True):
        req = urllib.request.Request(self.url + path, method="POST" if body is not None else "GET",
                                     data=None if body is None else json.dumps(body).encode())
        req.add_header("X-Camera-Agent", "1")
        if paired and self.cookie:
            req.add_header("Cookie", self.cookie)
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                code, data, headers = r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            code, data, headers = e.code, e.read(), e.headers
        if path == "/api/pair" and code == 200:
            self.cookie = headers["Set-Cookie"].split(";")[0]
        try:
            return code, json.loads(data)
        except ValueError:
            return code, {}

    def state(self):
        return self.call("/api/state")[1]


def wait_for(test, timeout=15.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if test():
            return True
        time.sleep(0.1)
    return False


def check(cfg, pin, port):
    services = FakeServices(cfg)
    guard = PinGuard(hash_pin(pin, iterations=1000), cfg.paired_file)
    pi = Pi(cfg, guard, services, port, faces=False)
    phone = Phone(pi.dash.url)
    wrong = "000000" if pin != "000000" else "111111"
    results = []

    def step(name, ok, detail=""):
        results.append(ok)
        print("%s  %s%s" % ("PASS" if ok else "FAIL", name, ("  (%s)" % detail) if detail and not ok else ""),
              flush=True)

    mode = lambda: pi.c.mode
    iso_sets = lambda: [s for s in services.cam.sets if s[1] == "IsoSensitivity"]
    try:
        step("Starts read-only, watching and suggesting only",
             wait_for(lambda: mode() == "watching") and services.cam.read_only, mode())
        step("A phone that isn't paired sees nothing and can't arm",
             phone.call("/api/state")[0] == 401 and phone.call("/api/arm", {"pin": pin, "confirm": "LIVE"})[0] == 401)
        step("A wrong PIN doesn't pair the phone; the right one does",
             phone.call("/api/pair", {"pin": wrong})[0] == 403 and phone.call("/api/pair", {"pin": pin})[0] == 200)
        step("The phone sees the Pi watching",
             (phone.state().get("pi") or {}).get("mode") == "watching")
        before = len(services.cam.sets)
        time.sleep(3)
        step("Watching for 3 seconds sends the camera nothing", len(services.cam.sets) == before == 0)
        step("Arming without typing LIVE is refused", phone.call("/api/arm", {"pin": pin})[0] == 400)
        step("Arming with a wrong PIN is refused", phone.call("/api/arm", {"pin": wrong, "confirm": "LIVE"})[0] == 403)
        step("Arming with the PIN and LIVE works",
             phone.call("/api/arm", {"pin": pin, "confirm": "LIVE"})[0] == 200 and wait_for(lambda: mode() == "armed"),
             mode())
        state = phone.state()
        iso_before = state["camera"]["iso"]
        time.sleep(2)
        step("Armed, Auto stays off until pressed (nothing sent)",
             state.get("auto") is False and not services.cam.sets and not services.cam.read_only)
        phone.call("/api/auto", {"on": True})
        changed = wait_for(lambda: iso_sets(), timeout=20)
        names = sorted({s[1] for s in services.cam.sets})
        step("Auto on: the agent raises ISO in the too-dark scene", changed, "no ISO change in 20 s")
        step("Only ISO changes: aperture, shutter and white balance stay", names == ["IsoSensitivity"], names)
        wait_for(lambda: phone.state()["camera"]["iso"] != iso_before, timeout=5)
        step("The phone shows the new ISO", phone.state()["camera"]["iso"] != iso_before,
             "%s -> %s" % (iso_before, phone.state()["camera"]["iso"]))
        step("The kill switch works from any phone, paired or not",
             phone.call("/api/kill", {}, paired=False)[0] == 200 and wait_for(lambda: mode() == "locked"), mode())
        step("After the kill, the camera refuses changes and the kill-switch file is written",
             services.cam.locked and services.cam.read_only and cfg.lock_file.exists())

        pi.stop()                                           # the agent restarts, as at a power cut
        pi = Pi(cfg, guard, services, port, faces=False)
        phone.url = pi.dash.url.rstrip("/")
        step("After a restart it's still locked, and it never arms itself",
             wait_for(lambda: mode() == "locked") and services.cam.read_only and services.cam.locked, mode())
        step("Only arming clears the kill",
             phone.call("/api/arm", {"pin": pin, "confirm": "LIVE"})[0] == 200
             and wait_for(lambda: mode() == "armed") and not cfg.lock_file.exists(), mode())

        phone.call("/api/auto", {"on": True})
        quiet = cfg.phone_timeout_s + 1.5
        time.sleep(quiet)                                   # the phone says nothing: it dropped off
        r = pi.c.runner
        held = len(services.cam.sets)
        time.sleep(2)
        step("Phone gone for %.0f s while armed: Auto goes off and the settings are held" % quiet,
             pi.c.phone_lost and r is not None and r.paused and len(services.cam.sets) == held)
        phone.state()                                       # the phone is back
        back = wait_for(lambda: not pi.c.phone_lost, timeout=5)
        step("Phone back: it says so, and Auto stays off until pressed",
             back and phone.state().get("auto") is False and "back" in pi.c.message, pi.c.message)
        step("Disarm locks it and goes back to read-only",
             phone.call("/api/disarm", {})[0] == 200 and wait_for(lambda: mode() == "locked")
             and services.cam.read_only, mode())
    finally:
        pi.stop()
        services.stop()
    print("\n%d of %d steps passed." % (sum(results), len(results)))
    return all(results)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="go through the first-arm steps by itself")
    ap.add_argument("--port", type=int, default=8772)
    ap.add_argument("--allow-exposure", action="store_true", help="as if the settings file allowed exposure")
    args = ap.parse_args()
    data = Path(tempfile.mkdtemp(prefix="pi-rehearsal-"))
    run_dir = ROOT / "run" / ("reh-%s" % uuid.uuid4().hex[:6])  # macOS caps socket paths at 104 characters
    cfg = parse('[paths]\ndata_dir = "%s"\nrun_dir = "%s"\n[bridge]\nallow_exposure = %s\n'
                % (data, run_dir, "true" if args.allow_exposure else "false"))
    pin = "%06d" % secrets.randbelow(10 ** 6)
    try:
        if args.check:
            sys.exit(0 if check(cfg, pin, args.port) else 1)
        services = FakeServices(cfg)
        pi = Pi(cfg, PinGuard(hash_pin(pin, iterations=1000), cfg.paired_file), services, args.port, faces=True)
        print("Fake Pi with the fake camera: open %s  (PIN %s). Ctrl-C to stop." % (pi.dash.url, pin), flush=True)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            pi.stop()
            services.stop()
    finally:
        shutil.rmtree(data, ignore_errors=True)
        shutil.rmtree(run_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
