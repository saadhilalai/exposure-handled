"""The runner (eyes → brain → safety gate → bridge) against the fake camera. No real camera."""
import json
import uuid
from pathlib import Path

import pytest

from agent.brain import Output, Proposal
from agent.bridge_client import BridgeClient
from agent.eyes import Eyes
from agent.looks import LOOKS
from agent.runner import MAX_CHANGES_PER_MIN, AgentRunner, RunnerError
from tools.fake_bridge import FakeCamera, serve

ROOT = Path(__file__).resolve().parent.parent
TOO_DARK = -2.0     # the made-up scene 2 stops darker: key about -2.5 st at ISO 800, 1/160, f/2.8


@pytest.fixture
def fake():
    """Start fake cameras on short socket paths (macOS caps socket paths at 104 characters)."""
    servers = []

    def start(**kw):
        kw.setdefault("size", (512, 288))
        kw.setdefault("realtime", False)          # time moves 1/24 s per frame: fast, repeatable
        cam = FakeCamera(**kw)
        path = ROOT / "run" / ("test-%s.sock" % uuid.uuid4().hex[:8])
        servers.append((serve(cam, path), path))
        return cam, path

    yield start
    for server, path in servers:
        server.shutdown()
        server.server_close()
        path.unlink(missing_ok=True)


def runner_for(cam, path, tmp_path, **kw):
    eyes = Eyes(face_model=ROOT / "no-face-model")               # the made-up scene has no faces: skip detection
    r = AgentRunner(path, tmp_path / "session", clock=cam.clock, eyes=eyes, **kw)
    r.start()
    return r


def until_first_change(r, max_frames=24 * 20):
    for _ in range(max_frames):
        assert r.step()
        if r.changes:
            return
    pytest.fail("no change within %d frames" % max_frames)


def log(tmp_path, name):
    f = tmp_path / "session" / name
    return [json.loads(line) for line in f.read_text().splitlines()] if f.exists() else []


def test_dry_run_sends_nothing_and_says_what_it_would_do(fake, tmp_path):
    cam, path = fake(scene_offset=TOO_DARK)
    r = runner_for(cam, path, tmp_path)
    r.run(seconds=4)
    assert cam.sets == []
    would = [e for e in log(tmp_path, "runner_log.jsonl") if e["event"] == "would_change"]
    assert would and would[0]["setting"] == "IsoSensitivity"
    assert log(tmp_path, "changes.jsonl") == []
    assert (tmp_path / "session" / "settings_start.json").exists()


def test_live_changes_only_iso_and_logs_a_reason_for_each(fake, tmp_path):
    cam, path = fake(scene_offset=TOO_DARK)
    r = runner_for(cam, path, tmp_path, live=True)
    r.run(seconds=15)
    assert r.changes and {name for _, name, _ in cam.sets} == {"IsoSensitivity"}
    assert all(800 <= raw <= 12800 for _, _, raw in cam.sets)
    changes = log(tmp_path, "changes.jsonl")
    assert len(changes) == len(r.changes)
    assert all(c["event"] == "change" and c["reason"] and c["old"] and c["new"] for c in changes)
    assert -1.0 - 0.35 <= r.report.key_stops <= 1.0             # brought into the cinematic window
    advice = " | ".join(e["text"] for e in log(tmp_path, "runner_log.jsonl") if e["event"] == "advice")
    assert "not approved yet: 180° shutter" in advice
    assert len(list((tmp_path / "session" / "frames").glob("change_*.jpg"))) == len(r.changes)


def test_kill_switch_locks_the_bridge_and_nothing_more_is_sent(fake, tmp_path):
    cam, path = fake(scene_offset=TOO_DARK)
    r = runner_for(cam, path, tmp_path, live=True)
    until_first_change(r)
    r.kill("Kill switch (test)")
    sent = len(cam.sets)
    assert cam.locked and r.killed and not r.step()
    assert r.gate.change_setting("IsoSensitivity", 1000, "test")["refused"]
    assert len(cam.sets) == sent                                  # the gate refused before the bridge
    assert BridgeClient(path).command("set IsoSensitivity 1000")["error"] == "kill switch is on (bridge locked)"
    r.finish()
    assert r.restorable == []                                     # locked: the director restores by hand


class Flapper:
    """A broken brain that wants a change on every frame."""
    look = LOOKS["cinematic"]

    def __init__(self):
        self.n = 0

    def update(self, obs, cam):
        self.n += 1
        iso = 1000 if self.n % 2 else 800
        return Output(Proposal("IsoSensitivity", iso, "", "ISO %d" % iso, "flap %d" % self.n), [], "flapping")


def test_runaway_guard_trips_the_kill_switch(fake, tmp_path):
    cam, path = fake()
    r = runner_for(cam, path, tmp_path, live=True)
    r.brain = Flapper()
    for _ in range(MAX_CHANGES_PER_MIN + 5):
        if not r.step():
            break
    assert r.killed and r.kill_reason.startswith("Runaway guard") and cam.locked
    assert len(r.changes) == MAX_CHANGES_PER_MIN


def test_live_mode_refuses_a_read_only_bridge(fake, tmp_path):
    cam, path = fake(read_only=True)
    with pytest.raises(RunnerError, match="read-only"):
        runner_for(cam, path, tmp_path, live=True)
    runner_for(cam, path, tmp_path).run(seconds=1)               # watching is fine
    assert cam.sets == []


def test_lock_from_another_terminal_stops_the_runner(fake, tmp_path):
    cam, path = fake(scene_offset=TOO_DARK)
    r = runner_for(cam, path, tmp_path, live=True)
    r.run(seconds=0.5)
    BridgeClient(path).lock()                                     # what tools/kill_switch.py does
    r.run(seconds=3)
    assert r.killed and "outside" in r.kill_reason and r.changes == []


def test_no_changes_while_the_camera_records(fake, tmp_path):
    cam, path = fake(scene_offset=TOO_DARK)
    cam.recording = True
    r = runner_for(cam, path, tmp_path, live=True)
    r.run(seconds=6)
    assert cam.sets == [] and "recording" in r.output.status


def test_a_refused_change_pauses_the_agent(fake, tmp_path):
    cam, path = fake(scene_offset=TOO_DARK)
    cam.props["IsoSensitivity"]["can_set_now"] = False
    r = runner_for(cam, path, tmp_path, live=True)
    r.run(seconds=8)
    assert len(cam.sets) == 1 and r.paused and r.changes == []


def test_session_end_restores_the_starting_iso_through_the_gate(fake, tmp_path):
    cam, path = fake(scene_offset=TOO_DARK)
    r = runner_for(cam, path, tmp_path, live=True)
    until_first_change(r)
    r.stop()
    diffs = r.finish()
    assert [(d["setting"], d["by"]) for d in diffs] == [("IsoSensitivity", "agent")]
    assert r.restorable
    r.restore()
    assert cam.props["IsoSensitivity"]["current"] == 800
    assert "restoring" in log(tmp_path, "changes.jsonl")[-1]["reason"]
    assert (tmp_path / "session" / "settings_end.json").exists()
