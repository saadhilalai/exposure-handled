"""The Pi's controller (agent/pi_controller.py): read-only at start, armed only with the PIN and LIVE, a kill always
locks and drops back to read-only, and nothing ever arms itself. Fake camera only; no real camera."""
import json
import shutil
import uuid
from pathlib import Path

import pytest

from agent.config import parse
from agent.dashboard import Dashboard
from agent.eyes import Eyes
from agent.pi_controller import PiController
from agent.pin import PinGuard, hash_pin
from tests.test_pin import call
from tests.test_runner import TOO_DARK
from tools.fake_bridge import FakeCamera, serve

ROOT = Path(__file__).resolve().parent.parent
PIN = "482915"


class FakeSwitch:
    """Stands in for the two systemd services: each start() restarts the fake camera in that mode."""

    def __init__(self, cfg):
        self.cfg, self.server, self.cam, self.starts, self.fail_armed, self.during_armed = cfg, None, None, [], False, None
        cfg.run_dir.mkdir(parents=True, exist_ok=True)

    def start(self, armed):
        self.starts.append(armed)
        self.stop()
        if armed and self.fail_armed:
            raise RuntimeError("the armed service didn't start")
        if armed and self.during_armed:
            self.during_armed()
        self.cam = FakeCamera(size=(256, 144), realtime=False, scene_offset=TOO_DARK, read_only=not armed,
                              allow_exposure=armed and self.cfg.allow_exposure, lock_file=self.cfg.lock_file)
        self.server = serve(self.cam, self.cfg.socket_path)

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        self.cfg.socket_path.unlink(missing_ok=True)


@pytest.fixture
def pi(tmp_path):
    run_dir = ROOT / "run" / ("pc-%s" % uuid.uuid4().hex[:6])          # macOS caps socket paths at 104 characters
    made = []

    def make(extra=""):
        cfg = parse('[paths]\ndata_dir = "%s"\nrun_dir = "%s"\n%s' % (tmp_path / "data", run_dir, extra))
        switch = FakeSwitch(cfg)
        c = PiController(cfg, switch, PinGuard(hash_pin(PIN, iterations=1000), cfg.paired_file),
                         eyes=Eyes(face_model=ROOT / "no-face-model"), wait_s=3.0, poll_s=0.02)
        made.append((c, switch))
        return c, switch, cfg

    yield make
    for c, switch in made:
        c.close()
        switch.stop()
    shutil.rmtree(run_dir, ignore_errors=True)


def ticks(c, n=10):
    for _ in range(n):
        c.tick()


def armed(c, switch):
    ticks(c, 1)
    assert c.arm({"pin": PIN, "confirm": "LIVE"})[0] == 200
    ticks(c, 2)
    assert c.mode == "armed"


def test_it_starts_read_only_and_only_suggests(pi):
    c, switch, cfg = pi()
    ticks(c, 30)
    assert switch.starts == [False] and c.mode == "watching" and not c.runner.live
    assert switch.cam.read_only and switch.cam.sets == []
    assert c.state()["locked"] is False and c.state()["armed"] is False


def test_arming_needs_the_pin_and_live(pi):
    c, switch, cfg = pi()
    ticks(c, 1)
    assert c.arm({"pin": "000000", "confirm": "LIVE"})[0] == 403
    assert c.arm({"pin": PIN, "confirm": "live"})[0] == 400
    assert c.arm({"pin": PIN})[0] == 400
    assert c.mode == "watching" and switch.starts == [False]
    assert c.arm({"pin": PIN, "confirm": "LIVE"})[0] == 200
    ticks(c, 1)
    assert c.mode == "armed" and switch.starts == [False, True]
    assert c.runner.live and c.runner.paused                    # Auto is off: still two presses on the phone
    assert not switch.cam.read_only and not c.runner.exposure   # ISO only: the file doesn't allow exposure
    assert c.arm({"pin": PIN, "confirm": "LIVE"})[0] == 409     # already armed


def test_exposure_only_when_the_settings_file_allows_it(pi):
    c, switch, cfg = pi("[bridge]\nallow_exposure = true\n")
    armed(c, switch)
    assert c.runner.exposure and switch.cam.allow_exposure


def test_a_kill_locks_survives_and_drops_back_to_read_only(pi):
    c, switch, cfg = pi()
    armed(c, switch)
    assert c.kill()[0] == 200
    ticks(c, 2)
    assert c.mode == "locked" and switch.starts == [False, True, False]
    assert cfg.lock_file.exists() and switch.cam.locked and switch.cam.read_only
    assert c.runner is not None and not c.runner.live          # the phone still sees the picture
    assert c.state()["locked"]


def test_disarm_is_a_kill(pi):
    c, switch, cfg = pi()
    armed(c, switch)
    assert c.disarm()[0] == 200
    ticks(c, 2)
    assert c.mode == "locked" and cfg.lock_file.exists() and switch.cam.read_only
    assert c.disarm()[0] == 409


def test_arming_clears_an_old_kill_and_nothing_else_does(pi):
    c, switch, cfg = pi()
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    cfg.lock_file.write_text("locked by the kill switch\n")
    ticks(c, 20)
    assert c.mode == "locked" and switch.cam.locked and cfg.lock_file.exists()
    assert c.runner.bridge_locked and switch.cam.sets == []
    assert c.arm({"pin": PIN, "confirm": "LIVE"})[0] == 200
    ticks(c, 1)
    assert c.mode == "armed" and not cfg.lock_file.exists() and not switch.cam.locked


def test_a_failed_arm_ends_locked_and_read_only(pi):
    c, switch, cfg = pi()
    ticks(c, 1)
    switch.fail_armed = True
    c.arm({"pin": PIN, "confirm": "LIVE"})
    ticks(c, 1)
    assert c.mode == "locked" and "Arming failed" in c.message
    assert cfg.lock_file.exists() and switch.cam.read_only and switch.cam.locked


def test_the_kill_switch_works_mid_switch(pi):
    c, switch, cfg = pi()
    ticks(c, 1)
    switch.during_armed = lambda: c.kill()                      # pressed while there's no runner at all
    c.arm({"pin": PIN, "confirm": "LIVE"})
    ticks(c, 1)
    assert c.mode == "locked" and cfg.lock_file.exists() and switch.cam.read_only


def test_losing_the_camera_while_armed_goes_back_to_read_only(pi):
    c, switch, cfg = pi()
    armed(c, switch)

    def gone(*a, **kw):
        raise ConnectionError("camera unplugged")
    c.runner.client.frame = gone
    ticks(c, 2)
    assert c.mode == "watching" and switch.starts[-1] is False and switch.cam.read_only
    assert "Lost the camera while armed" in c.message


def test_a_restart_never_arms_itself(pi):
    c, switch, cfg = pi()
    armed(c, switch)
    c.close()                                                   # the agent restarts (crash, update, power)
    c2 = PiController(cfg, switch, c.guard, eyes=c.eyes, wait_s=3.0, poll_s=0.02)
    ticks(c2, 1)
    assert switch.starts[-1] is False and c2.mode == "watching" and not c2.runner.live
    c2.close()


def test_the_phone_sees_the_pi_state_and_arming_needs_pairing(pi):
    c, switch, cfg = pi()
    dash = Dashboard(None, port=0, guard=c.guard).start()
    c.attach(dash)
    try:
        assert call(dash, "/api/arm", {"pin": PIN, "confirm": "LIVE"})[0] == 401   # not paired
        ticks(c, 1)
        cookie = call(dash, "/api/pair", {"pin": PIN})[2]["Set-Cookie"].split(";")[0]
        code, body, _ = call(dash, "/api/state", cookie=cookie)
        assert code == 200 and json.loads(body)["pi"]["mode"] == "watching"
        assert call(dash, "/api/arm", {"pin": PIN, "confirm": "LIVE"}, cookie=cookie)[0] == 200
        assert json.loads(call(dash, "/api/state", cookie=cookie)[1])["pi"]["mode"] == "arming"
        ticks(c, 1)
        assert json.loads(call(dash, "/api/state", cookie=cookie)[1])["pi"]["mode"] == "armed"
        assert call(dash, "/api/kill", {})[0] == 200                               # unpaired, still works
        ticks(c, 2)
        assert c.mode == "locked"
    finally:
        dash.stop()
