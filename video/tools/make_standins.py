"""Stand-in clips for the brag video, until Saturday's footage: rendered by the website's own camera simulator, so
the draft shows the story and its timing. Every frame carries "STAND-IN · illustration, not footage".

They use the real clips' file names (assets/video/clipA.mp4, clipB1-3.mp4), so on Saturday swapping is just
replacing the files. This tool never overwrites a file it didn't make (each stand-in has a .standin note beside it).

CLIP A (11.4 s, the S3 story): steady tungsten interior; at 3.0 s (the mark) one lamp goes off and the scene gets
one stop darker (rendered as half the light on the sensor); the agent waits ~1.5 s, then raises ISO a third of a stop
at a time (3200 -> 4000 -> 5000 -> 6400), the way it worked on the FX2 on Oct 19, and the picture is back by 7.9 s.
CLIPS B1-B3 (8.4 s): the same steady scene for all three panes, with no outcome implied.

Needs the website preview running (python tools/serve_site.py) and ffmpeg.
Usage: python video/tools/make_standins.py
"""
import base64
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "video" / "composition" / "assets" / "video"
SITE = "http://127.0.0.1:8780/?debug&quality=high"
FPS, W, H = 30, 1280, 720

# per-frame exposure (as an ISO the picture is rendered at) and scene light: the lamp going off makes the scene
# exactly one stop darker (rendered as half the light on the sensor); the agent's third-stop ISO steps bring it back.
def story_a(t):
    light = 1.0 if t < 3.0 else max(0.5, 1.0 - (t - 3.0) / 0.15 * 0.5)
    iso = 3200 if t < 4.5 else 4032 if t < 6.2 else 5080 if t < 7.9 else 6400      # the agent: +1/3 stop each
    return iso * light, 1.0


def story_b(t):
    return 3200, 1.0


RENDER = """([t, iso, key, label]) => {
  const sim = window.__debug.sim;
  let v = window.__standin;
  if (!v) {
    const c = document.createElement('canvas'); c.style.cssText = 'position:fixed;left:0;top:0;width:%dpx;height:%dpx;z-index:9999';
    document.body.append(c);
    for (const x of sim.views) x.hold = true;                 // only the stand-in renders
    v = window.__standin = sim.view(c, { scene: 1, size: [%d, %d] });
    v.base = { ...v.scene }; v.t0 = 0; v.hold = false;
  }
  v.scene = { ...v.base, key: v.base.key * key };
  v.a = { iso, shutter: 1 / 48, fnum: 2.8, wb: 3500, mode: 'normal' }; v.b = null; v.visible = true;
  sim.render(t * 1000);
  const x = v.ctx; x.save();
  x.font = '600 22px ui-monospace, Menlo, monospace'; x.textBaseline = 'bottom';
  const msg = 'STAND-IN · illustration, not footage · ' + label;
  const w = x.measureText(msg).width + 28;
  x.fillStyle = 'rgba(0,0,0,.55)'; x.fillRect(24, %d - 70, w, 44);
  x.fillStyle = '#ffd23a'; x.fillText(msg, 38, %d - 36);
  x.restore();
  return v.canvas.toDataURL('image/jpeg', 0.9);
}""" % (W // 2, H // 2, W, H, H, H)


def render(page, name, seconds, story, label):
    target = OUT / (name + ".mp4")
    note = OUT / (name + ".standin")
    if target.exists() and not note.exists():
        sys.exit("%s exists and isn't a stand-in (a real clip?): not touching it." % target)
    with tempfile.TemporaryDirectory() as tmp:
        n = round(seconds * FPS)
        for i in range(n):
            t = i / FPS
            iso, key = story(t)
            data = page.evaluate(RENDER, [t, iso, key, label])
            Path(tmp, "f%04d.jpg" % i).write_bytes(base64.b64decode(data.split(",", 1)[1]))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(Path(tmp, "f%04d.jpg")),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", "-movflags", "+faststart", str(target)],
                       check=True)
    note.write_text("stand-in made by video/tools/make_standins.py; replace %s.mp4 with the real clip and delete this note\n" % name)
    print("wrote", target, "(%d frames)" % n)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        page = b.new_page(viewport={"width": 1440, "height": 900})
        page.goto(SITE, wait_until="load")
        page.mouse.wheel(0, 10)
        page.wait_for_function("window.__debug && window.__debug.sim", timeout=60000)
        render(page, "clipA", 11.4, story_a, "CLIP A: S3, lamp off at 0:03")
        render(page, "clipB1", 8.4, story_b, "CLIPS B1-B3: the same stand-in in all three panes")
        b.close()
    for n in ("clipB2", "clipB3"):          # the same steady scene in all three panes
        if (OUT / (n + ".mp4")).exists() and not (OUT / (n + ".standin")).exists():
            sys.exit("%s.mp4 exists and isn't a stand-in: not touching it." % n)
        shutil.copyfile(OUT / "clipB1.mp4", OUT / (n + ".mp4"))
        (OUT / (n + ".standin")).write_text((OUT / "clipB1.standin").read_text().replace("clipB1", n))
        print("wrote", OUT / (n + ".mp4"))


if __name__ == "__main__":
    main()
