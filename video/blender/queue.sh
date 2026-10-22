#!/bin/zsh
# Render a list of shots one after another (each in its own Blender), skipping finished ones; safe to re-run after a
# sleep or crash (unfinished shots resume from their last frame). Log: video/blender/out/queue.log
cd "$(dirname "$0")/../.."
B=/Applications/Blender.app/Contents/MacOS/Blender
SCRIPT=video/blender/${SHOTS:-shots.py}            # SHOTS=shots_fx.py for the FX2 films
LOG=video/blender/out/queue.log
for s in "$@"; do
  if [[ $s == still:* ]]; then                       # still:SHOT:TIME:NAME
    parts=(${(s/:/)s}); shot=$parts[2]; tm=$parts[3]; name=$parts[4]
    [[ -f video/blender/out/stills4k/$name.png ]] && continue
    echo "$(date +%T) still $name" >> $LOG
    $B -b -noaudio --python-exit-code 1 -P $SCRIPT -- $shot --res 3840 --spp 160 --threshold 0.01 --stills $tm --stilldir video/blender/out/stills4k/tmp >> $LOG.full 2>&1
    mkdir -p video/blender/out/stills4k && mv video/blender/out/stills4k/tmp/*.png video/blender/out/stills4k/$name.png 2>/dev/null
    continue
  fi
  [[ -f video/blender/out/$s.mp4 || -f video/blender/out/$s.webm ]] && continue
  echo "$(date +%T) start $s" >> $LOG
  $B -b -noaudio --python-exit-code 1 -P $SCRIPT -- $s >> $LOG.full 2>&1 && echo "$(date +%T) done $s" >> $LOG || echo "$(date +%T) FAILED $s" >> $LOG
done
echo "$(date +%T) queue finished" >> $LOG
