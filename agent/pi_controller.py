"""The agent on the Pi: one controller owns the runner and switches the bridge between its two modes.

  watching  the bridge is read-only and the agent only suggests. After a kill it's "locked": the bridge
            refuses everything, the kill-switch file keeps it that way across restarts, and the phone still
            sees the picture.
  armed     the phone armed it with the PIN and LIVE: the bridge in its normal mode (ISO only, unless the
            settings file allows exposure), the agent live with Auto off, so Auto still takes two presses.

Safety rules, all enforced here:
  - At start (power-up, or the agent restarting), the bridge is put in read-only. Nothing ever arms itself.
  - Arming needs the PIN and the word LIVE, and it's the only thing that removes the kill-switch file.
  - If arming fails anywhere, the agent ends locked and read-only, never half-armed.
  - Disarm is a kill: the bridge is locked first (and the file written), then it goes back to read-only.
  - Losing the camera or the bridge while armed drops back to read-only: arm again to carry on.
  - Losing the phone while armed (nothing from it for phone_timeout_s): Auto goes off, so the settings stay as
    they are and the agent only suggests. When the phone is back, Auto stays off until it's pressed again.
"""
import json
import os
import queue
import subprocess
import threading
import time
from datetime import datetime

from agent.bridge_client import BridgeClient
from agent.faces import FaceBook
from agent.runner import AgentRunner


class SystemdBridge:
    """On the Pi: one service per mode. They conflict, so starting one stops the other."""
    UNITS = {False: "camera-bridge.service", True: "camera-bridge-armed.service"}

    def start(self, armed):
        subprocess.run(["systemctl", "start", self.UNITS[armed]], check=True, timeout=60, capture_output=True)


def write_lock(path):
    """The same kill-switch file the bridge writes (bridge/src/bridge_args.hpp), flushed to the card."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write("locked by the kill switch\n")
        f.flush()
        os.fsync(f.fileno())
    _sync_dir(path.parent)


def remove_lock(path):
    if path.exists():
        path.unlink()
        _sync_dir(path.parent)


def _sync_dir(folder):
    fd = os.open(str(folder), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class PiController:
    def __init__(self, cfg, switch, guard, eyes=None, clock=time.monotonic, wait_s=30.0, poll_s=0.5):
        self.cfg, self.switch, self.guard, self.eyes, self.clock = cfg, switch, guard, eyes, clock
        self.wait_s, self.poll_s = wait_s, poll_s
        self.look = cfg.look
        self.mode, self.message = "starting", "Starting: waiting for the camera"
        self.runner, self.dash, self.armed = None, None, False
        self.requests = queue.Queue()
        self.mutex = threading.Lock()
        self.stop_event = threading.Event()
        self.started = False
        self.kill_during_switch = threading.Event()
        self.last_seen = None                             # the paired phone's last request (its heartbeat)
        self.faces = FaceBook(cfg.state_dir / "face_refs.json")   # on the card's data partition, never uploaded
        self.phone_lost = False
        for d in (cfg.sessions_dir, cfg.state_dir, cfg.logs_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- the phone's buttons
    def attach(self, dash):
        self.dash = dash
        dash.runner = self.runner
        dash.actions.update({"arm": self.arm, "disarm": self.disarm, "kill": self.kill})
        dash.extra_state = self.state
        dash.on_seen = self.seen

    def seen(self):
        self.last_seen = self.clock()

    def state(self):
        r = self.runner
        locked = self.cfg.lock_file.exists() or bool(r and getattr(r, "bridge_locked", False))
        return {"mode": self.mode, "message": self.message, "locked": locked, "armed": self.mode == "armed",
                "phone_lost": self.phone_lost, "health": self._health(),
                "exposure_allowed": self.cfg.allow_exposure, "pin": self.guard.enabled}

    def _health(self):
        """The latest power-and-heat reading (tools/pi_health.py, once a minute), or None."""
        try:
            return json.loads((self.cfg.state_dir / "health.json").read_text())
        except (OSError, ValueError):
            return None

    def arm(self, body):
        """PIN + LIVE (checked here, in the phone's request), then the switch happens in the main loop."""
        with self.mutex:
            if self.mode not in ("watching", "locked"):
                return 409, {"ok": False, "error": "can't arm now (%s)" % self.mode}
            if not self.guard.enabled:
                return 409, {"ok": False, "error": "set a PIN on the Pi first"}
            if str(body.get("confirm") or "") != "LIVE":
                return 400, {"ok": False, "error": "type LIVE to arm"}
            ok, error = self.guard.check(str(body.get("pin") or ""))
            if not ok:
                return 403, {"ok": False, "error": error}
            self.mode, self.message = "arming", "Arming: the bridge is switching to its normal mode"
            self.requests.put("arm")
        return 200, {"ok": True, "arming": True}

    def kill(self, body=None):
        """The kill switch, at any moment, even mid-switch when there's no runner: lock whatever bridge is up."""
        r = self.runner
        if r is not None:
            r.kill("Kill switch (phone)")
            return 200, {"ok": True}
        self.kill_during_switch.set()
        try:
            write_lock(self.cfg.lock_file)
        except OSError:
            pass
        try:
            c = BridgeClient(self.cfg.socket_path, timeout=2.0)
            try:
                c.lock()
            finally:
                c.close()
        except (OSError, ValueError):
            pass                                          # no bridge up: the file keeps the next one locked
        return 200, {"ok": True}

    def disarm(self, body=None):
        """A kill with its own reason: the bridge locks at once, then goes back to read-only."""
        r = self.runner
        if self.mode != "armed" or r is None:
            return 409, {"ok": False, "error": "not armed"}
        r.kill("Disarmed from the phone")
        return 200, {"ok": True}

    # ---------------------------------------------------------------- main loop
    def run(self):
        while not self.stop_event.is_set():
            self.tick()
        self.close()

    def tick(self):
        """One step of the main loop (tests call this directly)."""
        if not self.started:
            self.started = True
            self._to_watching(start_bridge=True)          # power-up or a restart: read-only, always
            return
        try:
            request = self.requests.get_nowait()
        except queue.Empty:
            request = None
        if request == "arm":
            return self._arm()
        r = self.runner
        if r is None:
            self._to_watching(start_bridge=False)
            if self.runner is None:
                self.stop_event.wait(self.poll_s)
            return
        if not r.step():
            return self._runner_stopped(r)
        if self.mode == "armed":
            self._watch_phone(r)

    def _watch_phone(self, r):
        now = self.clock()
        gone = self.last_seen is None or now - self.last_seen > self.cfg.phone_timeout_s
        if gone and not self.phone_lost:
            self.phone_lost = True
            if r.live and not r.paused and not r.killed:
                r.set_auto(False)
                r.note("phone", "The phone dropped off: Auto off, holding the settings. Press Auto to carry on.")
            self.message = "The phone dropped off: Auto is off and the settings are held."
        elif not gone and self.phone_lost:
            self.phone_lost = False
            self.message = "The phone is back. Auto stays off until you press it."
        elif gone and r.live and not r.paused and not r.killed:
            r.set_auto(False)                             # Auto turned on from elsewhere while the phone is gone

    def close(self):
        r, self.runner = self.runner, None
        if self.dash:
            self.dash.runner = None
        if r is not None:
            self._end(r)

    # ---------------------------------------------------------------- switching
    def _set_runner(self, r):
        self.runner = r
        if self.dash:
            self.dash.runner = r

    def _end(self, r):
        self.look = r.brain.look.key if hasattr(r, "brain") else self.look
        try:
            r.finish()
        finally:
            r.close()

    def _wait_bridge(self, read_only):
        deadline = self.clock() + self.wait_s
        while True:
            try:
                c = BridgeClient(self.cfg.socket_path, timeout=5.0)
                try:
                    status = c.status()
                finally:
                    c.close()
                if status.get("ok") and status.get("connected") and bool(status.get("read_only")) == read_only:
                    return status
            except (OSError, ValueError, KeyError):
                pass
            if self.clock() >= deadline or self.stop_event.is_set():
                return None
            self.stop_event.wait(self.poll_s)

    def _new_runner(self, live):
        name = "%s_%s" % (datetime.now().strftime("%Y-%m-%d_%H%M%S"), "pi-armed" if live else "pi-watch")
        r = AgentRunner(self.cfg.socket_path, self.cfg.sessions_dir / name, look=self.look, live=live, eyes=self.eyes, faces=self.faces,
                        clock=self.clock, auto=False, exposure=live and self.cfg.allow_exposure, watch_locked=not live,
                        max_fps=self.cfg.max_fps, half_size=self.cfg.half_size)
        r.start()
        return r

    def _to_watching(self, start_bridge):
        self.armed = False
        if start_bridge:
            try:
                self.switch.start(armed=False)
            except Exception as e:
                self.mode, self.message = "starting", "Couldn't start the read-only bridge (%s): retrying" % e
                return
        status = self._wait_bridge(read_only=True)
        if status is None:
            self.mode, self.message = "starting", "Waiting for the camera (plugged in, on, USB mode Remote Shoot)"
            return
        try:
            self._set_runner(self._new_runner(live=False))
        except Exception as e:
            self.mode, self.message = "starting", "The agent couldn't start (%s): retrying" % e
            return
        locked = bool(status.get("locked"))
        self.mode = "locked" if locked else "watching"
        self.message = ("Kill switch on: nothing can change. Arm from the phone (PIN + LIVE) to carry on." if locked
                        else "Watching: read-only, suggesting only. Arm from the phone (PIN + LIVE) to let it change ISO.")

    def _arm(self):
        self.kill_during_switch.clear()
        r = self.runner
        self._set_runner(None)
        if r is not None:
            self._end(r)
        try:
            remove_lock(self.cfg.lock_file)               # the only place an old kill is cleared
            self.switch.start(armed=True)
            status = self._wait_bridge(read_only=False)
            if status is None or status.get("locked"):
                raise RuntimeError("the bridge didn't come back ready")
            if self.kill_during_switch.is_set():
                raise RuntimeError("the kill switch was pressed")
            self._set_runner(self._new_runner(live=True))
            if self.kill_during_switch.is_set():
                raise RuntimeError("the kill switch was pressed")
        except Exception as e:
            return self._fail_safe("Arming failed (%s)" % e)
        self.armed = True
        self.last_seen, self.phone_lost = self.clock(), False   # the phone just armed it
        self.mode = "armed"
        self.message = "Armed: the agent may change %s. Auto is off: press Auto to start." % (
            "ISO, aperture, shutter and WB" if self.cfg.allow_exposure else "ISO")

    def _fail_safe(self, why):
        """Anything unexpected while armed or arming: locked and read-only, never half-armed."""
        r = self.runner
        self._set_runner(None)
        if r is not None:
            try:
                r.kill(why)
            finally:
                self._end(r)
        try:
            write_lock(self.cfg.lock_file)
        except OSError:
            pass                                          # the read-only bridge refuses changes anyway
        self._to_watching(start_bridge=True)
        self.message = "%s: locked and read-only. Arm again to carry on." % why
        if self.runner is not None:
            self.mode = "locked"

    def _runner_stopped(self, r):
        was_armed = self.armed
        self._set_runner(None)
        killed = r.killed
        self._end(r)
        if killed:                                        # kill switch, disarm, runaway guard: the bridge is locked
            self._to_watching(start_bridge=was_armed)
            if self.runner is not None:
                self.mode = "locked"
                self.message = "%s: the bridge is locked. Arm from the phone (PIN + LIVE) to carry on." % (
                    r.kill_reason or "Kill switch")
        elif was_armed:                                   # lost the camera or the bridge while armed
            self._to_watching(start_bridge=True)
            if self.runner is not None:
                self.message = "Lost the camera while armed: back to read-only. Arm again to carry on."
        else:
            self.mode, self.message = "starting", "Lost the camera: waiting for it"
