#!/bin/bash
# Render the films' 3D shots on the gaming PC (WSL Ubuntu, RTX 3080), then upload the finished clips to a private
# Hugging Face dataset so the Mac can fetch them (tools/fetch_renders.py). Steps: video/blender/RENDER_ON_PC.md
#
#   bash video/blender/render_pc.sh                 render the remaining shots, then upload
#   bash video/blender/render_pc.sh h_xray h_chip   just these shots
set -e
cd "$(dirname "$0")/../.."
BV=5.2.2                                            # the Mac's version: the scene file was saved with it
BLENDER=${BLENDER:-$HOME/blender-$BV-linux-x64/blender}
SHOTS_LIST=${*:-"s_catch s_hero h_world h_smash h_xray h_irisx h_chip h_swarm h_kill h_slam"}
REPO=${RENDERS_REPO:-s4dAi/camera-agent-renders}

if [[ ! -x $BLENDER ]]; then
  echo "Downloading Blender $BV for Linux (one time)..."
  curl -L -o /tmp/blender.tar.xz "https://download.blender.org/release/Blender${BV%.*}/blender-$BV-linux-x64.tar.xz"
  tar -xf /tmp/blender.tar.xz -C "$HOME" && rm /tmp/blender.tar.xz
fi
command -v ffmpeg >/dev/null || { echo "Install ffmpeg first: sudo apt install -y ffmpeg"; exit 1; }
[[ -f video/blender/cache/model.blend ]] || { echo "Missing video/blender/cache/model.blend: git pull first"; exit 1; }

BLENDER=$BLENDER bash video/blender/queue.sh $SHOTS_LIST || echo "(the queue stopped early: uploading what finished)"
tail -n 15 video/blender/out/queue.log

echo "Uploading the finished clips to the private dataset $REPO ..."
python3 - "$REPO" $SHOTS_LIST <<'EOF'
import sys
from pathlib import Path
from huggingface_hub import HfApi
repo, shots = sys.argv[1], sys.argv[2:]
api = HfApi()
api.create_repo(repo, repo_type="dataset", private=True, exist_ok=True)
out = Path("video/blender/out")
files = [p for s in shots for p in (out / (s + ".mp4"), out / (s + ".webm")) if p.exists()]
for p in files:
    api.upload_file(path_or_fileobj=str(p), path_in_repo=p.name, repo_id=repo, repo_type="dataset")
    print("uploaded", p.name)
missing = [s for s in shots if not any(f.stem == s for f in files)]
print("done: %d clips uploaded%s" % (len(files), ("; NOT rendered: " + ", ".join(missing)) if missing else ""))
EOF
