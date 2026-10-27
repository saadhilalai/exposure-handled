"""Unattended live test on the real camera, with the dashboard up the whole time.

The director's go: camera on a tripod at a white wall lit by a lamp, card out,
nothing can record; run it without typing LIVE or watching.

  Phase 1, live ISO test (bridge allows ISO only):
      60 s with Auto off (it only suggests). Then ISO is set 2 stops too bright, Auto goes on and
      the agent brings it back. Then 60 s with nothing to fix: it must not touch anything. Then the
      dashboard's kill switch: the runner must stop and the bridge lock.
  Phase 2, self-test (bridge and gate with the exposure switch: aperture, shutter and WB too):
      ISO, aperture and shutter each go one step up and back, then one step down and back. Each change is
      confirmed by the camera, timed, and its brightness change measured in the picture. White
      balance: Color Temp is swept 2800-7500K on the wall to calibrate the WB reading, then put back.
  Phase 3, a short automatic run with all four settings (interview look) on the static scene,
      starting from a deliberately wrong ISO, f-stop and Kelvin so every lever has something to do.
  After every phase the camera is put back exactly as it was found, and that's checked.

Safety: every change goes through SafetyGate.change_setting() (the director's ranges) and the
bridge's own allow-list. The run stops and puts everything back if anything looks wrong:
a refused or unconfirmed change, a setting outside its approved range, a setting changed by
anything other than this test, recording, the camera disconnecting or the live view stalling,
or more changes than planned. The dashboard's kill switch, pressed by a person, stops
everything at once: no more changes, nothing put back (the camera is theirs).

Usage:
  python tools/live_selftest.py                 # the real camera (no other bridge may be running)
  python tools/live_selftest.py --fake          # rehearsal on the fake camera
  [--phases 1,2,3] [--port 8770] [--quick]      # --quick: short waits (rehearsals)
"""
import argparse
import json
import math
import signal
import statistics
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent.bridge_client import BridgeClient  # noqa: E402
from agent.dashboard import Dashboard  # noqa: E402
from agent.runner import AgentRunner  # noqa: E402
from agent.safety import SafetyGate, load_ranges, within_range  # noqa: E402
from agent.sony_values import describe_value, load_enums  # noqa: E402
from agent.tone import CALIBRATION_FILE  # noqa: E402
from tools.step3_bridge_test import DRIFTS_ON_ITS_OWN, diff_settings  # noqa: E402

REAL_SOCKET = ROOT / "run" / "bridge.sock"
FAKE_SOCKET = ROOT / "run" / "fake_bridge.sock"
BRIDGE_DIR = ROOT / "build" / "bridge"
FOUR = ("IsoSensitivity", "FNumber", "ShutterSpeed", "WhiteBalance")
KELVIN = "Colortemp"
AWB, COLOR_TEMP = 0x0000, 0x0100
MUST_NOT_CHANGE = ("MovieShootingMode", "Movie_Recording_FrameRateSetting", "PictureProfile", "PictureProfile_Gamma")
WB_SWEEP = (2800, 3200, 3700, 4300, 5000, 5600, 6500, 7500)
MAX_AGENT_1, MAX_AGENT_3 = 8, 12      # the most changes the agent may make in phase 1 / phase 3
STALL_S = 3.0                         # live view frozen this long = something's wrong
DISAGREE_S = 1.0                      # the runner re-reads settings 4x a second; allow for that


class Abort(Exception):
    """Something looked wrong: stop and put everything back."""


class OperatorKill(Exception):
    """A person pressed the kill switch: stop, send nothing more, leave the camera to them."""


def now_text():
    return datetime.now().isoformat(timespec="milliseconds")


# --------------------------------------------------------------------------- bridges
class RealBridge:
    """Starts and stops build/bridge/camera_bridge with one startup flag (or none = ISO only)."""
    socket = REAL_SOCKET

    def __init__(self, session):
        self.session, self.proc, self.flag = session, None, None

    def start(self, flag=None):
        try:
            BridgeClient(self.socket, timeout=2).close()
            raise Abort("another bridge is already running on %s: stop it first" % self.socket)
        except OSError:
            pass
        log = (self.session / "bridge_stdout.log").open("a")
        log.write("--- %s start %s\n" % (now_text(), flag or "(ISO only)"))
        log.flush()
        cmd = [str(BRIDGE_DIR / "camera_bridge"), str(self.socket), str(self.session)] + ([flag] if flag else [])
        self.proc = subprocess.Popen(cmd, cwd=BRIDGE_DIR, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise Abort("the bridge stopped while connecting (exit %s): see bridge_stdout.log" % self.proc.returncode)
            try:
                c = BridgeClient(self.socket, timeout=3)
                status = c.status()
                c.close()
                if status.get("connected"):
                    self.flag = flag
                    return status
            except OSError:
                pass
            time.sleep(0.3)
        raise Abort("the bridge didn't connect to the camera within 30 s")

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        if not self.alive():
            return
        try:
            c = BridgeClient(self.socket, timeout=5)
            c.quit()
            c.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            self.proc.wait(timeout=5)


class FakeBridge:
    """The fake camera in this process. It keeps its state across 'restarts', like a real camera."""
    socket = FAKE_SOCKET

    def __init__(self, session, frame=None):
        from tools.fake_bridge import FakeCamera
        self.camera = FakeCamera(frame=frame, iso=1600, shutter=50, fnumber=5.6, log_dir=session, light_k=3200)
        self.server, self.flag = None, None

    def start(self, flag=None):
        from tools.fake_bridge import serve
        c = self.camera
        c.read_only, c.allow_exposure, c.iso_while_recording, c.locked = flag == "--read-only", flag == "--allow-exposure", False, False
        self.server, self.flag = serve(c, self.socket), flag
        return {"connected": True}

    def alive(self):
        return self.server is not None

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            self.socket.unlink(missing_ok=True)


# --------------------------------------------------------------------------- watchdog
class Tracker:
    """Every change this test makes, what the camera should show, and the change budget."""

    def __init__(self, found, ranges, enums):
        self.found = found
        self.ranges, self.enums = ranges, enums
        self.expected = {n: found[n]["current"] for n in FOUR + (KELVIN,)}
        self.budget = self.used = 0
        self.part = None
        self.changes = []
        self.disagree_since = {}

    def allow(self, n, part):
        """A new part of the test may make up to n changes."""
        self.budget, self.used, self.part = n, 0, part

    def freeze(self):
        """No more changes allowed in this part (e.g. the 'nothing to fix' hold)."""
        self.budget = self.used

    def text(self, name, raw):
        return describe_value(name, raw, self.enums)

    def wrap(self, gate, who):
        send = gate.change_setting

        def change_setting(name, raw, reason):
            if self.used >= self.budget:
                raise Abort("more changes than planned in %s (%d allowed): %s %s was stopped before sending" % (
                    self.part, self.budget, name, self.text(name, raw)))
            self.used += 1
            reply = send(name, raw, reason)
            entry = {"time": now_text(), "part": self.part, "who": who, "setting": name,
                     "to": self.text(name, raw), "raw": raw, "reason": reason, "ok": bool(reply.get("ok")),
                     "changed": reply.get("changed"), "ms_confirmed": reply.get("ms_confirmed"),
                     "error": reply.get("error")}
            self.changes.append(entry)
            if not reply.get("ok"):
                raise Abort("%s → %s was %s: %s" % (name, self.text(name, raw),
                                                    "refused" if reply.get("refused") else "not confirmed",
                                                    reply.get("error") or "no confirmation"))
            self.expected[name] = reply.get("camera_reports", raw)
            if name == "WhiteBalance":
                self.expected[KELVIN] = self._kelvin_after_mode_change(gate.client, raw)
            return reply

        gate.change_setting = change_setting
        return gate

    @staticmethod
    def _kelvin_after_mode_change(client, mode):
        """Switching WB mode makes the camera show (or hide) its remembered Kelvin: wait for it to settle."""
        deadline = time.monotonic() + 2.0
        k = None
        while time.monotonic() < deadline:
            k = client.get(KELVIN)[KELVIN]["current"]
            if (mode == COLOR_TEMP) == (k != 0):
                break
            time.sleep(0.05)
        return k

    def check(self, props, now):
        """Raises Abort if a setting is outside its range, changed by something else, or recording started."""
        for name in FOUR:
            raw = props[name]["current"]
            if not within_range(name, raw, self.ranges[name]) and raw != self.found[name]["current"]:
                raise Abort("%s is %s, outside its approved range" % (name, self.text(name, raw)))
        if props["WhiteBalance"]["current"] == COLOR_TEMP and props.get(KELVIN, {}).get("current"):
            k = props[KELVIN]["current"]
            if not within_range(KELVIN, k, self.ranges[KELVIN]):
                raise Abort("white balance is %dK, outside the approved 2800-7500K" % k)
        for name in FOUR + (KELVIN,):
            want, have = self.expected.get(name), props.get(name, {}).get("current")
            if want is None or have is None or have == want:
                self.disagree_since.pop(name, None)
                continue
            if now - self.disagree_since.setdefault(name, now) > DISAGREE_S:
                raise Abort("%s changed to %s, not by this test (expected %s)" % (
                    name, self.text(name, have), self.text(name, want)))
        for name in MUST_NOT_CHANGE:
            if name in props and name in self.found and props[name]["current"] != self.found[name]["current"]:
                raise Abort("%s changed (%s → %s): this test never touches it" % (
                    name, self.text(name, self.found[name]["current"]), self.text(name, props[name]["current"])))
        if props.get("RecordingState", {}).get("current"):
            raise Abort("the camera started recording")


class TestDashboard(Dashboard):
    """The normal dashboard, which also tells the test whether a kill came from a person."""
    test_kill_expected = False
    operator_killed = False
    t_kill_done = None

    def control(self, action, body):
        if action == "kill" and not self.test_kill_expected:
            self.operator_killed = True
        reply = super().control(action, body)
        if action == "kill":
            self.t_kill_done = time.monotonic()
        return reply


# --------------------------------------------------------------------------- the test
class LiveSelfTest:
    def __init__(self, args):
        self.args = args
        self.session = ROOT / "sessions" / ("%s_live-selftest%s" % (datetime.now().strftime("%Y-%m-%d_%H%M%S"),
                                                                    "-fake" if args.fake else ""))
        self.session.mkdir(parents=True)
        self.bridge = FakeBridge(self.session, args.frame) if args.fake else RealBridge(self.session)
        self.ranges, self.enums = load_ranges(), load_enums()
        self.quick = args.quick
        self.runner = self.dash = None
        self.exposure_used = False
        self.remembered_k = None
        self.wb_cal = None
        self.report = {"started": now_text(), "fake": args.fake, "phases": {}, "stopped": None}
        self.last_frame_no, self.last_frame_t = -1, time.monotonic()

    # ----------------------------------------------------------- plumbing
    def wait(self, real_s, quick_s):
        return quick_s if self.quick else real_s

    def say(self, text, kind="test"):
        line = "%s  %s" % (datetime.now().strftime("%H:%M:%S"), text)
        print(line, flush=True)
        with (self.session / "selftest_log.txt").open("a") as f:
            f.write(line + "\n")
        if self.runner is not None:
            self.runner._event(kind, text)

    def save(self):
        self.report["tracker_changes"] = self.tracker.changes if hasattr(self, "tracker") else []
        (self.session / "selftest_report.json").write_text(json.dumps(self.report, indent=1, default=str))

    def new_runner(self, part, live, exposure, look, auto=False):
        r = AgentRunner(self.bridge.socket, self.session / part, look=look, live=live, auto=auto, exposure=exposure)
        r.start()
        self.tracker.wrap(r.gate, "agent")
        old, self.runner = self.runner, r
        if self.dash is None:
            self.dash = TestDashboard(r, "127.0.0.1", self.args.port).start()
            self.say("Dashboard: %s" % self.dash.url)
        else:
            self.dash.runner = r
            self.dash.cache.clear()
        if old is not None:
            old.close()
        self.last_frame_no, self.last_frame_t = -1, time.monotonic()
        return r

    def check_operator(self):
        if self.dash is not None and self.dash.operator_killed:
            raise OperatorKill("the kill switch was pressed on the dashboard")
        if self.runner is not None and self.runner.killed and not self.dash.test_kill_expected:
            if (self.runner.kill_reason or "").startswith("Runaway"):
                raise Abort(self.runner.kill_reason)
            raise OperatorKill(self.runner.kill_reason or "the kill switch was used")

    def pump(self, seconds, until=None, on_sample=None):
        """Keep the live view (and the dashboard) going while the watchdog checks every frame.
        Returns True if until() became true, False if the time ran out."""
        r = self.runner
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.check_operator()
            if not self.bridge.alive():
                raise Abort("the bridge stopped (camera disconnected?)")
            going = r.step()
            now = time.monotonic()
            if not going:
                self.check_operator()
                if r.killed and self.dash.test_kill_expected:
                    return True
                errors = [e["text"] for e in r.events if e["kind"] == "error"]
                raise Abort(errors[-1] if errors else "the agent stopped by itself")
            if r.frame_no != self.last_frame_no:
                self.last_frame_no, self.last_frame_t = r.frame_no, now
            elif now - self.last_frame_t > STALL_S:
                raise Abort("the live view froze for %.0f s" % STALL_S)
            self.tracker.check(r.props, now)
            if on_sample and r.report is not None:
                on_sample(now - r.report.ms / 1000.0, r.report)
            if r.paused and r.live and getattr(r, "_auto_wanted", False):
                pauses = [e["text"] for e in r.events if e["kind"] == "pause" and e["text"].startswith("PAUSED")]
                raise Abort(pauses[-1] if pauses else "the agent paused itself")
            if until is not None and until():
                return True
        return False

    def read(self, flag=None, keep=False):
        """Full settings, via a bridge started for it if none is up."""
        started = not self.bridge.alive()
        if started:
            self.bridge.start(flag or "--read-only")
        c = BridgeClient(self.bridge.socket)
        props = c.settings()
        c.close()
        if started and not keep:
            self.bridge.stop()
        return props

    def kelvin_options(self):
        return [k for k in WB_SWEEP if within_range(KELVIN, k, self.ranges[KELVIN])]

    # ----------------------------------------------------------- phase 0
    def find(self):
        """Read-only: how the camera was found. Nothing may change before this is saved."""
        self.bridge.start("--read-only")
        c = BridgeClient(self.bridge.socket)
        status = c.status()
        found = c.settings()
        time.sleep(1.0)
        again = c.settings()
        c.close()
        self.bridge.stop()
        self.found = found
        self.volatile = set(DRIFTS_ON_ITS_OWN) | {d["setting"] for d in diff_settings(found, again, self.enums)}
        (self.session / "settings_found.json").write_text(json.dumps(found, indent=1))
        self.tracker = Tracker(found, self.ranges, self.enums)
        t = lambda n: describe_value(n, found[n]["current"], self.enums)  # noqa: E731
        self.report["found"] = {n: t(n) for n in FOUR + MUST_NOT_CHANGE + ("RecordingState",)}
        self.say("Found: %s, %s, %s, WB %s, %s, %s, %s" % (
            t("IsoSensitivity"), t("ShutterSpeed"), t("FNumber"), t("WhiteBalance"), t("MovieShootingMode"),
            t("Movie_Recording_FrameRateSetting"), t("RecordingState")))
        if found["RecordingState"]["current"]:
            raise Abort("the camera is recording: not starting")
        for name in FOUR:
            if not within_range(name, found[name]["current"], self.ranges[name]):
                raise Abort("%s starts at %s, outside its approved range: I couldn't put it back through the "
                            "safety gate, so I won't start" % (name, t(name)))
        if found["WhiteBalance"]["current"] == COLOR_TEMP and not within_range(KELVIN, found[KELVIN]["current"],
                                                                              self.ranges[KELVIN]):
            raise Abort("WB starts at %s, outside 2800-7500K" % t(KELVIN))
        self.report["volatile"] = sorted(self.volatile)
        self.report["bridge_status_read_only"] = status
        self.save()

    # ----------------------------------------------------------- phase 1
    def phase1(self):
        res = self.report["phases"]["1"] = {"name": "live ISO test", "result": "running"}
        self.bridge.start(None)                                    # ISO only
        self.tracker.allow(1 + MAX_AGENT_1, "phase 1")
        r = self.new_runner("phase1", live=True, exposure=False, look="cinematic", auto=False)
        if r.allowed != {"IsoSensitivity"}:
            raise Abort("phase 1 must allow ISO only, got %s" % sorted(r.allowed))
        self.say("TEST 1 of 3 · Live ISO test. Bridge: ISO only (800-12800). First %d s with Auto off: it only suggests."
                 % self.wait(60, 8))

        # a. Auto off: it may only suggest.
        self.pump(self.wait(60, 8))
        would = [e["text"] for e in r.events if e["kind"] == "would_change" and "ISO" in e["text"]]
        res["dry_run_iso_suggestions"] = would
        res["dry_run_status"] = r.output.status if r.output else None

        # b. Start it 2 stops too bright.
        found_iso = self.found["IsoSensitivity"]["current"]
        isos = sorted(v for v in (r.props["IsoSensitivity"].get("set_values") or r.props["IsoSensitivity"]["values"])
                      if within_range("IsoSensitivity", v, self.ranges["IsoSensitivity"]))
        setup = min(isos, key=lambda v: abs(math.log2(v / (found_iso * 4))))
        r.gate.change_setting("IsoSensitivity", setup, "Test setup: ISO 2 stops too bright, so the agent has something to fix")
        self.say("Test setup: ISO %d → %d (2 stops too bright). Auto goes on in 2 s." % (found_iso, setup), "change")
        self.pump(2.0)

        # c. Auto on: it should bring it back, in small steps, and stop.
        n0, t_auto = len(r.changes), time.monotonic()
        r.set_auto(True)
        r._auto_wanted = True
        quiet = 8.0
        settled = self.pump(90, until=lambda: len(r.changes) > n0 and time.monotonic() - max(
            [c["t"] for c in r.changes] or [t_auto]) >= quiet)
        agent = r.changes[n0:]
        res["agent_changes"] = [{k: c[k] for k in ("setting", "from", "to", "reason", "ms_confirmed")} |
                                {"t_after_auto": round(c["t"] - t_auto, 2)} for c in agent]
        res["settled"] = settled
        res["settle_s"] = round(agent[-1]["t"] - t_auto, 1) if agent else None
        res["status_when_settled"] = r.output.status if r.output else None
        self.say("Agent: %d change(s) in %.1f s, then quiet for %.0f s: %s" % (
            len(agent), res["settle_s"] or 0, quiet, res["status_when_settled"]))
        if not settled:
            res["result"] = "FAIL: didn't settle within 90 s"
            raise Abort("the agent didn't settle within 90 s")

        # d. Nothing to fix: it must not touch anything.
        hold = self.wait(60, 8)
        self.tracker.freeze()
        self.say("Holding %d s with nothing to fix: any change now counts as a fault." % hold)
        n_hold = len(r.changes)
        self.pump(hold)
        res["changes_during_hold"] = len(r.changes) - n_hold

        # e. The kill switch, pressed through the dashboard exactly as the button does it.
        self.say("Kill switch test: pressing the dashboard's kill switch now.")
        self.dash.test_kill_expected = True
        t_press = time.monotonic()

        def press():
            req = urllib.request.Request("http://127.0.0.1:%d/api/kill" % self.dash.port, data=b"{}", method="POST",
                                         headers={"X-Camera-Agent": "1", "Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5).read()

        threading.Thread(target=press, daemon=True).start()
        stopped = self.pump(5.0, until=lambda: r.killed)
        t_stopped = time.monotonic()
        c = BridgeClient(self.bridge.socket)
        locked = c.status().get("locked")
        c.close()
        res["kill"] = {"runner_stopped": bool(stopped and r.killed), "ms_to_stop": round((t_stopped - t_press) * 1000),
                       "ms_button_answered": round(((self.dash.t_kill_done or t_stopped) - t_press) * 1000),
                       "bridge_locked": locked}
        self.dash.test_kill_expected = False
        self.say("Kill switch: runner stopped in %d ms, bridge locked: %s." % (res["kill"]["ms_to_stop"], locked))

        problems = []
        if res["dry_run_iso_suggestions"]:
            problems.append("suggested ISO changes on a static scene before Auto")
        if res["changes_during_hold"]:
            problems.append("changed something with nothing to fix")
        if not (res["kill"]["runner_stopped"] and locked and res["kill"]["ms_to_stop"] <= 1500):
            problems.append("kill switch")
        if not all(c["setting"] == "IsoSensitivity" for c in agent):
            problems.append("changed something other than ISO")
        res["result"] = "PASS" if not problems else "FAIL: " + "; ".join(problems)
        self.bridge.stop()                                         # locked: a fresh bridge puts ISO back
        self.restore("after test 1", flag=None)
        self.save()
        return not problems

    # ----------------------------------------------------------- phase 2
    def sample(self, t, rep):
        return {"t": t, "key": rep.key_stops, "mired": rep.color.get("mired_shift"),
                "conf": rep.color.get("confidence"), "neutral": rep.color.get("neutral_pixel_share")}

    def step(self, gate, name, raw, reason, kind):
        """One self-test change: 0.6 s before, the change, 1.6 s after; measures what the picture did."""
        before, after = [], []
        self.pump(0.6, on_sample=lambda t, rep: before.append(self.sample(t, rep)))
        old = self.runner.props[name]["current"]
        r = self.runner
        r.hold_status = "Self-test: %s %s → %s" % (name, self.tracker.text(name, old), self.tracker.text(name, raw))
        reply = gate.change_setting(name, raw, reason)
        t_sent = reply.get("t_sent_monotonic", time.monotonic())
        r._event("change", "Self-test: %s → %s (confirmed in %s ms)" % (
            self.tracker.text(name, old), self.tracker.text(name, raw), _ms(reply.get("ms_confirmed"))))
        self.pump(1.6, on_sample=lambda t, rep: after.append(self.sample(t, rep)))
        field = "mired" if kind == "wb" else "key"
        b = [s[field] for s in before if s[field] is not None]
        a = [s[field] for s in after if s[field] is not None and 1.0 <= s["t"] - t_sent <= 1.6]
        out = {"setting": name, "from": self.tracker.text(name, old), "to": self.tracker.text(name, raw), "raw": raw,
               "changed": reply.get("changed", True), "ms_confirmed": reply.get("ms_confirmed"),
               "ms_first_callback": reply.get("ms_first_callback"), "measure": field,
               "before": round(statistics.median(b), 3) if b else None,
               "after": round(statistics.median(a), 3) if a else None,
               "confidence_after": statistics.mode([s["conf"] for s in after[-10:]]) if after else None,
               "neutral_after": after[-1]["neutral"] if after else None}
        if kind == "exposure":
            out["expected_stops"] = round(expected_stops(name, old, raw), 3)
        if b and a:
            delta = out["after"] - out["before"]
            out["measured"] = round(delta, 3)
            big_enough = abs(delta) >= (8.0 if kind == "wb" else 0.12)
            if big_enough:
                half = out["before"] + delta / 2
                hit = [s["t"] for s in after if s[field] is not None and (s[field] - half) * math.copysign(1, delta) >= 0]
                out["ms_picture_halfway"] = round((hit[0] - t_sent) * 1000) if hit else None
            else:
                out["ms_picture_halfway"] = None
                out["note"] = "change too small to time in the picture"
        return out

    def exposure_steps(self, props):
        """[(name, raw, label)]: one step up and back, one step down and back, for ISO, aperture, shutter."""
        plan = []
        for name in ("IsoSensitivity", "FNumber", "ShutterSpeed"):
            start = props[name]["current"]
            offered = props[name].get("set_values") or props[name]["values"]
            ok = [v for v in offered if within_range(name, v, self.ranges[name])]
            key = (lambda v: (v >> 16) / (v & 0xFFFF)) if name == "ShutterSpeed" else (lambda v: v & 0xFFFFFF)
            ok.sort(key=key)
            i = ok.index(start)
            for j, label in ((i + 1, "up"), (i - 1, "down")):
                if 0 <= j < len(ok):
                    plan += [(name, ok[j], "one step %s" % label), (name, start, "back")]
        return plan

    def phase2(self):
        res = self.report["phases"]["2"] = {"name": "self-test", "result": "running"}
        self.exposure_used = True
        self.bridge.start("--allow-exposure")
        r = self.new_runner("phase2", live=False, exposure=True, look="cinematic")
        r.held, r.hold_status = True, "Self-test: starting"
        gate = self.tracker.wrap(SafetyGate(r.client, self.session / "phase2" / "changes.jsonl", self.ranges,
                                            exposure=True), "self-test")
        plan = self.exposure_steps(r.props)
        wb_found = r.props["WhiteBalance"]["current"]
        sweep = self.kelvin_options()
        n_wb = (1 if wb_found != COLOR_TEMP else 0) + len(sweep) + 1 + (1 if wb_found != COLOR_TEMP else 0)
        self.tracker.allow(len(plan) + n_wb, "phase 2 (self-test)")
        self.say("TEST 2 of 3 · Self-test, exposure switch ON (aperture f/2.8-f/11, shutter 1/48-1/100, WB 2800-7500K). "
                 "%d planned changes, each put back." % (len(plan) + n_wb))
        self.pump(1.0)

        steps = []
        for name, raw, label in plan:
            reason = "Self-test: %s %s" % (name, label)
            steps.append(self.step(gate, name, raw, reason, "exposure"))
            steps[-1]["label"] = label
            s = steps[-1]
            self.say("  %s %s → %s: camera confirmed in %s ms; picture %s" % (
                name, s["from"], s["to"], _ms(s["ms_confirmed"]),
                "%+.2f st (expected %+.2f)" % (s["measured"], s["expected_stops"]) if s.get("measured") is not None else "?"))
        res["exposure_steps"] = steps

        # White balance: Color Temp mode, sweep, put the remembered Kelvin back, then the original mode.
        wb_steps = []
        if wb_found != COLOR_TEMP:
            wb_steps.append(self.step(gate, "WhiteBalance", COLOR_TEMP, "Self-test: Color Temp mode, to set Kelvin", "wb"))
        self.remembered_k = self.tracker.expected[KELVIN]
        res["kelvin_remembered_by_camera"] = self.remembered_k
        self.say("  WB → Color Temp: the camera's remembered Kelvin is %sK" % self.remembered_k)
        if not within_range(KELVIN, self.remembered_k or 0, self.ranges[KELVIN]):
            raise Abort("the camera's remembered Kelvin (%s) is outside 2800-7500K" % self.remembered_k)
        for k in sweep:
            wb_steps.append(self.step(gate, KELVIN, k, "Self-test: WB calibration on the wall, %dK" % k, "wb"))
            s = wb_steps[-1]
            self.say("  WB %s → %s: confirmed in %s ms; picture %s mired (confidence %s)" % (
                s["from"], s["to"], _ms(s["ms_confirmed"]), s["after"], s["confidence_after"]))
        wb_steps.append(self.step(gate, KELVIN, self.remembered_k,
                                  "Self-test: back to the Kelvin the camera remembered (%dK)" % self.remembered_k, "wb"))
        if wb_found != COLOR_TEMP:
            wb_steps.append(self.step(gate, "WhiteBalance", wb_found, "Self-test: back to %s" %
                                      self.tracker.text("WhiteBalance", wb_found), "wb"))
        res["wb_steps"] = wb_steps
        self.wb_cal = res["wb_calibration"] = fit_wb([(s["raw"], s["after"]) for s in wb_steps
                                                      if s["setting"] == KELVIN and s["after"] is not None
                                                      and s["raw"] in sweep])
        cal = self.wb_cal
        self.say("  WB calibration: %s" % cal["summary"])
        if cal["ok"] and not self.args.fake:
            save_wb_calibration(cal, self.session)
            self.say("  Saved to config/liveview_calibration.json (slog3.white_balance).")

        problems = []
        for s in steps:
            if s.get("expected_stops") is not None and abs(s["expected_stops"]) >= 0.2:
                if s.get("measured") is None or abs(s["measured"] - s["expected_stops"]) > 0.12:
                    problems.append("%s %s→%s measured %s st, expected %+.2f" % (
                        s["setting"], s["from"], s["to"], s.get("measured"), s["expected_stops"]))
        if not cal["ok"]:
            problems.append("WB calibration: " + cal["summary"])
        res["problems"] = problems
        res["result"] = "PASS" if not problems else "PASS WITH NOTES: " + "; ".join(problems)
        self.bridge.stop()
        self.restore("after test 2", flag="--allow-exposure")
        self.save()
        return True

    # ----------------------------------------------------------- phase 3
    def phase3(self):
        res = self.report["phases"]["3"] = {"name": "automatic run, all four settings", "result": "running"}
        self.exposure_used = True
        self.bridge.start("--allow-exposure")
        use_wb = bool(self.wb_cal and self.wb_cal["ok"])
        r = self.new_runner("phase3", live=True, exposure=True, look="interview", auto=False)
        found = {n: self.found[n]["current"] for n in FOUR}
        setup = [("IsoSensitivity", self.iso_two_thirds_up(r.props, found["IsoSensitivity"]),
                  "Test setup: ISO too high"),
                 ("FNumber", 800 if found["FNumber"] != 800 else 1000, "Test setup: closed down past the look's range")]
        if use_wb:
            wrong = self.wrong_kelvin()
            setup += [("WhiteBalance", COLOR_TEMP, "Test setup: Color Temp mode, so the agent can set Kelvin"),
                      (KELVIN, wrong, "Test setup: a wrong Kelvin (%dK), so WB has something to fix" % wrong)]
        self.tracker.allow(len(setup) + MAX_AGENT_3, "phase 3")
        self.say("TEST 3 of 3 · Automatic run, all four settings, interview look. Setup: %s. Auto goes on after." % (
            ", ".join("%s %s" % (n, self.tracker.text(n, v)) for n, v, _ in setup)))
        if not use_wb:
            self.say("WB calibration didn't pass, so this run leaves WB alone (the agent can't trust its WB reading).")
        self.pump(2.0)
        for name, raw, reason in setup:
            r.gate.change_setting(name, raw, reason)
            self.pump(0.5)
        self.pump(2.0)

        n0, t_auto = len(r.changes), time.monotonic()
        r.set_auto(True)
        r._auto_wanted = True
        quiet = 15.0
        settled = self.pump(120, until=lambda: time.monotonic() - max([c["t"] for c in r.changes[n0:]] or [t_auto]) >= quiet
                            and (len(r.changes) > n0))
        agent = r.changes[n0:]
        res["setup"] = [{"setting": n, "to": self.tracker.text(n, v)} for n, v, _ in setup]
        res["agent_changes"] = [{k: c[k] for k in ("setting", "from", "to", "reason", "ms_confirmed")} |
                                {"t_after_auto": round(c["t"] - t_auto, 2)} for c in agent]
        res["settled"] = settled
        res["settle_s"] = round(agent[-1]["t"] - t_auto, 1) if agent else None
        res["status_when_settled"] = r.output.status if r.output else None
        res["advice_when_settled"] = r.output.advice if r.output else []
        self.say("Agent: %d change(s) in %.1f s: %s" % (len(agent), res["settle_s"] or 0, res["status_when_settled"]))
        if not settled:
            raise Abort("the agent didn't settle within 120 s")
        hold = self.wait(30, 6)
        self.tracker.freeze()
        self.say("Holding %d s with nothing to fix: any change now counts as a fault." % hold)
        n_hold = len(r.changes)
        self.pump(hold)
        res["changes_during_hold"] = len(r.changes) - n_hold
        r._auto_wanted = False
        r.set_auto(False)
        self.pump(0.5)
        touched = {c["setting"] for c in agent}
        res["levers_used"] = sorted(touched)
        problems = ["changed something with nothing to fix"] if res["changes_during_hold"] else []
        res["result"] = "PASS" if not problems else "FAIL: " + "; ".join(problems)
        self.bridge.stop()
        self.restore("after test 3", flag="--allow-exposure")
        self.save()
        return not problems

    def iso_two_thirds_up(self, props, iso):
        isos = sorted(v for v in (props["IsoSensitivity"].get("set_values") or props["IsoSensitivity"]["values"])
                      if within_range("IsoSensitivity", v, self.ranges["IsoSensitivity"]))
        return min(isos, key=lambda v: abs(math.log2(v / (iso * 2))))      # about 1 stop up

    def wrong_kelvin(self):
        """A Kelvin far from the light, where the WB reading was still trusted during the sweep."""
        light = self.wb_cal["light_k"]
        trusted = [s["raw"] for s in self.report["phases"]["2"]["wb_steps"]
                   if s["setting"] == KELVIN and s["confidence_after"] in ("medium", "high")
                   and abs(1e6 / s["raw"] - 1e6 / light) >= 60]
        if not trusted:
            return 6500 if light < 4800 else 3200
        return max(trusted, key=lambda k: abs(1e6 / k - 1e6 / light))

    # ----------------------------------------------------------- putting it back
    def restore(self, label, flag):
        """Put the four settings (and the camera's remembered Kelvin) back exactly as found, through the gate,
        then check by reading back. Starts its own bridge; disconnects at the end."""
        self.say("Putting everything back as found (%s)." % label, "restore")
        for attempt_no in (1, 2):
            attempt = flag
            try:
                if self.bridge.alive():
                    self.bridge.stop()
                self.bridge.start(attempt)
                c = BridgeClient(self.bridge.socket)
                gate = self.tracker.wrap(SafetyGate(c, self.session / "restore_changes.jsonl", self.ranges,
                                                    exposure=attempt == "--allow-exposure"), "restore")
                self.tracker.allow(6, "restore (%s)" % label)
                now = c.get(*FOUR, KELVIN)
                cur = {n: now[n]["current"] for n in FOUR + (KELVIN,)}
                want = {n: self.found[n]["current"] for n in FOUR + (KELVIN,)}
                if cur["WhiteBalance"] == COLOR_TEMP and want["WhiteBalance"] != COLOR_TEMP:
                    if self.remembered_k and cur[KELVIN] != self.remembered_k:
                        gate.change_setting(KELVIN, self.remembered_k, "Putting back the Kelvin the camera remembered")
                    gate.change_setting("WhiteBalance", want["WhiteBalance"], "Putting back how you left it")
                elif want["WhiteBalance"] == COLOR_TEMP and cur[KELVIN] != want[KELVIN]:
                    gate.change_setting(KELVIN, want[KELVIN], "Putting back how you left it")
                for name in ("IsoSensitivity", "FNumber", "ShutterSpeed"):
                    if cur[name] != want[name]:
                        gate.change_setting(name, want[name], "Putting back how you left it")
                end = c.settings()
                c.close()
                self.bridge.stop()
                break
            except Abort as e:
                self.say("Restore attempt %d failed (%s)%s" % (attempt_no, e, "; trying once more" if attempt_no == 1 else ""))
                if attempt_no == 2:
                    self.report.setdefault("restore_failures", []).append({"when": label, "error": str(e)})
                    self.bridge.stop()
                    raise
        (self.session / ("settings_%s.json" % label.replace(" ", "_"))).write_text(json.dumps(end, indent=1))
        wrong = [n for n in FOUR if end[n]["current"] != self.found[n]["current"]]
        if self.found["WhiteBalance"]["current"] == end["WhiteBalance"]["current"] and \
                end[KELVIN]["current"] != self.found[KELVIN]["current"]:
            wrong.append(KELVIN)
        others = [d for d in diff_settings(self.found, end, self.enums)
                  if d["setting"] not in self.volatile and d["setting"] not in FOUR + (KELVIN,)
                  and not d["drifts_on_its_own"]]
        self.report.setdefault("restores", []).append({"when": label, "time": now_text(), "not_back": wrong,
                                                       "other_differences": others})
        if wrong:
            raise Abort("after putting back, still different: %s" % ", ".join(wrong))
        t = lambda n: describe_value(n, end[n]["current"], self.enums)  # noqa: E731
        self.say("Back as found: %s, %s, %s, WB %s. Other settings different from the start: %s" % (
            t("IsoSensitivity"), t("ShutterSpeed"), t("FNumber"), t("WhiteBalance"),
            ", ".join("%s %s→%s" % (d["setting"], d["before"], d["after"]) for d in others) or "none"), "restore")

    # ----------------------------------------------------------- the whole run
    def run(self, phases):
        try:
            self.find()
            ok = True
            if 1 in phases:
                ok = self.phase1()
                if not ok:
                    self.say("Test 1 didn't pass, so the other settings stay locked. Stopping here.")
            if ok and 2 in phases:
                self.phase2()
            if ok and 3 in phases:
                self.phase3()
            self.report["finished"] = now_text()
        except OperatorKill as e:
            self.report["stopped"] = "kill switch: %s" % e
            self.say("STOPPED by the kill switch (%s). Nothing more is sent; the camera is yours." % e, "kill")
            self.bridge.stop()
            try:                                       # reading only: what's different from how it was found
                end = self.read("--read-only")
                self.report["left_after_kill"] = [d for d in diff_settings(self.found, end, self.enums)
                                                  if d["setting"] in FOUR + (KELVIN,)]
            except Exception as e2:
                self.report["left_after_kill"] = "couldn't read: %s" % e2
        except (Abort, Exception, KeyboardInterrupt) as e:
            kind = "STOPPED" if isinstance(e, Abort) else "STOPPED (interrupted)" if isinstance(
                e, KeyboardInterrupt) else "STOPPED (program error)"
            self.report["stopped"] = "%s: %s" % (kind, e)
            self.say("%s: %s. Putting everything back." % (kind, e), "error")
            if not isinstance(e, (Abort, KeyboardInterrupt)):
                import traceback
                (self.session / "error.txt").write_text(traceback.format_exc())
            try:
                self.bridge.stop()
                if hasattr(self, "tracker"):
                    self.restore("after stop", flag="--allow-exposure" if self.exposure_used else None)
            except Exception as e2:
                self.report["stopped"] += " · RESTORE FAILED: %s" % e2
                self.say("COULD NOT PUT EVERYTHING BACK: %s. Check the camera by hand: %s" % (e2, self.report.get("found")),
                         "error")
        finally:
            self.bridge.stop()
            if self.runner is not None:
                self.runner.close()
            if self.dash is not None:
                self.dash.stop()
            self.save()
            print("Report: %s" % (self.session / "selftest_report.json"), flush=True)


# --------------------------------------------------------------------------- helpers
def _ms(v):
    return "?" if v is None else "%d" % round(v)


def expected_stops(name, old, new):
    if name == "IsoSensitivity":
        return math.log2((new & 0xFFFFFF) / (old & 0xFFFFFF))
    if name == "FNumber":
        return 2 * math.log2(old / new)
    if name == "ShutterSpeed":
        return math.log2(((new >> 16) / (new & 0xFFFF)) / ((old >> 16) / (old & 0xFFFF)))
    return 0.0


def fit_wb(points):
    """WB sweep on a neutral wall -> how the live view's color shift relates to the WB error.
    Model: picture mired shift m = gain x (1e6/light - 1e6/WB). A straight line through the points
    (x = 1e6/WB) gives gain = -slope, and the light's color temperature where the wall looks neutral."""
    pts = [(k, m) for k, m in points if m is not None]
    out = {"points": [{"kelvin": k, "picture_mired_shift": m} for k, m in pts], "ok": False}
    if len(pts) < 4:
        out["summary"] = "not enough points (%d)" % len(pts)
        return out
    xs = [1e6 / k for k, _ in pts]
    ys = [m for _, m in pts]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    icpt = my - slope * mx
    ss_res = sum((y - (icpt + slope * x)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    gain = -slope
    light = 1e6 * gain / icpt if icpt > 0 and gain > 0 else None
    raw_est = [1e6 / (1e6 / k + m) for k, m in pts]
    cal_est = [1e6 / (1e6 / k + m / gain) for k, m in pts] if gain > 0 else []
    out.update(gain=round(gain, 3), light_k=round(light) if light else None, r2=round(r2, 4),
               residual_mired_max=round(max(abs(y - (icpt + slope * x)) for x, y in zip(xs, ys)), 1),
               light_estimates_before=[round(v) for v in raw_est], light_estimates_after=[round(v) for v in cal_est])
    out["ok"] = bool(light and r2 >= 0.9 and 0.3 <= gain <= 3.0 and 2000 <= light <= 12000)
    spread = lambda v: (round(min(v)), round(max(v))) if v else (None, None)  # noqa: E731
    out["summary"] = ("gain %.2f, light on the wall ≈ %sK, R² %.3f; light estimate across the sweep: %s-%sK before, "
                      "%s-%sK after calibration" % (gain, out["light_k"], r2, *spread(raw_est), *spread(cal_est)))
    return out


def save_wb_calibration(cal, session):
    data = json.loads(CALIBRATION_FILE.read_text())
    data["slog3"]["white_balance"] = {
        "mired_gain": cal["gain"],
        "light_k_on_wall": cal["light_k"],
        "r2": cal["r2"],
        "points": cal["points"],
        "status": "MEASURED: Color Temp swept 2800-7500K on a white wall lit by one lamp (live view, S-Log3). "
                  "The live view shows a WB error as gain x the real error, in mireds; the eyes divide by it. "
                  "Assumes the wall is neutral (off-white paint shifts the light reading, not the gain).",
        "source_session": "sessions/…_%s (not committed)" % session.name.split("_", 2)[-1],
    }
    CALIBRATION_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fake", action="store_true", help="rehearse on the fake camera (no real camera)")
    ap.add_argument("--frame", help="fake: a recorded live-view frame (ISO 1600, 1/50, f/5.6)")
    ap.add_argument("--phases", default="1,2,3")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--quick", action="store_true", help="short waits (rehearsals only)")
    args = ap.parse_args()
    test = LiveSelfTest(args)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        test.run({int(p) for p in args.phases.split(",")})
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
