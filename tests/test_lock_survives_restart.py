"""The kill switch outlives a restart when the bridge has a lock file (the Pi restarts the bridge by itself after a
crash, and that must never quietly undo a kill). Fake camera only."""
import uuid
from pathlib import Path

import pytest

from agent.bridge_client import BridgeClient
from agent.eyes import Eyes
from agent.runner import AgentRunner, RunnerError
from tools.fake_bridge import FakeCamera, serve

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def fake():
    servers = []

    def start(**kw):
        kw.setdefault("size", (512, 288))
        kw.setdefault("realtime", False)
        cam = FakeCamera(**kw)
        path = ROOT / "run" / ("test-%s.sock" % uuid.uuid4().hex[:8])
        servers.append((serve(cam, path), path))
        return cam, path

    yield start
    for server, path in servers:
        server.shutdown()
        server.server_close()
        path.unlink(missing_ok=True)


def test_a_kill_is_written_down_and_survives_a_restart(fake, tmp_path):
    lock = tmp_path / "locked"
    cam, path = fake(lock_file=lock)
    assert BridgeClient(path).status()["lock_file"] and not lock.exists()
    reply = BridgeClient(path).lock()
    assert reply["locked"] and reply["kept_after_restart"] and lock.exists()

    cam2, path2 = fake(lock_file=lock)                           # the "restarted" bridge
    status = BridgeClient(path2).status()
    assert status["locked"] and status["lock_file"]
    iso = cam2.props["IsoSensitivity"]["current"]
    assert BridgeClient(path2).command("set IsoSensitivity 1000")["error"] == "kill switch is on (bridge locked)"
    assert cam2.props["IsoSensitivity"]["current"] == iso        # refused, unchanged
    assert lock.exists()                                         # nothing in the bridge removes it


def test_the_agent_wont_start_against_a_kill_from_before(fake, tmp_path):
    lock = tmp_path / "locked"
    lock.write_text("locked by the kill switch\n")
    cam, path = fake(lock_file=lock)
    eyes = Eyes(face_model=ROOT / "no-face-model")
    for live in (False, True):
        with pytest.raises(RunnerError, match="still on from before"):
            AgentRunner(path, tmp_path / ("session-%s" % live), clock=cam.clock, eyes=eyes, live=live).start()
    assert cam.sets == []                                        # it never even asked


def test_without_a_lock_file_nothing_changes(fake, tmp_path):
    cam, path = fake()
    assert BridgeClient(path).status()["lock_file"] is False
    reply = BridgeClient(path).lock()
    assert reply["locked"] and reply["kept_after_restart"] is None
    cam2, path2 = fake()                                         # the Mac's behaviour: a restart unlocks
    assert not BridgeClient(path2).status()["locked"]


def test_a_lock_file_that_cant_be_written_still_locks(fake, tmp_path):
    cam, path = fake(lock_file=tmp_path / "no-such-folder" / "locked")
    reply = BridgeClient(path).lock()
    assert reply["locked"] and reply["kept_after_restart"] is False
    assert BridgeClient(path).command("set IsoSensitivity 1000")["error"] == "kill switch is on (bridge locked)"
