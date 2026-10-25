#!/bin/zsh
# Gate for heavy jobs on the Mac (Blender, video renders, encodes): one heavy thing at a time, only when memory is fine.
# Exit 0 = OK to start. Exit 1 = don't start (the reason is printed).
#   tools/heavy_ok.sh            check before starting a heavy job
#   tools/heavy_ok.sh --quiet    same, print only on failure
[[ $(uname) != Darwin ]] && exit 0                    # the gaming PC has its own memory; this is for the Mac
level=$(sysctl -n kern.memorystatus_vm_pressure_level 2>/dev/null)   # 1 normal (green), 2 warning (yellow), 4 critical (red)
free=$(memory_pressure 2>/dev/null | awk -F': ' '/free percentage/ {print $2}')
if [[ $level != 1 ]]; then
  echo "NOT OK: memory pressure is not green (level $level, free $free). Don't start a heavy job."
  exit 1
fi
busy=$(pgrep -fl "Blender -b|MacOS/Blender|chrome-headless-shell|Chrome for Testing|hyperframes.*render|ffmpeg" 2>/dev/null | grep -v heavy_ok)
if [[ -n $busy ]]; then
  echo "NOT OK: another heavy job is running:"
  echo "$busy" | cut -c1-120
  exit 1
fi
[[ $1 != --quiet ]] && echo "OK: memory pressure green (free $free), no other heavy job running."
exit 0
