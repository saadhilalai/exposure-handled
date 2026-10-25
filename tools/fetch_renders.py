"""Bring the 3D clips rendered on the gaming PC back to the Mac: downloads every .mp4/.webm from the private Hugging Face
dataset (made by video/blender/render_pc.sh) into video/blender/out/, where tools/build_films.py picks them up.

    .venv/bin/python tools/fetch_renders.py
"""
import shutil
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download

REPO = "s4dAi/camera-agent-renders"
OUT = Path(__file__).resolve().parent.parent / "video" / "blender" / "out"

if __name__ == "__main__":
    api = HfApi()
    names = [f for f in api.list_repo_files(REPO, repo_type="dataset") if f.endswith((".mp4", ".webm"))]
    for n in names:
        src = Path(hf_hub_download(REPO, n, repo_type="dataset"))
        dst = OUT / n
        if dst.exists() and dst.stat().st_size == src.stat().st_size:
            continue
        shutil.copy2(src, dst)
        print("fetched", n, "%.1f MB" % (dst.stat().st_size / 1e6))
    print("%d clips in %s" % (len(names), OUT))
