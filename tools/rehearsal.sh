#!/bin/bash
# One command for a rehearsal take: makes the folder, starts the bridge, starts the agent with the dashboard.
# You type LIVE yourself, and SPACE (kill switch) stays under your finger: the agent runs in this window.
# When the agent stops (q, SPACE then q, or Ctrl-C), the bridge is stopped too, so its switch never lingers.
#
#   tools/rehearsal.sh                       the sunset run: REH_sunset_A_agent (live, the agent may change
#                                            ISO, aperture, shutter and WB, also while recording)
#   tools/rehearsal.sh REH_cmp1_A_agent      any REH_..._agent take: the same, under that name
#   tools/rehearsal.sh REH_cmp1_B_auto       camera-auto take: the agent only watches; the bridge is read-only
#   tools/rehearsal.sh REH_cmp1_C_manual     by-hand take: the same
#
# Everything is labeled rehearsal (sessions/REHEARSAL/) and never mixes with Step 7.
# Anything after the take name goes to the agent (for example --look interview).
# For testing without a camera: REHEARSAL_FAKE=1 REHEARSAL_NO_OPEN=1 tools/rehearsal.sh REH_test_A_agent --seconds 8

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
TAKE="${1:-REH_sunset_A_agent}"
EXTRA=("${@:2}")
PORT=8770
SOCK="$ROOT/run/bridge.sock"
URL="http://127.0.0.1:$PORT/"

case "$TAKE" in
  REH_*_agent) MODE=agent; BRIDGE_FLAG="--allow-exposure-while-recording"
               AGENT_FLAGS=(--live --allow-exposure-while-recording) ;;
  REH_*)       MODE=watch; BRIDGE_FLAG="--read-only"; AGENT_FLAGS=() ;;
  *) echo "Rehearsal takes are named REH_..., for example REH_sunset_A_agent. Nothing started."; exit 2 ;;
esac

RUNNING="$(pgrep -x camera_bridge; pgrep -f '[f]ake_bridge[.]py --socket')"
if [ -n "$RUNNING" ]; then
  echo "A bridge is already running (pid $(echo $RUNNING)). Stop it first. Nothing started."
  exit 1
fi

LOGDIR="$ROOT/sessions/REHEARSAL/bridge-$(date +%Y-%m-%d_%H%M%S)_$TAKE"
mkdir -p "$LOGDIR" "$ROOT/run"
echo "rehearsal: not part of the Step 7 test" > "$LOGDIR/LABEL"
rm -f "$SOCK"                                   # an old socket would look like a running bridge

caffeinate -dims -w $$ &                        # the Mac stays awake while this runs

# The bridge gets its own process group, so Ctrl-C here reaches only the agent (which locks the bridge itself).
if [ "${REHEARSAL_FAKE:-0}" = 1 ]; then
  FAKE_FLAG="$BRIDGE_FLAG"
  "$PY" -c 'import os, sys; os.setsid(); os.execv(sys.argv[1], sys.argv[1:])' "$PY" "$ROOT/tools/fake_bridge.py" \
      --socket "$SOCK" --log-dir "$LOGDIR" $FAKE_FLAG > "$LOGDIR/bridge_stdout.log" 2>&1 &
else
  (cd "$ROOT/build/bridge" && exec "$PY" -c 'import os, sys; os.setsid(); os.execv(sys.argv[1], sys.argv[1:])' \
      ./camera_bridge "$SOCK" "$LOGDIR" "$BRIDGE_FLAG") > "$LOGDIR/bridge_stdout.log" 2>&1 &
fi
BRIDGE=$!

stop_bridge() {
  if kill -0 "$BRIDGE" 2>/dev/null; then
    kill -TERM "$BRIDGE" 2>/dev/null
    for _ in $(seq 1 50); do kill -0 "$BRIDGE" 2>/dev/null || break; sleep 0.1; done
    kill -0 "$BRIDGE" 2>/dev/null && kill -KILL "$BRIDGE" 2>/dev/null
    echo "Bridge stopped."
  fi
}
trap stop_bridge EXIT
trap 'true' INT                                  # Ctrl-C is for the agent; this script just waits for it

echo "Starting the bridge ($([ $MODE = agent ] && echo 'rehearsal switch ON' || echo 'read-only')) ..."
READY=0
for _ in $(seq 1 60); do
  if ! kill -0 "$BRIDGE" 2>/dev/null; then break; fi
  if "$PY" - "$SOCK" <<'EOF' 2>/dev/null; then READY=1; break; fi
import sys
sys.path.insert(0, ".")
from agent.bridge_client import BridgeClient
s = BridgeClient(sys.argv[1], timeout=2).status()
sys.exit(0 if s.get("connected") else 1)
EOF
  sleep 0.5
done
grep -v '^$' "$LOGDIR/bridge_stdout.log" | sed 's/^/  bridge: /'
if [ $READY != 1 ]; then
  echo "The bridge didn't connect. Check the USB cable, USB Connection Mode = Remote Shoot/Trn., and no phone app"
  echo "connected to the camera. Then run this again. (Bridge log: $LOGDIR)"
  exit 1
fi

# Open the dashboard as soon as it answers (it starts after you type LIVE).
[ "${REHEARSAL_NO_OPEN:-0}" = 1 ] || ( for _ in $(seq 1 240); do
    if curl -s -m 1 -o /dev/null "$URL"; then open "$URL"; break; fi
    sleep 1
  done ) &

echo
[ $MODE = agent ] && echo "Take $TAKE: LIVE agent take. Type LIVE when asked. Then press Auto on the dashboard." \
                  || echo "Take $TAKE: the agent only watches and logs. Expose with the camera (auto or by hand)."
echo "Keys: SPACE kill switch · m mark a light change · x log a problem · q quit"
echo
"$PY" tools/run_agent.py ${AGENT_FLAGS[@]+"${AGENT_FLAGS[@]}"} --rehearsal --take "$TAKE" --dashboard --port $PORT ${EXTRA[@]+"${EXTRA[@]}"}
STATUS=$?
echo
echo "Agent stopped. Bridge log: $LOGDIR"
exit $STATUS
