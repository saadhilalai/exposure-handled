"""The Pi's start-up services, permission rules, install script, bridge launcher and power-and-heat log
(deploy/pi/, tools/pi_bridge.py, tools/pi_health.py). They only run for real on the Pi; this checks what can be
checked here. No camera."""
import configparser
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from agent.config import parse
from tools import pi_health

ROOT = Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy" / "pi"


def unit(name):
    c = configparser.ConfigParser(interpolation=None, strict=False)
    c.optionxform = str
    c.read(DEPLOY / name)
    return c


def test_the_bridge_starts_read_only_at_power_up():
    u = unit("camera-bridge.service")
    assert u["Service"]["ExecStart"].endswith("pi_bridge.py --read-only")
    assert u["Unit"]["Conflicts"] == "camera-bridge-armed.service"
    assert u["Install"]["WantedBy"] == "multi-user.target"
    assert u["Service"]["User"] == "camera-agent"                       # never root


def test_the_armed_bridge_is_never_enabled_or_restarted_armed():
    u = unit("camera-bridge-armed.service")
    assert u["Service"]["ExecStart"].endswith("pi_bridge.py --armed")
    assert u["Service"]["Restart"] == "no"
    assert u["Unit"]["OnFailure"] == "camera-bridge.service"            # read-only takes over
    assert u["Unit"]["Conflicts"] == "camera-bridge.service"
    assert "Install" not in u                                           # nothing can enable it at power-up


def test_the_agent_doesnt_stop_when_arming_stops_the_read_only_bridge():
    u = unit("camera-agent.service")
    assert "camera-bridge.service" in u["Unit"]["Wants"] and "Requires" not in u["Unit"]
    assert u["Service"]["ExecStart"].endswith("tools/pi_agent.py")
    assert u["Service"]["User"] == "camera-agent" and u["Install"]["WantedBy"] == "multi-user.target"


def test_at_most_two_cores_are_busy():                                # four busy cores switch a weak supply off
    agent = unit("camera-agent.service")["Service"]
    assert agent["AllowedCPUs"] == "3" and "OPENCV_FOR_THREADS_NUM=1" in agent["Environment"]
    assert unit("camera-bridge.service")["Service"]["AllowedCPUs"] == "2"
    assert unit("camera-bridge-armed.service")["Service"]["AllowedCPUs"] == "2"


def test_the_health_reading_runs_every_minute():
    assert unit("camera-health.timer")["Timer"]["OnUnitActiveSec"] == "60"
    s = unit("camera-health.service")["Service"]
    assert s["Type"] == "oneshot" and "video" in s["SupplementaryGroups"]   # vcgencmd needs the video group


def test_the_permission_rules_are_narrow():
    rule = (DEPLOY / "50-camera-agent.rules").read_text()
    assert 'subject.user == "camera-agent"' in rule and 'verb == "start"' in rule
    units = {w.strip('"') for w in rule.replace("(", " ").replace(")", " ").split() if w.endswith('.service"')}
    assert units == {"camera-bridge.service", "camera-bridge-armed.service"}
    udev = (DEPLOY / "60-camera-agent.rules").read_text()
    assert 'ATTR{idVendor}=="054c"' in udev and 'GROUP="camera-agent"' in udev and 'MODE="0660"' in udev


def test_the_install_script_parses_and_never_starts_the_bridge():
    text = (DEPLOY / "install.sh").read_text()
    subprocess.run(["bash", "-n", str(DEPLOY / "install.sh")], check=True)
    assert "systemctl start" not in text and "systemctl restart" not in text
    assert "set -euo pipefail" in text
    if shutil.which("shellcheck"):
        subprocess.run(["shellcheck", "-S", "warning", str(DEPLOY / "install.sh")], check=True)


def test_the_bridge_launcher_uses_the_settings_file(tmp_path):
    env = dict(os.environ, CAMERA_AGENT_CONFIG=str(ROOT / "config" / "pi.example.toml"))
    run = lambda mode: subprocess.run([sys.executable, str(ROOT / "tools" / "pi_bridge.py"), mode, "--print"],
                                      env=env, capture_output=True, text=True, check=True).stdout.split()
    assert run("--read-only") == ["/opt/camera-agent/build/bridge/camera_bridge", "/run/camera-agent/bridge.sock",
                                  "/data/camera-agent/logs", "--read-only",
                                  "--lock-file=/data/camera-agent/state/locked"]
    assert "--read-only" not in run("--armed") and "--allow-exposure" not in run("--armed")


def test_reading_power_and_heat():
    ok = pi_health.summary(pi_health.parse_throttled("throttled=0x0\n"), pi_health.parse_temp("temp=48.3'C\n"))
    assert ok["power_ok"] and ok["temp_c"] == 48.3 and ok["notes"] == []
    seen = pi_health.summary(pi_health.parse_throttled("throttled=0x50000"), 61.0)
    assert not seen["power_ok"] and seen["undervoltage_seen"] and not seen["undervoltage_now"]
    assert seen["notes"] == ["under-voltage seen", "throttling seen"]
    now = pi_health.summary(pi_health.parse_throttled("throttled=0x50005"), None)
    assert now["undervoltage_now"] and now["throttled_now"]
    with pytest.raises(ValueError):
        pi_health.parse_throttled("error")


def test_the_reading_goes_to_the_log_and_the_dashboard(tmp_path):
    cfg = parse('[paths]\ndata_dir = "%s"\n' % tmp_path)

    class Done:
        def __init__(self, out):
            self.stdout = out
    answers = {"get_throttled": "throttled=0x10000\n", "measure_temp": "temp=55.0'C\n"}
    entry = pi_health.read(run=lambda cmd, **kw: Done(answers[cmd[1]]))
    pi_health.save(entry, cfg)
    assert json.loads((cfg.state_dir / "health.json").read_text())["undervoltage_seen"]
    log = cfg.logs_dir / "health.jsonl"
    log.write_text("x" * (pi_health.MAX_LOG_BYTES + 10) + "\n")       # too big: trimmed, not endless
    pi_health.save(entry, cfg)
    assert log.stat().st_size < pi_health.MAX_LOG_BYTES


def test_the_card_copy_refuses_the_wrong_disk_and_asks_first():
    text = (DEPLOY / "clone_card.sh").read_text()
    subprocess.run(["bash", "-n", str(DEPLOY / "clone_card.sh")], check=True)
    assert "set -euo pipefail" in text
    assert 'is the card the Pi is running from' in text                 # never the running card
    assert "isn't a USB disk" in text and "has mounted parts" in text
    assert 'Type the disk' in text and "not confirmed: nothing changed" in text
    assert text.index("not confirmed") < text.index("wipefs")           # the question comes before any erase
    assert "PARTUUID=$NEW-03  /data" in text                            # the separate data partition


def test_sending_code_finds_a_file_emptied_by_a_power_cut_and_restores_it(tmp_path):
    app = tmp_path / "pi"                                                # a folder stands in for the Pi
    subprocess.run(["git", "clone", "-q", str(ROOT), str(app)], check=True)
    subprocess.run(["git", "-C", str(app), "checkout", "-q", "HEAD~1"], check=True)
    (app / "agent" / "config.py").write_text("")
    env = dict(os.environ, PI="local", PI_APP=str(app), PI_SAVED=str(tmp_path / "saved"), PI_SUDO="")
    run = lambda *a: subprocess.run(["bash", str(ROOT / "tools" / "pi_send_code.sh"), *a], env=env,
                                    capture_output=True, text=True)
    check = run("--check")
    assert check.returncode == 1 and "1 of" in check.stdout and "agent/config.py" in check.stdout
    fixed = run("--restore")
    assert fixed.returncode == 0 and "All" in fixed.stdout
    assert (app / "agent" / "config.py").read_text() and list((tmp_path / "saved").rglob("config.py"))
    assert run("--check").returncode == 0
    gone = subprocess.run(["bash", str(ROOT / "tools" / "pi_send_code.sh"), "--restore"], capture_output=True,
                          text=True, env=dict(env, PI_APP=str(tmp_path / "no-such-pi")))
    assert gone.returncode != 0 and not list((tmp_path / "saved").rglob("runner.py"))   # no Pi: nothing touched


def test_the_watch_test_never_arms_and_refuses_damaged_code():
    text = (ROOT / "tools" / "pi_watch_test.sh").read_text()
    subprocess.run(["bash", "-n", str(ROOT / "tools" / "pi_watch_test.sh")], check=True)
    assert "set -euo pipefail" in text and "camera-bridge-armed" in text and "the bridge is armed" in text
    assert "systemctl start" not in text and "--armed" not in text                # the agent starts read-only itself
    assert "AllowedCPUs=3" in text and "OPENCV_FOR_THREADS_NUM=1" in text        # the 2-core limit
    assert "status --porcelain" in text and "pi_send_code.sh --restore" in text  # emptied files stop it
    assert "trap stop_all EXIT" in text
    assert "camera_on_usb ||" in text and "bInterfaceClass" in text             # an asleep camera stops it at once
    bench = (ROOT / "tools" / "pi_power_bench.sh").read_text()
    subprocess.run(["bash", "-n", str(ROOT / "tools" / "pi_power_bench.sh")], check=True)
    assert "set -euo pipefail" in bench and "the bridge is armed" in bench and "BridgeClient" not in bench


def test_the_hotspot_is_a_trial_that_undoes_itself_until_kept():
    text = (DEPLOY / "install.sh").read_text()
    made = text[text.index("step_hotspot() {"):text.index("step_hotspot_try() {")]
    assert "autoconnect no" in made and "autoconnect yes" not in made     # set up, but never on at start-up
    trial = text[text.index("step_hotspot_try() {"):text.index("step_hotspot_keep() {")]
    assert "--on-active=10min" in trial and '"$TO_HOME" sh "$home"' in trial   # no answer: back to home Wi-Fi
    assert "switch_later" in trial                                             # a dropped login can't stop it
    keep = text[text.index("step_hotspot_keep() {"):text.index("step_hotspot_off() {")]
    assert "--active" in keep and "clear_undo" in keep and "autoconnect yes" in keep
    for step in ("hotspot-try)", "hotspot-keep)", "hotspot-off)"):
        assert step in text
    rescue = unit("camera-wifi-rescue.service")
    assert rescue["Unit"]["ConditionPathExists"] == "/boot/firmware/home-wifi"
    assert rescue["Service"]["ExecStart"].endswith("install.sh hotspot-rescue")
    saved = text[text.index("step_hotspot_rescue() {"):]
    assert "autoconnect no" in saved and "TO_HOME" in saved and "device connect" not in saved   # home, never the hotspot
    assert saved.index("read_only_now") < saved.index('rm -f "$RESCUE_FILE"')      # read-only: the file stays
    assert 'up id "$1"' in text and "reset-failed camera-hotspot-undo" in text       # any name; a failed undo clears


def test_read_only_keeps_the_data_part_writable_and_needs_it():
    text = (DEPLOY / "read_only.sh").read_text()
    subprocess.run(["bash", "-n", str(DEPLOY / "read_only.sh")], check=True)
    assert 'PARAM="overlayroot=tmpfs:recurse=0"' in text            # recurse=1 (the default) would freeze /data
    on = text[text.index("    on)"):text.index("    off)")]
    assert "isn't installed" in on and "/data isn't its own part" in on and "before-read-only" in on
    send = (ROOT / "tools" / "pi_send_code.sh").read_text()
    assert "overlayroot=tmpfs /proc/cmdline" in send                 # no code sent into a read-only system
    assert "overlayroot=tmpfs /proc/cmdline" in (DEPLOY / "install.sh").read_text()
