"""The Pi's settings file (agent/config.py): Mac defaults with no file, strict about typos and wrong types."""
from pathlib import Path

import pytest

from agent import config
from agent.config import ConfigError, bridge_argv, load, parse

ROOT = Path(__file__).resolve().parent.parent


def test_no_file_means_the_mac_defaults(monkeypatch, tmp_path):
    monkeypatch.delenv("CAMERA_AGENT_CONFIG", raising=False)
    monkeypatch.setattr(config, "SYSTEM_FILE", tmp_path / "missing.toml")
    c = load()
    assert c.source == "defaults"
    assert c.host == "127.0.0.1" and c.port == 8770 and c.allow_exposure is False
    assert c.socket_path == ROOT / "run" / "bridge.sock"
    assert c.binary == ROOT / "build" / "bridge" / "camera_bridge"
    assert c.sessions_dir == ROOT / "sessions"


def test_the_example_file_is_valid_and_matches_the_plan():
    c = load(ROOT / "config" / "pi.example.toml")
    assert c.host == "10.42.0.1" and c.names == ["camera-pi.local"] and c.band == "bg"
    assert c.allow_exposure is False and c.pin_hash == ""
    assert c.lock_file == Path("/data/camera-agent/state/locked")
    assert c.socket_path == Path("/run/camera-agent/bridge.sock")


def test_env_variable_points_at_a_file(monkeypatch, tmp_path):
    f = tmp_path / "c.toml"
    f.write_text('[dashboard]\nport = 9000\n')
    monkeypatch.setenv("CAMERA_AGENT_CONFIG", str(f))
    assert load().port == 9000


@pytest.mark.parametrize("text, words", [
    ("[dashbord]\nport = 1\n", "unknown section"),
    ("[dashboard]\nprot = 8770\n", "unknown setting"),
    ("[bridge]\nallow_exposure = \"yes\"\n", "true or false"),
    ("[dashboard]\nport = true\n", "whole number"),
    ("[dashboard]\nport = 70000\n", "1-65535"),
    ("[agent]\nlook = \"moody\"\n", "look must be"),
    ("[hotspot]\nband = \"6GHz\"\n", "band must be"),
    ("[agent]\nphone_timeout_s = 0.1\n", "1-60"),
    ("[dashboard]\nnames = \"camera-pi.local\"\n", "list of names"),
    ("[paths]\ndata_dir = \"\"\n", "path in quotes"),
    ("not toml at all [", "(text)"),
])
def test_mistakes_are_refused_not_ignored(text, words):
    with pytest.raises(ConfigError, match=words.replace("(", r"\(").replace(")", r"\)")):
        parse(text)


def test_a_missing_file_given_by_name_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load(tmp_path / "nope.toml")


def test_bridge_command_line():
    c = parse('[paths]\ndata_dir = "/data/ca"\nrun_dir = "/run/ca"\n[bridge]\nbinary = "/opt/b"\n')
    assert bridge_argv(c, armed=False) == ["/opt/b", "/run/ca/bridge.sock", "/data/ca/logs", "--read-only",
                                           "--lock-file=/data/ca/state/locked"]
    assert bridge_argv(c, armed=True) == ["/opt/b", "/run/ca/bridge.sock", "/data/ca/logs",
                                          "--lock-file=/data/ca/state/locked"]
    c = parse('[bridge]\nallow_exposure = true\n')
    assert "--allow-exposure" in bridge_argv(c, armed=True)
    assert "--allow-exposure" not in bridge_argv(c, armed=False) and "--read-only" in bridge_argv(c, armed=False)
