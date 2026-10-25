#!/bin/bash
# Render a list of shots one after another (each in its own Blender), skipping finished ones; safe to re-run (an
# unfinished shot resumes from its last frame). Log: video/blender/out/queue.log
#
# Final renders run on the gaming PC (video/blender/RENDER_ON_PC.md). On the Mac this refuses to run unless
# ALLOW_MAC=1 is set, and then only when tools/heavy_ok.sh says memory is green and nothing else heavy is running.
#
# It never restarts Blender on its own: if a shot fails or Blender is quit, the whole queue stops there.
cd "$(dirname "$0")/../.."
SCRIPT=video/blender/${SHOTS:-shots_model.py}
LOG=video/blender/out/queue.log
LOCK=video/blender/out/.queue.lock
mkdir -p video/blender/out
if [[ $(uname) == Darwin ]]; then
  B=/Applications/Blender.app/Contents/MacOS/Blender
  if [[ $ALLOW_MAC != 1 ]]; then
    echo "Big renders go to the gaming PC (video/blender/RENDER_ON_PC.md). For a light job here: ALLOW_MAC=1 $0 ..."
    exit 1
  fi
else
  B=${BLENDER:-blender}
fi
if ! mkdir "$LOCK" 2>/dev/null; then                  # one queue at a time
  echo "Another render queue is running (or crashed: remove $LOCK if you're sure nothing is running)."
  exit 1
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT INT TERM
for s in "$@"; do
  [[ -f video/blender/out/$s.mp4 || -f video/blender/out/$s.webm ]] && continue
  [[ -d video/blender/out/$s ]] && find video/blender/out/$s -name 'f_*.png' -size 0 -delete   # a frame cut off mid-render
  if [[ $(uname) == Darwin ]] && ! tools/heavy_ok.sh --quiet; then
    echo "$(date +%T) stopped before $s: memory or another heavy job" >> $LOG
    exit 1
  fi
  echo "$(date +%T) start $s" | tee -a $LOG
  RUN=video/blender/out/.last_run.log
  "$B" -b -noaudio --python-exit-code 1 -P $SCRIPT -- $s > $RUN 2>&1
  ok=$?
  cat $RUN >> $LOG.full
  grep -m1 "^DEVICE:" $RUN | sed "s/^/  $s: /" | tee -a $LOG
  if [[ $ok != 0 && $(uname) != Darwin && -z $BLENDER_DEVICE ]] && grep -qi "optix" $RUN; then
    echo "$(date +%T) $s: OptiX failed, trying CUDA once" | tee -a $LOG     # one deliberate fallback, not a loop
    BLENDER_DEVICE=CUDA "$B" -b -noaudio --python-exit-code 1 -P $SCRIPT -- $s > $RUN 2>&1
    ok=$?
    cat $RUN >> $LOG.full
  fi
  if [[ $ok == 0 ]]; then
    echo "$(date +%T) done $s" | tee -a $LOG
  else
    echo "$(date +%T) FAILED $s: queue stopped (nothing restarts on its own)" | tee -a $LOG
    echo "---- last 20 lines from Blender ($s) ----"
    tail -n 20 $RUN
    exit 1
  fi
done
echo "$(date +%T) queue finished" >> $LOG
