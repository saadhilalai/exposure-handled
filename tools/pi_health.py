"""The Pi's power and heat, once a minute (run by camera-health.timer, deploy/pi/).

Reads `vcgencmd get_throttled` and `vcgencmd measure_temp`, adds a line to <data>/logs/health.jsonl and writes the
latest reading to <data>/state/health.json, which the dashboard shows. What matters is voltage dips: on a 3 A
D-tap cable, "under-voltage seen" means the Pi's 5 V sagged at some point since it started.

Usage: python tools/pi_health.py
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.config import ConfigError, load  # noqa: E402

# vcgencmd get_throttled bits (Raspberry Pi documentation)
BITS = {
    0: "under-voltage now", 1: "CPU speed capped now", 2: "throttled now", 3: "temperature limit now",
    16: "under-voltage seen", 17: "CPU speed capping seen", 18: "throttling seen", 19: "temperature limit seen",
}
MAX_LOG_BYTES = 2_000_000


def parse_throttled(text):
    m = re.search(r"throttled=(0x[0-9a-fA-F]+)", text or "")
    if not m:
        raise ValueError("unexpected get_throttled answer: %r" % text)
    return int(m.group(1), 16)


def parse_temp(text):
    m = re.search(r"temp=([0-9.]+)", text or "")
    return float(m.group(1)) if m else None


def summary(value, temp_c):
    return {
        "time": datetime.now().isoformat(timespec="seconds"), "throttled": hex(value), "temp_c": temp_c,
        "undervoltage_now": bool(value & 0x1), "undervoltage_seen": bool(value & 0x10000),
        "throttled_now": bool(value & 0x4), "throttled_seen": bool(value & 0x40000),
        "power_ok": not value & 0x10001,
        "notes": [text for bit, text in BITS.items() if value & (1 << bit)],
    }


def read(run=subprocess.run):
    out = lambda *a: run(["vcgencmd", *a], capture_output=True, text=True, timeout=5, check=True).stdout
    return summary(parse_throttled(out("get_throttled")), parse_temp(out("measure_temp")))


def save(entry, cfg):
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    log = cfg.logs_dir / "health.jsonl"
    if log.exists() and log.stat().st_size > MAX_LOG_BYTES:          # keep the newest half, from a line start
        data = log.read_bytes()
        cut = data.find(b"\n", len(data) // 2)
        log.write_bytes(data[cut + 1:] if cut >= 0 else b"")
    with log.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    latest = cfg.state_dir / "health.json"
    tmp = latest.with_suffix(".tmp")
    tmp.write_text(json.dumps(entry))
    os.replace(tmp, latest)


def main():
    try:
        cfg = load()
        entry = read()
    except (ConfigError, ValueError, OSError, subprocess.SubprocessError) as e:
        sys.exit("pi_health: %s" % e)
    save(entry, cfg)
    print("Power %s · %s°C%s" % ("OK" if entry["power_ok"] else "DIPPED", entry["temp_c"],
                                 " · " + ", ".join(entry["notes"]) if entry["notes"] else ""))


if __name__ == "__main__":
    main()
