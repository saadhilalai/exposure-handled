"""The Step 7 recording switch: ISO only, agent takes only, and every layer must agree. Fake camera only."""
import json

import pytest

from agent.runner import RunnerError
from agent.safety import SafetyGate, load_ranges
from tests.test_runner import TOO_DARK, fake, runner_for  # noqa: F401  (fake is a fixture)

TAKE = "S1_R3_A_agent"


def test_off_by_default_nothing_changes_while_recording(fake, tmp_path):
    cam, path = fake(scene_offset=TOO_DARK, iso_while_recording=True)    # even with the bridge's flag on
    cam.recording = True
    r = runner_for(cam, path, tmp_path, live=True)
    r.run(seconds=6)
    assert cam.sets == [] and r.state() == "RECORDING"


@pytest.mark.parametrize("kw, why", [
    ({"take": TAKE}, "wasn't started with --allow-iso-while-recording"),        # bridge flag off
    ({"take": None}, "agent takes only"),
    ({"take": "S1_R3_A_manual"}, "agent takes only"),
])
def test_switch_refuses_to_start_unless_everything_lines_up(fake, tmp_path, kw, why):
    cam, path = fake(scene_offset=TOO_DARK, iso_while_recording=kw.get("take") is None or "manual" in kw["take"])
    with pytest.raises(RunnerError, match=why):
        runner_for(cam, path, tmp_path, live=True, iso_while_recording=True, **kw)


def test_switch_needs_live(fake, tmp_path):
    cam, path = fake(iso_while_recording=True)
    with pytest.raises(RunnerError, match="live agent take"):
        runner_for(cam, path, tmp_path, iso_while_recording=True, take=TAKE)


def test_with_both_switches_on_the_agent_changes_iso_while_recording(fake, tmp_path):
    cam, path = fake(scene_offset=TOO_DARK, iso_while_recording=True)
    cam.recording = True
    r = runner_for(cam, path, tmp_path, live=True, iso_while_recording=True, take=TAKE)
    r.run(seconds=8)
    assert r.changes and {name for _, name, _ in cam.sets} == {"IsoSensitivity"}
    logged = [json.loads(line) for line in (tmp_path / "session" / "changes.jsonl").read_text().splitlines()]
    assert all(c["while_recording"] for c in logged) and r.state() == "AUTO"


def test_lock_still_holds_while_recording_with_the_switch_on(fake, tmp_path):
    cam, path = fake(scene_offset=TOO_DARK, iso_while_recording=True)
    cam.recording = True
    r = runner_for(cam, path, tmp_path, live=True, iso_while_recording=True, take=TAKE)
    r.hold(True)
    r.run(seconds=6)
    assert cam.sets == [] and r.state() == "LOCKED"


class StubCamera:
    """Answers the gate's questions: the camera is recording; counts what reaches it."""
    def __init__(self):
        self.sent = []

    def get(self, name, rec):
        return {name: {"current": 280 if name == "FNumber" else 800}, rec: {"current": 1}}

    def _set_raw(self, name, raw):
        self.sent.append(name)
        return {"ok": True, "changed": True}


def test_gate_allows_only_iso_while_recording(tmp_path, monkeypatch):
    import agent.safety as safety
    monkeypatch.setattr(safety, "within_range", lambda name, raw, rule: True)   # isolate the recording rule
    ranges = load_ranges()
    cam = StubCamera()
    off = SafetyGate(cam, tmp_path / "a.jsonl", ranges)
    on = SafetyGate(cam, tmp_path / "b.jsonl", ranges, iso_while_recording=True, exposure=True)  # aperture approved too
    assert off.change_setting("IsoSensitivity", 1000, "t")["error"] == "camera is recording"
    assert on.change_setting("FNumber", 400, "t")["error"] == "camera is recording"
    assert on.change_setting("IsoSensitivity", 1000, "t")["ok"]
    assert cam.sent == ["IsoSensitivity"]


def test_bridge_refuses_when_its_own_flag_is_off_even_if_the_gate_allows(fake, tmp_path):
    cam, path = fake(iso_while_recording=False)
    cam.recording = True
    r = runner_for(cam, path, tmp_path)                                       # dry run: we drive the gate by hand
    gate = SafetyGate(r.client, tmp_path / "gate.jsonl", load_ranges(), iso_while_recording=True)
    reply = gate.change_setting("IsoSensitivity", 1000, "test")              # the gate says yes...
    assert reply["error"] == "camera is recording" and cam.props["IsoSensitivity"]["current"] == 800   # ...the bridge says no
