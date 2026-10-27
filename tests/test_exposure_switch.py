"""The exposure switch (director): aperture f/2.8-f/11, shutter 1/48-1/100 and WB
(Auto or Color Temp 2800-7500K) may change too, but only with the switch on in BOTH layers.
Off by default: ISO only. Also checks that the compiled C++ allow-list and the Python ranges agree."""
import os
import subprocess
from pathlib import Path

import pytest

from agent.runner import AgentRunner, RunnerError, approved_settings
from agent.safety import SafetyGate, load_ranges, within_range
from tools.fake_bridge import FakeCamera, serve

ROOT = Path(__file__).resolve().parent.parent
BRIDGES = [p for p in (ROOT / "build" / "bridge" / "camera_bridge", ROOT / "build" / "bridge-next" / "camera_bridge")
           if p.exists()]


def shutter(den, num=1):
    return (num << 16) | den


VECTORS = [
    ("IsoSensitivity", 800, True), ("IsoSensitivity", 12800, True), ("IsoSensitivity", 640, False),
    ("IsoSensitivity", 16000, False), ("IsoSensitivity", 0xFFFFFF, False), ("IsoSensitivity", 0x10000000 | 1600, False),
    ("FNumber", 280, True), ("FNumber", 560, True), ("FNumber", 1100, True), ("FNumber", 250, False),
    ("FNumber", 1300, False), ("FNumber", 0xFFFE, False),
    ("ShutterSpeed", shutter(48), True), ("ShutterSpeed", shutter(50), True), ("ShutterSpeed", shutter(96), True),
    ("ShutterSpeed", shutter(100), True), ("ShutterSpeed", shutter(40), False), ("ShutterSpeed", shutter(125), False),
    ("ShutterSpeed", shutter(160), False), ("ShutterSpeed", shutter(10), False),          # 0.1"
    ("ShutterSpeed", shutter(10, 10), False), ("ShutterSpeed", 0, False),                # 1", Bulb
    ("ShutterSpeed", 0xFFFFFFFF, False), ("ShutterSpeed", shutter(96, 2), True),          # 2/96 = 1/48
    ("Colortemp", 2800, True), ("Colortemp", 7500, True), ("Colortemp", 2700, False), ("Colortemp", 7600, False),
    ("WhiteBalance", 0x0000, True), ("WhiteBalance", 0x0100, True), ("WhiteBalance", 0x0011, False),   # Daylight
    ("WhiteBalance", 0x0101, False), ("WhiteBalance", 0x0013, False),                    # Custom 1, Cloudy
    ("FocusMode", 1, False), ("MonitorLUTSetting", 2, False),
]


def test_python_ranges_match_the_director_approvals():
    ranges = load_ranges()
    for name, raw, allowed in VECTORS:
        rule = ranges.get(name)
        ok = bool(rule and rule.get("change_allowed") and within_range(name, raw, rule))
        assert ok == allowed, (name, raw)


@pytest.mark.skipif(not BRIDGES, reason="bridge not built")
@pytest.mark.parametrize("binary", BRIDGES, ids=lambda p: p.parent.name)
def test_compiled_bridge_rules_match(binary):
    """The real C++ rule_allows(), run without any camera (--check-rules exits before the SDK starts)."""
    if subprocess.run([str(binary), "--check-rules"], input="", capture_output=True, timeout=10).returncode != 0:
        pytest.skip("this build has no --check-rules")
    feed = "".join("%s %d\n" % (n, r) for n, r, _ in VECTORS)
    out = subprocess.run([str(binary), "--check-rules"], input=feed, capture_output=True, text=True, timeout=10,
                         cwd=binary.parent, env=dict(os.environ)).stdout.split("\n")
    got = {(n, int(r)): v == "1" for n, r, v in (line.split() for line in out if line)}
    for name, raw, allowed in VECTORS:
        assert got[(name, raw)] == allowed, (name, raw)


def test_only_iso_without_the_switch():
    ranges = load_ranges()
    assert approved_settings(ranges) == {"IsoSensitivity"}
    assert approved_settings(ranges, exposure=True) == {"IsoSensitivity", "FNumber", "ShutterSpeed", "Colortemp",
                                                        "WhiteBalance"}


class Stub:
    def __init__(self):
        self.sent = []

    def get(self, name, rec):
        return {name: {"current": 0}, rec: {"current": 0}}

    def _set_raw(self, name, raw):
        self.sent.append((name, raw))
        return {"ok": True, "changed": True}


def test_gate_refuses_exposure_settings_unless_switched_on(tmp_path):
    cam = Stub()
    off = SafetyGate(cam, tmp_path / "a.jsonl")
    on = SafetyGate(cam, tmp_path / "b.jsonl", exposure=True)
    for name, raw in (("FNumber", 400), ("ShutterSpeed", shutter(48)), ("WhiteBalance", 0x0100), ("Colortemp", 3200)):
        assert off.change_setting(name, raw, "t")["error"] == "only ISO may change (exposure switch is off)"
        assert on.change_setting(name, raw, "t")["ok"]
    assert on.change_setting("FNumber", 1300, "t")["error"] == "outside the approved range"
    assert on.change_setting("WhiteBalance", 0x0011, "t")["error"] == "outside the approved range"
    assert on.change_setting("FocusMode", 1, "t")["error"] == "not approved for changes"
    assert [n for n, _ in cam.sent] == ["FNumber", "ShutterSpeed", "WhiteBalance", "Colortemp"]


@pytest.fixture
def fake(tmp_path):
    servers = []

    def make(**kw):
        cam = FakeCamera(realtime=False, iso=1600, shutter=50, fnumber=5.6, **kw)
        path = Path("/tmp") / ("ca-exp-%d.sock" % os.getpid())
        servers.append(serve(cam, path))
        return cam, path

    yield make
    for s in servers:
        s.shutdown()
        s.server_close()


def test_runner_needs_the_bridge_switch_too(fake, tmp_path):
    cam, path = fake(allow_exposure=False)
    r = AgentRunner(path, tmp_path / "s", live=True, exposure=True)
    with pytest.raises(RunnerError, match="allow-exposure"):
        r.start()
    r.close()


def test_bridge_refuses_aperture_when_its_switch_is_off_even_if_the_gate_allows(fake, tmp_path):
    cam, path = fake(allow_exposure=False)
    r = AgentRunner(path, tmp_path / "s")                                    # dry run: drive a gate by hand
    gate = SafetyGate(r.client, tmp_path / "g.jsonl", exposure=True)
    reply = gate.change_setting("FNumber", 400, "test")
    assert reply["refused"] and "allow-exposure" in reply["error"] and cam.props["FNumber"]["current"] == 560
    r.close()


def test_color_temp_needs_color_temp_mode_and_comes_back(fake, tmp_path):
    cam, path = fake(allow_exposure=True)
    r = AgentRunner(path, tmp_path / "s")
    gate = SafetyGate(r.client, tmp_path / "g.jsonl", exposure=True)
    assert gate.change_setting("Colortemp", 3200, "t")["error"] == "camera says this setting can't be changed right now"
    assert gate.change_setting("WhiteBalance", 0x0100, "t")["ok"]
    assert gate.change_setting("Colortemp", 3250, "t")["error"] == "camera doesn't offer this value right now"
    assert gate.change_setting("Colortemp", 3200, "t")["ok"]
    assert gate.change_setting("WhiteBalance", 0x0000, "t")["ok"]
    assert cam.props["Colortemp"]["current"] == 0 and cam.remembered_k == 3200
    r.close()


def test_wb_calibration_fit_recovers_gain_and_light():
    from tools.live_selftest import fit_wb
    gain, light = 0.92, 2620
    pts = [(k, gain * (1e6 / light - 1e6 / k)) for k in (2800, 3200, 3700, 4300, 5000, 5600, 6500, 7500)]
    cal = fit_wb(pts)
    assert cal["ok"] and abs(cal["gain"] - gain) < 0.01 and abs(cal["light_k"] - light) < 10
    assert max(cal["light_estimates_after"]) - min(cal["light_estimates_after"]) < 5
    assert not fit_wb(pts[:3])["ok"]
