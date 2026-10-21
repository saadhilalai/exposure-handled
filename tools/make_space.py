"""Pack the website into a folder that runs as a free Hugging Face Space, and (optionally) upload it.

The site needs no server, so the Space is a free "static" Space, just files: everything in site/, including the
placeholder clips (site/media/placeholder/, kept out of git, remade by tools/make_placeholder_clips.py). The local
test pages (site/_dev/) stay out, and the Space's own README card replaces site/README.md.

Usage:
    python tools/make_space.py                                     # build build/hf_space/ only
    python tools/make_space.py --push s4dAi/exposure-handled       # build, then upload
                                                                   # (pip install huggingface_hub; hf auth login)
"""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
OUT = ROOT / "build" / "hf_space"
PLACEHOLDERS = ("lamp", "night", "night-log", "sunbeam")

SPACE_CARD = """\
---
title: "Exposure, Handled."
colorFrom: gray
colorTo: red
sdk: static
app_file: index.html
pinned: false
short_description: An AI camera assistant that sets exposure like a DP
---

# Exposure, Handled.

Camera Agent is an AI assistant for a Sony FX2 cinema camera. It reads the live picture, sets exposure the way a
cinematographer would, and explains every change in one line. This page lets you play with it: break a shot and
watch it fix it, take the exploded camera apart, or try to beat it.

What's real so far is tagged on the page. **Real**: the Oct 19 closed-loop test on the FX2 (its own log).
**Placeholder**: the dashboard screenshots and clips, until the Step 7 shoot. **Illustration**: the simulated camera
picture and the 3D camera.

Designed & built by Saad Hilal · S4D. Code, test plan and lab notebook:
https://github.com/saadhilalai/exposure-handled

Typefaces: Instrument Serif and D-DIN (SIL Open Font License, see fonts/). 3D: three.js (MIT).
Motion: GSAP with ScrollTrigger (GreenSock standard "no charge" license).
"""


def check_inputs():
    missing = [n for n in PLACEHOLDERS for ext in (".mp4", ".jpg")
               if not (SITE / "media" / "placeholder" / (n + ext)).exists()]
    if missing:
        raise SystemExit("Missing placeholder clips (%s). Run: python tools/make_placeholder_clips.py" % ", ".join(missing))


def build():
    check_inputs()
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SITE, OUT, ignore=shutil.ignore_patterns(".DS_Store", "_dev", "README.md"))
    (OUT / "README.md").write_text(SPACE_CARD)
    files = [p for p in OUT.rglob("*") if p.is_file()]
    print("Built %s/ (%d files, %.1f MB)" % (OUT.relative_to(ROOT), len(files), sum(p.stat().st_size for p in files) / 1e6))


def push(repo_id):
    from huggingface_hub import HfApi
    api = HfApi()
    api.create_repo(repo_id, repo_type="space", space_sdk="static", exist_ok=True)
    api.upload_folder(folder_path=str(OUT), repo_id=repo_id, repo_type="space",
                      commit_message="Deploy Exposure, Handled.", delete_patterns="*")
    user, name = repo_id.split("/")
    print("Uploaded. Space page: https://huggingface.co/spaces/%s" % repo_id)
    print("Live site: https://%s-%s.static.hf.space" % (user.lower(), name.lower().replace("_", "-")))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--push", metavar="USERNAME/SPACE", help="upload to this Hugging Face Space")
    args = parser.parse_args()
    build()
    if args.push:
        push(args.push)
