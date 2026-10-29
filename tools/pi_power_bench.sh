#!/bin/bash
# The hardest power test, run on the Pi: all 4 cores busy (the eyes benchmark on saved frames, no camera use)
# while the voltage, low-power flag and heat are logged twice a second. On the MacBook's supplies this switched
# the Pi off within a second, twice; a proper 5.1 V supply should hold it with no low-power flag at all.
#
#   tools/pi_power_bench.sh [SECONDS]      default 120
#
# Everything is flushed to the card first, and the log line by line, so a switch-off loses nothing but the run.
set -euo pipefail

SECONDS_WANTED=${1:-120}
APP=/opt/camera-agent
LOG=$HOME/power-4core.txt

die() { printf '\nSTOPPED: %s\n' "$*" >&2; exit 1; }
case "$SECONDS_WANTED" in ''|*[!0-9]*) die "seconds is a whole number" ;; esac
[ "$(id -u)" != 0 ] || die "run it as your own user"
! systemctl is-active -q camera-bridge-armed || die "the bridge is armed: disarm from the phone first"

sync
rm -f "$LOG"
(while true; do
    echo "$(date +%T.%N | cut -c1-10) $(vcgencmd pmic_read_adc EXT5V_V | sed 's/.*=//') $(vcgencmd get_throttled | sed 's/.*=//') $(vcgencmd measure_temp | sed 's/.*=//')"
    sync; sleep 0.5
done) >> "$LOG" 2>/dev/null </dev/null &
LOGGER=$!
trap 'kill $LOGGER 2>/dev/null || true; sync' EXIT

echo "Before: $(vcgencmd get_throttled), $(vcgencmd pmic_read_adc EXT5V_V | sed 's/.*=//'). All 4 cores busy for ${SECONDS_WANTED} s..."
END=$(( $(date +%s) + SECONDS_WANTED ))
cd "$APP"
while [ "$(date +%s)" -lt "$END" ]; do
    .venv/bin/python tools/bench_eyes.py site/media/real --threads 4 >/dev/null 2>&1
done
kill "$LOGGER" 2>/dev/null || true
python3 - "$LOG" <<'PY'
import statistics as s, sys
rows = [l.split() for l in open(sys.argv[1]) if len(l.split()) >= 4]
v = [float(r[1].rstrip("V")) for r in rows]
low = sum(int(r[2], 16) & 0x1 != 0 for r in rows)
print("Still on after %.0f s of all 4 cores." % (len(rows) / 2))
print("voltage    median %.2f V, lowest %.2f V" % (s.median(v), min(v)))
print("low power  %d of %d readings (%d%%)" % (low, len(rows), round(100 * low / len(rows))))
print("heat       up to %.1f C" % max(float(r[3].rstrip("'C")) for r in rows))
PY
echo "After: $(vcgencmd get_throttled)   (0x0 = never short of power since start-up)   log: $LOG"
