#!/bin/bash
# The watch-only power test, run on the Pi. The agent watches the camera, read-only, on one core (the bridge on
# another), while the Pi's voltage, low-power flag, heat and load are logged every second. Then one summary.
#
#   tools/pi_watch_test.sh [MINUTES] [LABEL]      default: 5 minutes, label "watch"
#
# Settings: $CAMERA_AGENT_CONFIG, else /etc/camera-agent/config.toml. Before the Pi has its own Wi-Fi, use a copy
# whose [dashboard] host is the Pi's home address: the agent can't open 10.42.0.1 until the hotspot is up.
# It never arms: the bridge is the read-only service. It stops everything at the end, or on Ctrl-C.
set -euo pipefail

MINUTES=${1:-5}
LABEL=${2:-watch}
CONF=${CAMERA_AGENT_CONFIG:-/etc/camera-agent/config.toml}
APP=/opt/camera-agent
LOG=$HOME/power-$LABEL.txt
UNIT=camera-agent-test

say() { printf '\n== %s\n' "$*"; }
die() { printf '\nSTOPPED: %s\n' "$*" >&2; exit 1; }

case "$MINUTES" in ''|*[!0-9]*) die "minutes is a whole number" ;; esac
[ "$(id -u)" != 0 ] || die "run it as your own user (it uses sudo where it needs to)"
! systemctl is-active -q camera-bridge-armed || die "the bridge is armed: disarm from the phone first"
! systemctl is-active -q camera-agent || die "the agent service is running: sudo systemctl stop camera-agent"
! systemctl is-active -q "$UNIT" || die "a test is already running"
sudo test -r "$CONF" || die "no settings file at $CONF"
[ -z "$(sudo git -c safe.directory=$APP -C $APP status --porcelain --untracked-files=no)" ] ||
    die "the code on the Pi doesn't match its commit. On the Mac: tools/pi_send_code.sh --restore"
sudo systemctl reset-failed "$UNIT" 2>/dev/null || true
SESSIONS=$(cd "$APP" && sudo -u camera-agent .venv/bin/python -c \
    "from agent.config import load; print(load('$CONF').sessions_dir)")

LOGGER=
stop_all() {
    sudo systemctl stop "$UNIT" camera-bridge 2>/dev/null || true
    [ -z "$LOGGER" ] || kill "$LOGGER" 2>/dev/null || true
    sync
}
trap stop_all EXIT

say "Logging power every second to $LOG (on core 0)"
rm -f "$LOG"
taskset -c 0 bash -c 'while true; do
    echo "$(date +%T) $(vcgencmd pmic_read_adc EXT5V_V | sed "s/.*=//") $(vcgencmd get_throttled | sed "s/.*=//") $(vcgencmd measure_temp | sed "s/.*=//") $(cut -d" " -f1 /proc/loadavg)"
    sync; sleep 1; done' >> "$LOG" 2>/dev/null </dev/null &
LOGGER=$!

say "Starting the agent, watch-only, on core 3 for $MINUTES minute(s)"
touch "$HOME/.watch-test-start"
BRIDGE_BEFORE=$(systemctl show camera-bridge -p CPUUsageNSec --value)   # it may have run since start-up
case "$BRIDGE_BEFORE" in ''|*[!0-9]*) BRIDGE_BEFORE=0 ;; esac
sudo systemd-run -q --unit="$UNIT" -p User=camera-agent -p Group=camera-agent -p AllowedCPUs=3 \
    -E CAMERA_AGENT_CONFIG="$CONF" -E OPENCV_FOR_THREADS_NUM=1 -E OMP_NUM_THREADS=1 \
    "$APP/.venv/bin/python" "$APP/tools/pi_agent.py"
END=$(( $(date +%s) + MINUTES * 60 + 5 ))
while [ "$(date +%s)" -lt "$END" ]; do
    sleep 10
    if ! systemctl is-active -q "$UNIT"; then
        sudo journalctl -u "$UNIT" --no-pager -n 15 | sed 's/^/  /'
        die "the agent stopped early (above: its last lines)"
    fi
done
CPU_AGENT=$(systemctl show "$UNIT" -p CPUUsageNSec --value)
CPU_BRIDGE=$(systemctl show camera-bridge -p CPUUsageNSec --value)
case "$CPU_BRIDGE" in ''|*[!0-9]*) ;; *) [ "$CPU_BRIDGE" -lt "$BRIDGE_BEFORE" ] || CPU_BRIDGE=$((CPU_BRIDGE - BRIDGE_BEFORE)) ;; esac
SESSION=$(sudo find "$SESSIONS" -maxdepth 1 -name '*pi-watch*' -newer "$HOME/.watch-test-start" | sort | tail -1)
stop_all
LOGGER=

say "Result: $LABEL"
[ -n "$SESSION" ] || die "the agent never saw the camera (no new session in $SESSIONS)"
sudo cat "$SESSION/runner_log.jsonl" | python3 -c '
import json, statistics as s, sys
log, minutes, cpu_a, cpu_b = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
rows = [json.loads(l) for l in sys.stdin if l.strip()]
ticks = [r for r in rows if r.get("event") == "tick"]
power = [l.split() for l in open(log) if len(l.split()) >= 5]
v = [float(p[1].rstrip("V")) for p in power]
low = sum(int(p[2], 16) & 0x1 != 0 for p in power)
temp = max(float(p[3].rstrip("'\''C")) for p in power)
print("voltage    median %.2f V, lowest %.2f V" % (s.median(v), min(v)))
print("low power  %d of %d s (%d%%)" % (low, len(power), round(100 * low / len(power))))
print("heat       up to %.1f C" % temp)
if ticks:
    fps = [t["fps"] for t in ticks if t.get("fps")]
    eyes = [t["eyes_ms"] for t in ticks]
    print("frames     %.1f a second (median; lowest %.1f)" % (s.median(fps), min(fps)))
    print("per look   %.1f ms (median; longest %.1f)" % (s.median(eyes), max(eyes)))
    print("scene      %s stops at the start, %s at the end" % (ticks[0].get("key"), ticks[-1].get("key")))
secs = ticks[-1]["t"] if ticks else minutes * 60
for name, ns in (("agent", cpu_a), ("bridge", cpu_b)):
    if ns.isdigit():
        print("%-10s %d%% of one core" % (name + " CPU", round(100 * int(ns) / 1e9 / secs)))
sugg = [r for r in rows if r.get("event") == "would_change"]
print("suggested  %d time(s)%s" % (len(sugg), (": last " + sugg[-1]["text"]) if sugg else ""))
' "$LOG" "$MINUTES" "$CPU_AGENT" "$CPU_BRIDGE"
echo "session    $(basename "$SESSION")   power log: $LOG"
