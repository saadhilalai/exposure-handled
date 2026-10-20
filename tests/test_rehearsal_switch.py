"""The rehearsal recording switch: every approved exposure setting may change while recording, but only in a
live rehearsal agent take, and every layer must agree. Plus the rehearsal label and the problem log. Fake camera only."""
import json
import subprocess
import sys

import pytest

from agent.runner import RunnerError
from agent.safety import SafetyGate, load_ranges
from tests.test_recording_switch import StubCamera
from tests.test_runner import ROOT, TOO_DARK, fake, runner_for  # noqa: F401  (fake is a fixture)

TAKE = "REH_sunset_A_agent"
ON = dict(live=True, exposure=True, exposure_while_recording=True, take=TAKE, label="rehearsal")


def test_off_by_default_nothing_changes_while_recording(fake, tmp_path):
    cam, path = fake(scene_offset=TOO_DARK, exposure_while_recording=True)     # even with the bridge's flag on
    cam.recording = True
    r = runner_for(cam, path, tmp_path, live=True, exposure=True, take=TAKE, label="rehearsal")
    r.run(seconds=6)
    assert cam.sets == [] and r.state() == "RECORDING"


@pytest.mark.parametrize("change, bridge_flag, why", [
    ({}, False, "wasn't started with --allow-exposure-while-recording"),
    ({"label": None}, True, "add --rehearsal"),
    ({"take": "S1_R3_A_agent"}, True, "named REH_"),                       # a Step 7 take can never use it
    ({"take": "REH_sunset_C_manual"}, True, "rehearsal agent takes only"),
    ({"exposure": False}, True, "needs the exposure switch"),
    ({"live": False}, True, "live agent take"),
    ({"iso_while_recording": True}, True, "one recording switch"),
])
def test_switch_refuses_to_start_unless_everything_lines_up(fake, tmp_path, change, bridge_flag, why):
    cam, path = fake(scene_offset=TOO_DARK, exposure_while_recording=bridge_flag)
    with pytest.raises(RunnerError, match=why):
        runner_for(cam, path, tmp_path, **{**ON, **change})


def test_with_both_switches_on_the_agent_changes_while_recording(fake, tmp_path):
    cam, path = fake(scene_offset=TOO_DARK, exposure_while_recording=True)
    cam.recording = True
    r = runner_for(cam, path, tmp_path, **ON)
    r.run(seconds=8)
    assert r.changes and r.state() == "AUTO"
    logged = [json.loads(line) for line in (tmp_path / "session" / "changes.jsonl").read_text().splitlines()]
    assert logged and all(c["while_recording"] for c in logged)


def test_lock_still_holds_while_recording_with_the_switch_on(fake, tmp_path):
    cam, path = fake(scene_offset=TOO_DARK, exposure_while_recording=True)
    cam.recording = True
    r = runner_for(cam, path, tmp_path, **ON)
    r.hold(True)
    r.run(seconds=6)
    assert cam.sets == [] and r.state() == "LOCKED"


def test_gate_allows_every_exposure_setting_while_recording_only_with_the_switch(tmp_path, monkeypatch):
    import agent.safety as safety
    monkeypatch.setattr(safety, "within_range", lambda name, raw, rule: True)   # isolate the recording rule
    ranges, cam = load_ranges(), StubCamera()
    off = SafetyGate(cam, tmp_path / "a.jsonl", ranges, exposure=True)
    iso_only = SafetyGate(cam, tmp_path / "b.jsonl", ranges, exposure=True, iso_while_recording=True)
    no_exposure = SafetyGate(cam, tmp_path / "c.jsonl", ranges, exposure_while_recording=True)  # needs exposure too
    on = SafetyGate(cam, tmp_path / "d.jsonl", ranges, exposure=True, exposure_while_recording=True)
    assert off.change_setting("FNumber", 400, "t")["error"] == "camera is recording"
    assert iso_only.change_setting("FNumber", 400, "t")["error"] == "camera is recording"
    assert no_exposure.change_setting("IsoSensitivity", 1000, "t")["error"] == "camera is recording"
    for name, raw in (("IsoSensitivity", 1000), ("FNumber", 400), ("ShutterSpeed", (1 << 16) | 60), ("Colortemp", 5600)):
        assert on.change_setting(name, raw, "t")["ok"], name
    assert cam.sent == ["IsoSensitivity", "FNumber", "ShutterSpeed", "Colortemp"]


def test_bridge_refuses_when_its_own_flag_is_off_even_if_the_gate_allows(fake, tmp_path):
    cam, path = fake(allow_exposure=True)                                    # exposure on, recording switch off
    cam.recording = True
    r = runner_for(cam, path, tmp_path)                                       # dry run: we drive the gate by hand
    gate = SafetyGate(r.client, tmp_path / "gate.jsonl", load_ranges(), exposure=True, exposure_while_recording=True)
    reply = gate.change_setting("IsoSensitivity", 1000, "test")              # the gate says yes...
    assert reply["error"] == "camera is recording" and cam.props["IsoSensitivity"]["current"] == 800   # ...the bridge says no


def test_rehearsal_label_and_problem_log(fake, tmp_path):
    cam, path = fake()
    r = runner_for(cam, path, tmp_path, take="REH_sunset_B_auto", label="rehearsal")   # a dry-run rehearsal take
    for _ in range(30):
        r.step()
    r.problem("flicker on the face")
    r.problem()
    start = json.loads((tmp_path / "session" / "runner_log.jsonl").read_text().splitlines()[0])
    assert start["label"] == "rehearsal" and r.snapshot()["label"] == "rehearsal" and r.snapshot()["problems"] == 2
    problems = [json.loads(line) for line in (tmp_path / "session" / "problems.jsonl").read_text().splitlines()]
    assert [p["note"] for p in problems] == ["flicker on the face", ""]
    assert {"camera", "state", "status", "key_stops", "recent_events"} <= set(problems[0])


def test_launcher_refuses_the_switch_without_rehearsal():
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "run_agent.py"), "--fake", "--allow-exposure-while-recording",
                          "--seconds", "1"], capture_output=True, text=True, timeout=60)
    assert out.returncode != 0 and "rehearsals only" in out.stderr
