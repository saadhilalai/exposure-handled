#!/bin/bash
# Step 7, in two Terminal windows:
#
#   tools/step7.sh bridge             Window 1, once for the day: starts the bridge with the Step 7 switch
#                                     (--allow-iso-while-recording), keeps the Mac awake, waits until the camera
#                                     answers, then stays open. Ctrl-C here stops the bridge (do it at the end).
#   tools/step7.sh S1_R1_A_agent      Window 2, every take: runs that take's exact run-sheet command (look, live or
#                                     dry run, the switch) with the dashboard on port 8770. Typos are refused.
#   tools/step7.sh S1_R1_A_agent --print   only shows the command (anything else after the name goes to the agent)
#
# The run sheet stays the plan; this only saves typing. For testing without a camera: STEP7_FAKE=1 tools/step7.sh bridge

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
SOCK="$ROOT/run/bridge.sock"
PORT=8770

if [ "${1:-}" = "" ]; then
  sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
fi

# ---------------------------------------------------------------- one take
if [ "$1" != "bridge" ]; then
  TAKE="$1"
  sheet_command() {               # (a function: macOS bash 3.2 misreads a here-document inside $(...))
    "$PY" - "$1" <<'EOF'
import sys
sys.path.insert(0, "tools"); sys.path.insert(0, ".")
import difflib
import make_run_sheet as sheet              # importing doesn't write anything; only running it does
take = sys.argv[1]
rows = {t[1]: (num, t[4]) for num, ts in sheet.takes(sheet.build_order()).items() for t in ts}
if take not in rows:
    near = difflib.get_close_matches(take, list(rows), n=3)
    print("NOTONSHEET " + (" or ".join(near) if near else ""))
else:
    num, method = rows[take]
    print(sheet.command(take, sheet.SCENES[num][1], method))
EOF
  }
  CMD="$(sheet_command "$TAKE")"
  case "$CMD" in
    NOTONSHEET*) near="${CMD#NOTONSHEET }"
                 echo "$TAKE isn't on the Step 7 run sheet.${near:+ Did you mean $near?} Nothing started."; exit 2 ;;
    run_agent.py*) ;;
    *) echo "Couldn't read the run sheet: $CMD"; exit 1 ;;
  esac
  ARGS=(${CMD#run_agent.py })
  case " ${ARGS[*]} " in *" --dashboard "*) ARGS+=(--port "$PORT") ;; esac
  echo "Run sheet: $CMD"
  [ "${2:-}" = "--print" ] && exit 0
  exec "$PY" tools/run_agent.py "${ARGS[@]}" "${@:2}"
fi

# ---------------------------------------------------------------- the bridge, once for the day
RUNNING="$(pgrep -x camera_bridge; pgrep -f '[f]ake_bridge[.]py --socket')"
if [ -n "$RUNNING" ]; then
  echo "A bridge is already running (pid $(echo $RUNNING)). Nothing started."
  exit 1
fi
LOGDIR="$ROOT/sessions/bridge-$(date +%Y-%m-%d_%H%M%S)_step7"
mkdir -p "$LOGDIR" "$ROOT/run"
rm -f "$SOCK"                                   # an old socket would look like a running bridge
caffeinate -dims -w $$ &                        # the Mac stays awake while this runs (3-4 hours)

if [ "${STEP7_FAKE:-0}" = 1 ]; then
  "$PY" -c 'import os, sys; os.setsid(); os.execv(sys.argv[1], sys.argv[1:])' "$PY" "$ROOT/tools/fake_bridge.py" \
      --socket "$SOCK" --log-dir "$LOGDIR" --allow-iso-while-recording > "$LOGDIR/bridge_stdout.log" 2>&1 &
else
  (cd "$ROOT/build/bridge" && exec "$PY" -c 'import os, sys; os.setsid(); os.execv(sys.argv[1], sys.argv[1:])' \
      ./camera_bridge "$SOCK" "$LOGDIR" --allow-iso-while-recording) > "$LOGDIR/bridge_stdout.log" 2>&1 &
fi
BRIDGE=$!

stop_bridge() {
  if kill -0 "$BRIDGE" 2>/dev/null; then
    kill -TERM "$BRIDGE" 2>/dev/null
    for _ in $(seq 1 50); do kill -0 "$BRIDGE" 2>/dev/null || break; sleep 0.1; done
    kill -0 "$BRIDGE" 2>/dev/null && kill -KILL "$BRIDGE" 2>/dev/null
    echo "Bridge stopped. Restart it without the switch before any other work (the run sheet's last box)."
  fi
}
trap stop_bridge EXIT
trap 'exit 0' INT TERM

echo "Starting the Step 7 bridge (ISO may change while recording, in agent takes only) ..."
READY=0
for _ in $(seq 1 60); do
  kill -0 "$BRIDGE" 2>/dev/null || break
  if "$PY" - "$SOCK" <<'EOF' 2>/dev/null; then READY=1; break; fi
import sys
sys.path.insert(0, ".")
from agent.bridge_client import BridgeClient
s = BridgeClient(sys.argv[1], timeout=2).status()
sys.exit(0 if s.get("connected") and s.get("iso_while_recording") else 1)
EOF
  sleep 0.5
done
grep -v '^$' "$LOGDIR/bridge_stdout.log" | sed 's/^/  bridge: /'
if [ $READY != 1 ]; then
  echo "The bridge didn't connect. Check the USB cable, USB Connection Mode = Remote Shoot/Trn., and no phone app"
  echo "connected to the camera. Then run this again. (Bridge log: $LOGDIR)"
  exit 1
fi
echo
echo "Bridge ready. Leave this window open; run each take in a second window:  tools/step7.sh <take name>"
echo "Ctrl-C here at the end of the day stops the bridge.  (Bridge log: $LOGDIR)"
while kill -0 "$BRIDGE" 2>/dev/null; do sleep 1; done
echo "The bridge stopped on its own. See $LOGDIR/bridge_stdout.log"
exit 1
