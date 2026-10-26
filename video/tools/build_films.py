"""The three launch films: their edits, voice and soundtracks, as HyperFrames projects in video/v1-abstract,
video/v2-hype and video/v3-story. The 3D shots come from video/blender/shots.py (path-traced in Blender).

    python video/tools/build_films.py prep  [v1 v2 v3]    project folders, fonts, the 3D shots (with a glow pass) linked in
    python video/tools/build_films.py voice               trim the voice lines (video/films-voice) to tight WAVs
    python video/tools/build_films.py edit  [v1 v2 v3]    edit.js + index.html for each film
    python video/tools/build_films.py mix   [v1 v2 v3]    music + voice (+ effects) -> assets/audio/mix.m4a
    python video/tools/build_films.py render [v1 v2 v3] [--draft]   lint, then render (4K; --draft: 1080p)

No tags, labels or small print in the films (the director's rule): the honesty notes and credits live in
video/FILMS.md and video/CREDITS.md, and go in the website's Nerd mode when a film is published.
"""
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V = ROOT / "video"
OUT3D = V / "blender" / "out"
VOICE = V / "films-voice"
HYPE = V / "hype" / "assets"
SITE_URL = "s4dai-exposure-handled.static.hf.space"

BPM = 115.0
B = 60.0 / BPM


def s(beat):
    return round(beat * B, 3)


# ---------------------------------------------------------------- the films
# shots: (id, source, at, to, extra); source "3d:<shot>" is a Blender render, "ft:<file>" a footage excerpt.
# times are seconds of the film; "ms" = where in the source to start.
V1 = dict(
    dir="v1-abstract", title="Exposure, Handled. (calm)", duration=58.6, template="calm",
    # Art first, in the manner of the AI-lab launch films: warm paper, hand-made shapes that become ideas (light, a lens,
    # an eye, a frame); the camera shown sparingly, as art; one or two words at a time; a human-sounding narrator.
    calm=dict(A=[0.0, 8.6], C=[12.2, 19.0], D=[19.0, 25.0], E=[25.0, 32.5], F=[32.5, 38.5],
              flashes=[["#m1", 44.65, 45.65], ["#m2", 46.5, 47.25], ["#m3", 47.9, 48.5]]),
    # "Peace Within" (Peter Rudenko): its lift (1:13.3 in the track) lands on the hit after the black hold
    music=dict(file=V / "music-candidates/round2/calm/peace-within-rudenko/rudenko_peace-within.mp3", start=21.75, fade_in=1.5,
               fade_out=(57.2, 1.4), gain=0.0,
               env=[(0, -12), (7.5, -12), (9.0, -6), (43.5, -4), (48.8, -1), (49.05, -45), (51.5, -45), (51.55, 1), (54.2, 1), (54.7, -9)]),
    shots=[
        ("sil", "3d:c_silhouette", 38.5, 43.5, dict(cls="paper")),
        ("mg1", "3d:c_glint", 43.5, 44.65, dict()),
        ("mg2", "3d:c_ring", 45.65, 46.5, dict()),
        ("mg3", "3d:c_dial", 47.25, 47.9, dict()),
        ("mg4", "3d:c_glint", 48.5, 49.05, dict(ms=0.8)),
    ],
    blackCards=[(49.05, 51.55), (54.26, 58.6)],
    words=[
        dict(at=8.6, to=12.2, cls="name", html="Alan Turing"),
        dict(at=16.4, to=18.9, html="Light", y=86),
        dict(at=21.4, to=24.8, html="Never still", y=86),
        dict(at=33.4, to=35.6, html="Every stop", y=9.5),
        dict(at=35.8, to=38.3, html="Your look", y=9.5),
        dict(at=41.0, to=43.3, html="The moment", y=9.5),
        dict(at=54.26, to=58.6, cls="title", html="Exposure, <em>Handled</em>.", y=46, out=False),
        dict(at=55.9, to=58.6, cls="link", html=SITE_URL, y=58, out=False),
    ],
    panels=[dict(cls=c, html=h, dx=dx) for c, h, dx in [
        ("p-news", "Exposure, Handled.", -60), ("p-type", "EXPOSURE, HANDLED.", 0), ("p-clay", "Exposure, Handled.", 20),
        ("p-chalk", "Exposure, Handled.", 0), ("p-sage", "Exposure, Handled.", 10), ("p-note", "Exposure, Handled.", -20),
        ("p-ochre", "Exposure, Handled.", -30), ("p-term", "<b>$</b> exposure, handled<u></u>", -40), ("p-dusk", "Exposure, Handled.", 0),
        ("p-umber", "Exposure, Handled.", 0)]],
    panel_start=51.55, panel_durs=[0.42, 0.38, 0.34, 0.30, 0.27, 0.24, 0.22, 0.20, 0.18, 0.16],
    voice=[("c0", 0.38, "nasa", 6.0), ("c1", 12.7), ("c2", 19.6), ("c3", 25.6), ("c4", 33.4), ("c5", 39.2), ("c6", 54.8)],
    voice_dir="v3", sfx=[], fadeOut=(57.6, 58.6),
)

# The hype film keeps the hype draft's music edit: "Beast" (115 BPM), film beat 0 = track beat -16, the drop at film
# beat 16, a splice at film beat 64 to the track's last bar, and the music dropping out for the kill switch. Now quieter
# under the voice (the director: "turn it down", then "a bit quieter" again), and ducking harder.
# Beats 0-12: the camera locked in the centre while the world behind it changes on every beat: bold solid colours, then
# real places (plates thrown out of focus, as a long lens would), then the studio. Its light, reflections and iris change
# with each world in the render (video/blender/shots_model.py, WORLDS).
HYPE_WORLDS = ["#000000", "#b8791f", "#8a1b13", "#1c3893", "#78885f", "#e8e2d5", None, None, None, None, None, None]
HYPE_PLATES = {6: "sunset", 7: "city", 8: "desert", 9: "forest", 10: "studio", 11: "stage"}     # beat: plate id (PLATES)
# The plates: one beat each of a real place, (source, in, out, grade). Saad's own footage has none of these places without
# client work or faces, so they're licensed Pexels clips (video/stock/STOCK.md), thrown out of focus behind the camera.
PX = V / "stock" / "pexels"
PLATES = {
    "sunset": (PX / "p-sunset_px28486616_the-sun-setting-over-a-field-with-a-view-of-the-.mp4", 2.0, 3.2, None),
    "city": (PX / "p-city_px36872872_stunning-twilight-cityscape-aerial-view.mp4", 0.5, 1.7, None),
    "desert": (PX / "p-desert_px5728372_video-of-sunset-on-a-desert.mp4", 6.0, 7.2, None),
    "forest": (PX / "p-forest_px31807870_sunbeams-through-forest-trees-in-drenthe.mp4", 4.0, 5.2, None),
    "studio": (PX / "p-studio_px10729080_close-up-on-lamp-in-room.mp4", 0.2, 1.4, "eq=brightness=0.04"),
    "stage": (PX / "p-studio_px28957437_dramatic-foggy-light-show-in-dark-hallway.mp4", 33.8, 35.0, "eq=brightness=-0.05:saturation=0.6"),
}
# where each plate sits behind the camera: the horizon under it (so its shadow lands on ground), the sun beside the lens
PLATE_CSS = {"sunset": "--tx:24%;--ty:-23%;--sc:1.55", "desert": "--tx:27%;--ty:-6%;--sc:1.5", "city": "--ty:-4%;--sc:1.2",
             "forest": "--sc:1.15", "studio": "--sc:1.1", "stage": "--ty:6%;--sc:1.2"}
# and the camera's light matched to each world: a light grade on the transparent render, beat by beat
HYPE_CAMFX = {0: "none", 1: "sepia(.18) saturate(1.15)", 2: "sepia(.12) saturate(1.1)", 3: "hue-rotate(-6deg) brightness(.95)",
              4: "none", 5: "brightness(1.04)", 6: "sepia(.32) saturate(1.3) brightness(1.03)", 7: "hue-rotate(-10deg) saturate(.85) brightness(.82)",
              8: "sepia(.26) saturate(1.2) brightness(1.05)", 9: "sepia(.08) saturate(.95) brightness(.92)", 10: "brightness(1.05)", 11: "brightness(.9)"}
ALPHA = {"c_silhouette", "h_world"}           # 3D shots rendered with a transparent background (VP9 + alpha)
V2 = dict(
    dir="v2-hype", title="Exposure, Handled. (hype)", duration=s(70),
    music=dict(file=HYPE / "music" / "beast.mp3", beast=True, gain=-9.0),
    worlds=[dict(at=s(i), to=s(i + 1), color=c) for i, c in enumerate(HYPE_WORLDS) if c],
    camfx=[dict(id="world", at=s(i), f=f) for i, f in HYPE_CAMFX.items()],
    shots=[("pl_" + k, "pl:" + k, s(i), s(i + 1), dict(cls="plate", css=PLATE_CSS.get(k))) for i, k in HYPE_PLATES.items()] + [
        ("world", "3d:h_world", 0, s(12), dict(push=[1.0, 1.0])),
        ("smash", "3d:h_smash", s(12), s(16), dict(push=[1.0, 1.12], pushEase="power2.in")),
        ("xray", "3d:h_xray", s(16), s(24), dict(punch=1.08)),
        ("irisx", "3d:h_irisx", s(24), s(28), dict(punch=1.05)),
        ("chip", "3d:h_chip", s(28), s(32), dict(punch=1.04)),
        ("glint", "3d:c_glint", s(32), s(33), dict(ms=0.2, punch=1.06)),
        ("dial", "3d:c_dial", s(33), s(34), dict(punch=1.06)),
        ("ring", "3d:c_ring", s(34), s(35), dict(punch=1.06)),
        ("irisx2", "3d:h_irisx", s(35), s(36), dict(ms=s(2.9), punch=1.05)),
        ("swarm", "3d:h_swarm", s(36), s(40), dict(punch=1.06)),
        ("xray2", "3d:h_xray", s(40), s(44), dict(ms=s(4), punch=1.05)),
        ("irisx3", "3d:h_irisx", s(44), s(47), dict(punch=1.04)),
        ("kill", "3d:h_kill", s(47), s(50), dict(punch=1.02)),
        ("slam", "3d:h_slam", s(50), s(58), dict(push=[1.0, 1.03])),
    ],
    cards=[(s(58), s(70))],
    words=[
        dict(at=s(12.1), to=s(13.95), style="huge", html="A camera"),
        dict(at=s(14.0), to=s(15.95), style="huge", html="that thinks", size=250),
        dict(at=s(58), to=s(70), style="title", html="Exposure, <em>Handled</em>.", y=46, cut=True, out=False),
        dict(at=s(62), to=s(70), style="link", html=SITE_URL, y=60, cut=True, out=False),
    ],
    voice=[("h1", s(1.15)), ("h2", s(6.15)), ("h3", s(10.15)), ("h4", s(20.15)), ("h5", s(24.15)), ("h6", s(28.15)),
           ("h7", s(44.2)), ("h8", s(46.2)), ("h9", s(48.35)), ("h10", s(53.0)), ("h11", s(58.3))],
    voice_dir="v3",
    sfx=[(0, "impactPunch_heavy_000.ogg", -8), (0, "swish-7.wav", -11)]
        + [(b, "impactMetal_light_00%d.ogg" % (b % 2 * 2 + 1), -21) for b in range(1, 12)]
        + [(12, "swish-7.wav", -11), (16, "lowFrequency_explosion_000.ogg", -3), (16, "impactPunch_heavy_002.ogg", -6),
           (25, "impactMetal_002.ogg", -12), (26, "impactMetal_002.ogg", -12), (27, "impactMetal_002.ogg", -11), (28, "forceField_001.ogg", -14),
           (32, "impactMetal_light_001.ogg", -12), (33, "impactMetal_light_003.ogg", -12), (34, "swish-3.wav", -12), (35.1, "impactMetal_002.ogg", -12),
           (36, "swish-3.wav", -10), (40, "swish-7.wav", -10), (45, "impactMetal_002.ogg", -13), (46, "impactMetal_002.ogg", -13),
           (48, "lowFrequency_explosion_001.ogg", -4), (48, "impactPlate_heavy_002.ogg", -8),
           (52, "lowFrequency_explosion_000.ogg", -2), (52, "impactMetal_heavy_001.ogg", -8), (52, "explosionCrunch_002.ogg", -10),
           (58, "impactBell_heavy_001.ogg", -14), (58, "impactPunch_heavy_000.ogg", -10)],
    flashes=[(s(16), 0.85, 0.35), (s(24), 0.3, 0.2), (s(28), 0.3, 0.2), (s(36), 0.4, 0.25), (s(52), 0.75, 0.3)],
    streaks=[(s(12), 38, 1), (s(16.02), 52, -1), (s(36), 30, 1), (s(52.02), 60, -1)],
    kill=(s(48), s(50)),
    dims=[],
    blacks=[(s(68.6), s(70), 0.0, 1.0)],
)

# The story film. The director cut the old footage ("not cinematic"; no train, no beach: no shore or seaside shots either). Saad's Mac was searched again:
# nothing of his own met the bar without client work or faces, so the picture is licensed stock from Pexels (licences
# and links in video/stock/STOCK.md and CREDITS.md), graded to one look, plus the 3D camera. Letterboxed 2.39:1, an old-film
# texture over everything. Opens on two flat earthy fields under a curved horizon (after the AI-lab launch film's opening),
# which match-cuts to a real ridge line at sunrise. Music: "Cylinder Three" (Chris Zabriskie), quieter than the voice;
# its first new layer (0:24.5) lands as we go inside the camera, the second (0:41.0) on the hero.
STOCK = V / "stock" / "pexels"
FOOTAGE = {   # id: (source, in, out, crop or None, "709" or "hlg", extra filter or None)
    "ridge": (STOCK / "s-op_px28769585_silhouette-of-person-at-sunrise-in-mountains.mp4", 0.5, 5.0, None, "709", None),
    "dusk": (STOCK / "s-op_px4231685_silhouette-of-a-man-taking-photos.mp4", 0.2, 3.2, None, "709", None),
    "sink": (STOCK / "s-li_px3603305_video-footage-in-hyper-lapse-of-the-sun-setting-.mp4", 2.0, 5.5, None, "709", None),
    "cloud": (STOCK / "s-li_px33824905_dramatic-sky-timelapse-with-sunlit-clouds.mp4", 4.0, 5.6, None, "709", None),
    "door": (STOCK / "s-li_px6092472_female-opening-the-window-blinds.mp4", 2.4, 5.4, None, "709", "reverse,setpts=PTS/2.6"),
    "sunset": (STOCK / "s-mo_px27775382_a-sunset-over-the-ocean-with-birds-flying-over-i.mp4", 0.0, 2.0, None, "709", None),
    "gone": (STOCK / "s-mo_px34785690_serene-sunset-over-ocean-with-flying-seagull.mp4", 5.0, 7.2, None, "709", None),
    "lens": (STOCK / "s-op_px8089525_close-up-footage-of-a-person-adjusting-the-lens-.mp4", 0.5, 3.0, "crop=3840:2160:128:0", "709", None),
    "city": (STOCK / "s-li_px14549980_day-to-night-cycle-in-city.mp4", 10.0, 30.0, None, "709", "setpts=PTS/9"),
    "monitor": (STOCK / "s-op_px8089229_a-cameraman-filming-a-production-using-a-video-c.mp4", 4.0, 6.0, "crop=3840:2160:128:0", "709", None),
    "framer": (STOCK / "s-mo_px11197001_woman-watching-sunset.mp4", 0.0, 3.5, "scale=3840:-2,pad=3840:2160:0:(oh-ih)/2", "709", None),
    "horses": (STOCK / "s-op_px26791738_a-man-taking-a-photo-of-horses-in-the-desert.mp4", 0.0, 3.4, None, "709", None),
    "beams": (STOCK / "p-forest_px31807870_sunbeams-through-forest-trees-in-drenthe.mp4", 4.0, 7.0, None, "709", None),
}
V3 = dict(
    dir="v3-story", title="Exposure, Handled. (story)", duration=55.0, letterbox=True, film=True,
    horizon=dict(to=8.6, top0="#b07f55", top1="#c08d5c"),
    music=dict(file=V / "music-candidates/round2/story/cylinder-three-zabriskie/zabriskie_cylinder-three.flac", start=0.0, fade_in=0.05,
               fade_out=(53.2, 1.8), gain=-3.0, env=[(0, -2), (23.6, -2), (24.1, -9), (24.5, -1), (40.8, -1), (41.0, 1), (48.4, 1), (48.6, -4)],
               duck="threshold=0.012:ratio=12:attack=6:release=300"),
    shots=[
        ("ridge", "ft:ridge.mp4", 8.6, 12.6, dict(push=[1.04, 1.0], pushEase="power1.out")),
        ("dusk", "ft:dusk.mp4", 12.6, 15.2, dict(push=[1.0, 1.04])),
        ("sink", "ft:sink.mp4", 15.2, 18.2, dict(push=[1.0, 1.05], grade=[(15.2, 1.0, 1.0), (16.4, 1.0, 1.0), (17.4, 0.6, 0.8, "power2.inOut")])),
        ("cloud", "ft:cloud.mp4", 18.2, 19.5, dict(push=[1.0, 1.03], grade=[(18.2, 0.75, 0.85)])),
        ("door", "ft:door.mp4", 19.5, 20.6, dict(push=[1.02, 1.0], grade=[(19.5, 0.8, 0.85)])),
        ("sunset", "ft:sunset.mp4", 20.6, 22.25, dict(push=[1.0, 1.03], grade=[(20.6, 0.85, 0.9)])),
        ("gone", "ft:gone.mp4", 22.25, 24.1, dict(push=[1.0, 1.04], grade=[(22.25, 0.8, 0.85), (23.0, 0.8, 0.85), (24.1, 0.0, 0.6, "power2.in")])),
        ("catch", "3d:s_catch", 24.5, 28.5, dict(fadeIn=0.35, push=[1.0, 1.03])),
        ("lens", "ft:lens.mp4", 28.5, 30.75, dict(push=[1.0, 1.04])),
        ("city", "ft:city.mp4", 30.75, 32.75, dict(push=[1.0, 1.03])),
        ("monitor", "ft:monitor.mp4", 32.75, 34.5, dict(push=[1.03, 1.0])),
        ("framer", "ft:framer.mp4", 34.5, 37.9, dict(push=[1.0, 1.04])),
        ("horses", "ft:horses.mp4", 37.9, 41.0, dict(push=[1.0, 1.03])),
        ("hero", "3d:s_hero", 41.0, 46.0, dict(push=[1.0, 1.04], shift=[0, -6])),
        ("beams", "ft:beams.mp4", 46.0, 48.6, dict(push=[1.0, 1.03], fadeOut=0.5)),
    ],
    words=[
        dict(at=3.1, to=4.8, style="line", html="The light", cut=True),
        dict(at=5.0, to=7.6, style="line", html="won’t wait.", cut=True),
        dict(at=48.6, to=55.0, style="title", html="Exposure, <em>Handled</em>.", y=46, cut=True, out=False),
        dict(at=50.8, to=55.0, style="link", html=SITE_URL, y=60, cut=True, out=False),
    ],
    voice=[("s1", 0.7), ("s2", 9.1), ("s3", 15.4), ("s4", 18.4), ("s5", 25.0), ("s6", 29.0), ("s7", 36.6), ("s8", 49.1)],
    voice_dir="v3",
    sfx=[],
    flashes=[(41.0, 0.35, 0.6)],
    cards=[(24.1, 24.5), (48.6, 55.0)],
    dims=[],
    blacks=[(53.8, 55.0, 0.0, 1.0)],
)
FILMS = {"v1": V1, "v2": V2, "v3": V3}

# "Same words, many surfaces" (after the reference film whose name runs across headlines in one spot): the title holds one
# band of the screen while what it's written on changes every cut, each cut shorter, landing on the clean title on black.
# Only our own surfaces: the README's and the page's real title lines, a terminal, and designed paper, slate, art.
MONTAGE = [
    ("p-news grainy", "Exposure, Handled.", -60), ("p-code", "<i>&lt;title&gt;</i>Exposure, Handled.<i>&lt;/title&gt;</i>", 40),
    ("p-type grainy", "EXPOSURE, HANDLED.", 0), ("p-bauhaus", "Exposure, Handled.", -30), ("p-chalk", "Exposure, Handled.", 20),
    ("p-readme", "<i>#</i> Exposure, Handled.", 70), ("p-note", "Exposure, Handled.", -20), ("p-cyan", "Exposure, Handled.", 0),
    ("p-term", "<b>$</b> exposure, handled<u></u>", -40), ("p-enso grainy", "Exposure, Handled.", 10), ("p-tape", "EXPOSURE, HANDLED.", 0),
    ("p-blue", "Exposure, Handled.", -20), ("p-menu", "Exposure · Handled", 0),
]
DURS = [0.42, 0.38, 0.34, 0.30, 0.27, 0.24, 0.22, 0.20, 0.18, 0.16, 0.14, 0.13, 0.125]


def montage(start=43.875):
    out, t = [], start
    for (cls, html, dx), d in zip(MONTAGE, DURS):
        out.append(dict(at=round(t, 3), to=round(t + d, 3), cls=cls, html=html, dx=dx))
        t += d
    return out


def place_panels(F):
    t = F["panel_start"]
    for p, d in zip(F["panels"], F["panel_durs"]):
        p["at"], p["to"] = round(t, 3), round(t + d, 3)
        t += d


place_panels(V1)
V1["sfx"] = V1["sfx"] + [(p["at"], "impactGeneric_light_002.ogg", -31) for p in V1["panels"]]


def story_shots():
    """The story's picture: footage picked in video/v3-story/footage.json ({"shots": [[id, file, at, to, ms, grade?], ...]}),
    plus the 3D moment inside the camera."""
    f = V / "v3-story" / "footage.json"
    if not f.exists():
        return []
    spec = json.loads(f.read_text())
    out = []
    for row in spec["shots"]:
        sid, src, at, to, ms = row[:5]
        extra = dict(ms=ms, push=row[6] if len(row) > 6 else [1.0, 1.04], fadeIn=row[7] if len(row) > 7 else 0)
        if len(row) > 5 and row[5]:
            extra["grade"] = row[5]
        out.append((sid, src, at, to, extra))
    return out


# ---------------------------------------------------------------- helpers
def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def link(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)                           # a hard link: no extra disk
    except OSError:
        shutil.copy2(src, dst)


def glow(shot):
    """A gentle bloom on the 3D render (the crew's glow, the speculars): highlights blurred and screened back on."""
    src, dst = OUT3D / (shot + ".mp4"), OUT3D / "glow" / (shot + ".mp4")
    if not src.exists():
        return None
    if dst.exists() and dst.stat().st_mtime > src.stat().st_mtime:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    # then up to 3840x2160 (lanczos, a touch of sharpening): the moving 3D is path-traced at 1920x1080 to fit the night
    g = ("[0:v]format=gbrp,split[a][b];[b]colorlevels=rimin=0.55:gimin=0.55:bimin=0.55,gblur=sigma=18,colorchannelmixer=rr=1:gg=0.9:bb=0.8[g];"
         "[a][g]blend=all_mode=screen:all_opacity=0.55,scale=3840:2160:flags=lanczos,unsharp=5:5:0.45,format=yuv420p")
    run(["nice", "-n", "10", "ffmpeg", "-v", "error", "-y", "-i", str(src), "-filter_complex", g, "-c:v", "libx264", "-preset", "medium",
         "-crf", "15", "-g", "24", "-keyint_min", "24", "-movflags", "+faststart", str(dst)])
    return dst


LOOK = ("curves=all='0/0 0.18/0.1 0.5/0.4 0.8/0.7 1/0.86',eq=saturation=0.85,"
        "colorbalance=rs=-0.05:gs=-0.01:bs=0.06:rm=0.02:bm=-0.02:rh=0.06:gh=0.02:bh=-0.05")
HLG = "colorspace=all=bt709:iall=bt2020:fast=1,curves=all='0/0 0.3/0.18 0.7/0.56 1/0.82',eq=saturation=1.05,"


def footage(name, dst):
    """Cut a story excerpt from the original 4K file (read-only), with the film's grade: a soft highlight roll-off,
    muted colour, cool shadows and warm highlights. HLG sources are brought to Rec.709 first (approximately)."""
    if dst.exists():
        return
    src, t0, t1, crop, kind, extra = FOOTAGE[name.rsplit(".", 1)[0]]
    vf = ",".join(x for x in (extra, crop, (HLG if kind == "hlg" else "") + LOOK, "scale=3840:2160:flags=lanczos", "fps=24", "format=yuv420p") if x)
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(["nice", "-n", "10", "ffmpeg", "-v", "error", "-y", "-ss", str(t0), "-t", str(t1 - t0), "-i", str(src), "-an", "-vf", vf,
         "-c:v", "libx264", "-preset", "medium", "-crf", "15", "-g", "24", "-keyint_min", "24",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
         "-movflags", "+faststart", str(dst)])


def plate(name, dst):
    """One beat of a real place, from a stock or own clip (read-only), at 1080p: it sits out of focus behind the camera."""
    if dst.exists() or name not in PLATES:
        return dst.exists()
    src, t0, t1, vf = PLATES[name]
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(["nice", "-n", "10", "ffmpeg", "-v", "error", "-y", "-ss", str(t0), "-t", str(t1 - t0), "-i", str(src), "-an",
         "-vf", ",".join(x for x in (vf, "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=24", "format=yuv420p") if x),
         "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-g", "24", "-keyint_min", "24", "-movflags", "+faststart", str(dst)])
    return True


def alpha4k(shot):
    """A transparent 3D shot, scaled to 4K with its alpha kept (VP9 + alpha)."""
    src, dst = OUT3D / (shot + ".webm"), OUT3D / "glow" / (shot + ".webm")
    if not src.exists():
        return None
    if dst.exists() and dst.stat().st_mtime > src.stat().st_mtime:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(["nice", "-n", "10", "ffmpeg", "-v", "error", "-y", "-c:v", "libvpx-vp9", "-i", str(src), "-vf",
         "format=yuva444p,scale=3840:2160:flags=lanczos,unsharp=5:5:0.4,format=yuva420p",
         "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-crf", "20", "-b:v", "0", "-row-mt", "1", "-g", "24", "-auto-alt-ref", "0", str(dst)])
    return dst


def src_path(src):
    kind, name = src.split(":", 1)
    if kind == "3d":
        return "3d/%s.%s" % (name, "webm" if name in ALPHA else "mp4")
    return ("plates/%s.mp4" % name) if kind == "pl" else "footage/%s" % name


# ---------------------------------------------------------------- steps
def prep(F):
    heavy_ok()                                      # it encodes (glow pass, footage, plates)
    d = V / F["dir"]
    a = d / "assets"
    for sub in ("fonts", "vendor"):
        (a / sub).mkdir(parents=True, exist_ok=True)
    for f in (HYPE / "fonts").iterdir():
        link(f, a / "fonts" / f.name)
    link(HYPE / "vendor" / "gsap.min.js", a / "vendor" / "gsap.min.js")
    link(HYPE / "grain.png", a / "grain.png")
    if F.get("horizon"):                            # the opening's paper texture (made by tools/make_paper.py)
        link(V / "v1-abstract" / "assets" / "art" / "paper.png", a / "art" / "paper.png")
    (d / "meta.json").write_text(json.dumps({"id": "exposure-handled-" + F["dir"], "name": "exposure-handled-" + F["dir"],
                                             "createdAt": "2026-10-22T05:00:00.000Z"}, indent=2) + "\n")
    (d / "package.json").write_text(json.dumps({"name": "camera-agent-" + F["dir"], "private": True, "type": "module", "scripts": {
        "dev": "npx --yes hyperframes@0.8.167 preview", "check": "npx --yes hyperframes@0.8.167 check",
        "render": "npx --yes hyperframes@0.8.167 render"}}, indent=2) + "\n")
    missing = []
    for sid, src, *_ in all_shots(F):
        if src.startswith("ft:"):
            footage(src[3:], a / "footage" / src[3:])
        if src.startswith("pl:") and not plate(src[3:], a / "plates" / (src[3:] + ".mp4")):
            missing.append("plate " + src[3:])
            ph = a / "plates" / (src[3:] + ".mp4")
            ph.parent.mkdir(parents=True, exist_ok=True)
            run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x6a5a4a:s=1920x1080:r=24:d=2", "-c:v", "libx264",
                 "-g", "24", "-pix_fmt", "yuv420p", str(ph)])
        if src.startswith("3d:"):
            name = src[3:]
            g = alpha4k(name) if name in ALPHA else glow(name)
            dst = a / src_path(src)
            if g:
                link(g, dst)
            else:                                   # a stand-in, so a draft can render before the shot exists
                missing.append(name)
                if not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if name in ALPHA:
                        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x00000000:s=1920x1080:r=24:d=12,format=yuva420p",
                             "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-g", "24", str(dst)])
                    else:
                        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x101010:s=1920x1080:r=24:d=12", "-c:v", "libx264",
                             "-g", "24", "-pix_fmt", "yuv420p", str(dst)])
    print("prep %s: ready%s" % (F["dir"], ("; 3D still rendering: " + ", ".join(sorted(set(missing)))) if missing else ""))


def all_shots(F):
    return F["shots"]


def voice_lines():
    out = VOICE / "lines"
    out.mkdir(parents=True, exist_ok=True)
    trim = ("silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.01,areverse,"
            "silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.04,areverse,highpass=f=80,"
            "equalizer=f=3200:t=q:w=1.2:g=2.5,acompressor=threshold=0.12:ratio=3:attack=4:release=60:makeup=1.6")
    srcs = {p.stem: p for p in VOICE.glob("*.mp3")}
    for p in (HYPE / "voice" / "takes" / "imogen").glob("h*.mp3"):
        srcs.setdefault(p.stem, p)
    for k, p in sorted(srcs.items()):
        run(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-af", trim, "-ar", "48000", "-ac", "1", str(out / (k + ".wav"))])
    print("voice: %d lines -> %s" % (len(srcs), out.relative_to(ROOT)))


V2DIR = VOICE / "v2"
RADIO = ("highpass=f=380,lowpass=f=3000,acompressor=threshold=0.08:ratio=6:attack=2:release=40:makeup=3,asoftclip=type=tanh,"
         "aecho=0.8:0.6:35|62:0.22|0.12")


def voice_v2():
    """The human-sounding narrator (ElevenLabs v4, voice "Dallin"): keep the breaths, trim only the dead air at the ends,
    a gentle clean-up. The opening quote also gets a vintage-transmission version: band-limited, a little drive, a small
    room, tape hiss and crackle, so it plainly reads as an old recording read aloud, not as anyone's real voice."""
    src, out = V2DIR / "lines", V2DIR / "proc"
    out.mkdir(parents=True, exist_ok=True)
    clean = ("silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.05,areverse,"
             "silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.25,areverse,highpass=f=65,"
             "acompressor=threshold=0.18:ratio=2:attack=8:release=120:makeup=1.3")
    n = 0
    for p in sorted(src.glob("*.mp3")):
        dst = out / (p.stem + ".wav")
        run(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-af", clean, "-ar", "48000", "-ac", "1", str(dst)])
        dur = duration(dst) + 0.6
        g = ("[0:a]%s,apad=pad_dur=0.6[v];anoisesrc=c=pink:a=0.018:d=%.2f:r=48000,highpass=f=900,lowpass=f=5200[h];"
             "aevalsrc='if(gt(random(0),0.9982),0.5*(random(1)-0.5),0)':d=%.2f:s=48000,lowpass=f=3800[c];"
             "[v][h][c]amix=inputs=3:normalize=0,afade=t=in:d=0.25,afade=t=out:st=%.2f:d=0.35" % (RADIO, dur, dur, dur - 0.35))
        run(["ffmpeg", "-v", "error", "-y", "-i", str(dst), "-filter_complex", g, "-ar", "48000", "-ac", "1", str(out / (p.stem + "_radio.wav"))])
        n += 1
    print("voice v2: %d lines (clean + radio) -> %s" % (n, out.relative_to(ROOT)))


V3DIR = VOICE / "v3"
# The opening quote as a mission radio call: only the middle of the voice (300-3000 Hz, cut steeply), pushed into a
# compressor and soft clipping with a touch of bit-crush for the crunch, the band cut again after the distortion.
NASA = ("highpass=f=300,highpass=f=300,lowpass=f=3000,lowpass=f=3000,equalizer=f=1700:t=q:w=1.1:g=5,"
        "acompressor=threshold=0.04:ratio=9:attack=1:release=45:makeup=5,volume=5dB,asoftclip=type=atan,"
        "acrusher=bits=9:mode=log:mix=0.3:aa=0.5,highpass=f=300,highpass=f=300,lowpass=f=3000,lowpass=f=3000,lowpass=f=3200,alimiter=limit=0.7:level=disabled")
QUINDAR = 0.25                                       # each beep, s (the in-tone 2525 Hz, the out-tone 2475 Hz, as on mission audio)


def voice_v3():
    """The narrator for all three films (ElevenLabs v4, voice "Jazzo": relaxed, conversational, not a narrator read):
    trim the dead air at the ends, keep the breaths, a light clean-up. The calm film's opening quote also gets a mission
    radio version (c0_nasa): a tone, the line through the radio chain over band-limited static and crackle, a tone.
    Every sound in it is made here (filters, noise and sine tones), nothing borrowed."""
    src, out = V3DIR / "lines", V3DIR / "proc"
    out.mkdir(parents=True, exist_ok=True)
    clean = ("silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.05,areverse,"
             "silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.2,areverse,highpass=f=65,"
             "acompressor=threshold=0.18:ratio=2:attack=8:release=120:makeup=1.3")
    for p in sorted(src.glob("*.mp3")):
        run(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-af", clean, "-ar", "48000", "-ac", "1", str(out / (p.stem + ".wav"))])
    c0 = out / "c0.wav"
    if c0.exists():
        lead, gap, tail = 0.15, 0.12, 0.35
        v0 = lead + QUINDAR + gap                    # the voice starts here
        b2 = v0 + duration(c0) + 0.15                # the out-tone
        D = b2 + QUINDAR + tail
        tone = "aevalsrc='0.22*sin(2*PI*%d*t)':d=%.2f:s=48000,afade=t=in:d=0.006,afade=t=out:st=%.3f:d=0.006,adelay=%d|%d"
        g = ";".join([
            "[0:a]%s,adelay=%d,apad=whole_dur=%.3f[v]" % (NASA, v0 * 1000, D),
            "anoisesrc=c=white:a=0.07:d=%.3f:r=48000,highpass=f=300,highpass=f=300,lowpass=f=3000,lowpass=f=3000,tremolo=f=6:d=0.35[n]" % D,
            "aevalsrc='if(gt(random(0),0.9975),0.6*(random(1)-0.5),0)':d=%.3f:s=48000,highpass=f=300,highpass=f=300,lowpass=f=3000,lowpass=f=3000[c]" % D,
            (tone % (2525, QUINDAR, QUINDAR - 0.006, lead * 1000, lead * 1000)) + "[t1]",
            (tone % (2475, QUINDAR, QUINDAR - 0.006, b2 * 1000, b2 * 1000)) + "[t2]",
            "[v][n][c][t1][t2]amix=inputs=5:normalize=0,afade=t=in:d=0.08,afade=t=out:st=%.3f:d=0.2,atrim=duration=%.3f" % (D - 0.2, D)])
        run(["ffmpeg", "-v", "error", "-y", "-i", str(c0), "-filter_complex", g, "-ar", "48000", "-ac", "1", str(out / "c0_nasa.wav")])
        print("c0_nasa: %.2f s, voice from %.2f s" % (D, v0))
    print("voice v3: %d lines -> %s" % (len(list(src.glob("*.mp3"))), out.relative_to(ROOT)))


def voice_file(F, vid, fx=None):
    if F.get("voice_dir") == "v3":
        f = V3DIR / "proc" / (vid + ("_" + fx if fx else "") + ".wav")
        return f
    if F.get("voice_dir") == "v2":
        base = V2DIR / "proc"
        for stem in (vid, vid + "_a"):
            f = base / (stem + ("_radio" if fx == "radio" else "") + ".wav")
            if f.exists():
                return f
        return base / (vid + ".wav")
    return VOICE / "lines" / (vid + ".wav")


def edit_calm(F):
    d = V / F["dir"]
    html, shots = [], []
    for i, (sid, src, at, to, ex) in enumerate(F["shots"]):
        html.append('      <div class="shot %s" id="%s"><video id="v_%s" class="clip" src="assets/%s" data-start="%s" data-duration="%s" '
                    'data-media-start="%s" data-track-index="%d" muted playsinline></video></div>'
                    % (ex.get("cls", ""), sid, sid, src_path(src), round(at, 3), round(to - at, 3), round(ex.get("ms", 0.0), 3), i + 1))
        shots.append(dict(id=sid, at=round(at, 3), to=round(to, 3)))
    E = dict(duration=F["duration"], calm=F["calm"], shots=shots, words=F["words"], panels=F["panels"], blackCards=F["blackCards"],
             dark=F.get("dark", []), fadeOut=F.get("fadeOut"))
    (d / "edit.js").write_text("// Made by video/tools/build_films.py. Don't edit by hand.\nwindow.EDIT = %s;\n" % json.dumps(E, ensure_ascii=False, indent=1))
    page = (V / "tools" / "calm_template.html").read_text().replace("{{DURATION}}", str(F["duration"])).replace("{{SHOTS}}", "\n".join(html))
    (d / "index.html").write_text(page)
    print("edit %s (calm template): %d shots, %.2f s" % (F["dir"], len(shots), F["duration"]))


def edit(F):
    if F.get("template") == "calm":
        return edit_calm(F)
    d = V / F["dir"]
    shots, html = [], []
    for i, (sid, src, at, to, ex) in enumerate(all_shots(F)):
        e = dict(id=sid, at=round(at, 3), to=round(to, 3))
        for k in ("push", "punch", "fadeIn", "fadeOut", "origin", "grade", "pushEase", "shift"):
            if k in ex:
                e[k] = ex[k]
        path = src_path(src)
        ms = ex.get("ms", 0.0)
        html.append('      <div class="shot %s" id="%s"%s><video id="v_%s" class="clip" src="assets/%s" data-start="%s" data-duration="%s" '
                    'data-media-start="%s" data-track-index="%d" muted playsinline></video></div>'
                    % (ex.get("cls", ""), sid, (' style="%s"' % ex["css"]) if ex.get("css") else "", sid, path, round(at, 3), round(to - at, 3),
                       round(ms, 3), i + 1))
        shots.append(e)
    E = dict(duration=round(F["duration"], 3), shots=shots,
             words=[dict(w, at=round(w["at"], 3), to=round(w["to"], 3)) for w in F["words"]],
             flashes=F.get("flashes", []), streaks=F.get("streaks", []), kill=F.get("kill"), dims=F.get("dims", []), blacks=F.get("blacks", []),
             letterbox=F.get("letterbox", False), cards=F.get("cards", []), look=F.get("look"), panels=F.get("panels", []),
             horizon=F.get("horizon"), film=F.get("film", False), worlds=F.get("worlds", []), camfx=F.get("camfx", []))
    (d / "edit.js").write_text("// Made by video/tools/build_films.py. Don't edit by hand.\nwindow.EDIT = %s;\n" % json.dumps(E, ensure_ascii=False, indent=1))
    page = (V / "tools" / "films_template.html").read_text().replace("{{DURATION}}", str(round(F["duration"], 3))).replace("{{SHOTS}}", "\n".join(html))
    (d / "index.html").write_text(page)
    vtt = ["WEBVTT", ""]
    texts = {"v1a": "I watch the light.", "v1b": "I read it in stops.", "v1c": "I keep your look.", "v1d": "You keep the moment.",
             "v2a": "On it.", "v2b": "Highlights first.", "v2c": "Faces next.", "v3a": "You frame. I'll handle the light.",
             "h01": "Light's changing.", "h04": "Got it.", "h06": "Done.", "h07": "Want it back?", "h08": "One key.", "h09": "Stopped.",
             "h10": "It's yours.", "h11": "Exposure… handled."}
    if F.get("voice_dir") in ("v2", "v3"):
        texts = {"h1": "New light.", "h2": "New place.", "h3": "Got it.", "h4": "Sensor.", "h5": "Iris.", "h6": "Color.", "h7": "Want it back?",
                 "h8": "One key.", "h9": "Stopped.", "h10": "It's yours.", "h11": "Exposure. Handled.",
                 "s1": "Every filmmaker knows this feeling.", "s2": "You're alone. The light is perfect…", "s3": "and then… it isn't.",
                 "s4": "A cloud. A door. A setting sun. And the moment is gone.", "s5": "Unless someone is watching the light… with you.",
                 "s6": "It reads every stop. It moves when the light moves. And it tells you why.",
                 "s7": "You frame the shot. It handles the light.", "s8": "Exposure… handled."}
    for row in F["voice"]:
        vid, at = row[0], row[1]
        f = voice_file(F, vid, row[2] if len(row) > 2 else None)
        dur = duration(f) if f.exists() else 1.0
        vtt += ["%s --> %s" % (ts(at), ts(at + dur + 0.3)), texts.get(vid, texts.get(vid.split("_")[0], "")), ""]
    (d / "captions.vtt").write_text("\n".join(vtt))
    print("edit %s: %d shots, %.2f s" % (F["dir"], len(shots), F["duration"]))


def ts(x):
    return "%02d:%02d:%06.3f" % (x // 3600, x // 60 % 60, x % 60)


def envelope(pts):
    """[(t, dB), ...] -> an ffmpeg expression for the gain at time t (linear in dB between points, flat outside)."""
    expr = "%.6f" % (10 ** (pts[-1][1] / 20))
    for (t0, d0), (t1, d1) in reversed(list(zip(pts, pts[1:]))):
        seg = "pow(10,(%.3f+(%.3f)*(t-%.3f)/%.3f)/20)" % (d0, d1 - d0, t0, max(1e-3, t1 - t0))
        expr = "if(lt(t,%.3f),%s,%s)" % (t1, seg, expr)
    return "if(lt(t,%.3f),%.6f,%s)" % (pts[0][0], 10 ** (pts[0][1] / 20), expr)


# the voice bus (the director, after the review: the voice a touch quieter, about 2.5 dB; the music back up by as much)
VOICE_GAIN = 2.2 * 10 ** (-2.5 / 20)


def mix(F):
    d = V / F["dir"] / "assets"
    m = F["music"]
    D = F["duration"] + 0.5
    inputs, g = [], []
    if m.get("beast"):                             # the hype draft's edit of "Beast", with the kill drop-out
        drop, film0, splice, kill = 20.90, -16, (64, 264), 48
        a0, seg1, b0 = drop + film0 * B, splice[0] * B, drop + splice[1] * B
        vol = "if(lt(t,{a}),1,if(lt(t,{b}),0.04,if(lt(t,{c}),0.04+0.96*(t-{b})/({c}-{b}),1)))".format(a=s(kill), b=s(kill + 3), c=s(kill + 4))
        inputs += ["-i", str(m["file"]), "-i", str(m["file"])]
        g += ["[0:a]atrim=start=%.3f:duration=%.3f,asetpts=PTS-STARTPTS[m1]" % (a0, seg1 + 0.03),
              "[1:a]atrim=start=%.3f,asetpts=PTS-STARTPTS[m2]" % b0,
              "[m1][m2]acrossfade=d=0.03:c1=tri:c2=tri,aresample=48000,aformat=channel_layouts=stereo,"
              "volume=eval=frame:volume='%s',volume=%sdB,afade=t=out:st=%.3f:d=%.3f,atrim=duration=%.3f[mus]"
              % (vol, m.get("gain", 0.0), s(68.6), s(70) - s(68.6) + 0.5, D)]
    elif not m.get("file"):                         # no track chosen yet: a silent bed
        inputs += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        g.append("[0:a]atrim=duration=%.3f[mus]" % D)
    else:
        inputs += ["-i", str(m["file"])]
        fo = m["fade_out"]
        env = "volume=eval=frame:volume='%s'," % envelope(m["env"]) if m.get("env") else ""
        g.append("[0:a]atrim=start=%.3f:duration=%.3f,asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,volume=%sdB,%s"
                 "afade=t=in:st=0:d=%.2f,afade=t=out:st=%.3f:d=%.3f,apad=whole_dur=%.3f,atrim=duration=%.3f[mus]"
                 % (m["start"], D, m.get("gain", 0.0), env, m["fade_in"], fo[0], fo[1], D, D))
    n = len(inputs) // 2
    fx = []
    for b, f, gain in F["sfx"]:
        inputs += ["-i", str(HYPE / "sfx" / f)]
        at = s(b) if m.get("beast") else b
        ms = int(at * 1000)
        g.append("[%d:a]aresample=48000,aformat=channel_layouts=stereo,volume=%sdB,adelay=%d|%d[x%d]" % (n, gain, ms, ms, n))
        fx.append("[x%d]" % n)
        n += 1
    vo = []
    for row in F["voice"]:
        vid, at = row[0], row[1]
        f = voice_file(F, vid, row[2] if len(row) > 2 else None)
        inputs += ["-i", str(f)]
        ms = int(at * 1000)
        gain = row[3] if len(row) > 3 else 0.0           # e.g. the band-limited radio line reads quieter
        g.append("[%d:a]aresample=48000,aformat=channel_layouts=stereo,volume=%sdB,adelay=%d|%d[v%d]" % (n, gain, ms, ms, n))
        vo.append("[v%d]" % n)
        n += 1
    g.append("%samix=inputs=%d:normalize=0,apad=whole_dur=%.3f,atrim=duration=%.3f,volume=%.3f,asplit=2[vo1][vo2]" % ("".join(vo), len(vo), D, D, VOICE_GAIN))
    duck = m.get("duck", "threshold=0.015:ratio=10:attack=8:release=280")
    g.append("[mus][vo1]sidechaincompress=%s:makeup=1[md]" % duck)
    if fx:
        g.append("%samix=inputs=%d:normalize=0,apad=whole_dur=%.3f,atrim=duration=%.3f[sfx]" % ("".join(fx), len(fx), D, D))
        g.append("[md][sfx][vo2]amix=inputs=3:normalize=0,atrim=duration=%.3f[mx]" % D)
    else:
        g.append("[md][vo2]amix=inputs=2:normalize=0,atrim=duration=%.3f[mx]" % D)
    g.append("[mx]aresample=48000[out]")
    out = d / "audio" / "mix.m4a"
    out.parent.mkdir(parents=True, exist_ok=True)
    pre = d / "audio" / "premaster.wav"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(g), "-map", "[out]", "-c:a", "pcm_s24le", str(pre)])
    # two passes, so the designed dynamics survive (single-pass loudnorm pumps the quiet parts and fills the silences):
    # measure the whole mix, then one fixed gain to -14 LUFS and a peak limiter
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(pre), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True)
    lufs = float([ln for ln in r.stderr.splitlines() if ln.strip().startswith("I:")][-1].split()[1])
    run(["ffmpeg", "-v", "error", "-y", "-i", str(pre), "-af", "volume=%.2fdB,alimiter=limit=0.87:attack=3:release=60:level=disabled" % (-14.0 - lufs),
         "-c:a", "aac", "-b:a", "256k", str(out)])
    pre.unlink()
    print("mix %s: %.2f s, %d voice lines, %d effects" % (F["dir"], duration(out), len(vo), len(fx)))


def heavy_ok():
    """One heavy job at a time on the Mac, and only when memory pressure is green (tools/heavy_ok.sh)."""
    r = subprocess.run([str(ROOT / "tools" / "heavy_ok.sh")])
    if r.returncode:
        raise SystemExit("Not starting: see the line above.")


def close_browsers():
    """Close any headless browser a render left behind."""
    subprocess.run(["pkill", "-f", "chrome-headless-shell|Chrome for Testing"], capture_output=True)


def render(F, draft=False):
    heavy_ok()
    d = V / F["dir"]
    hf = ["npx", "--yes", "hyperframes@0.8.167"]
    subprocess.run(hf + ["lint"], cwd=d)            # shown, not fatal: a draft may run before every 3D shot exists
    name = "%s-%s.mp4" % (F["dir"], "draft" if draft else "4k")
    (d / "renders").mkdir(exist_ok=True)
    args = ["render", "--fps", "24", "--workers", "1", "-o", "renders/" + name]
    args += ["--quality", "looks"] if draft else ["--resolution", "landscape-4k", "--quality", "delivery", "--video-frame-format", "png"]
    try:
        run(["nice", "-n", "5"] + hf + args, cwd=d)
    finally:
        close_browsers()
    print("render %s -> %s" % (F["dir"], d / "renders" / name))


FINAL = Path.home() / "Movies" / "Final Renders"
FINAL_NAMES = {"v1-abstract": "1 - Calm", "v2-hype": "2 - Hype", "v3-story": "3 - Story"}


def deliver(F):
    """A phone copy (1080p, under 30 MB) beside the 4K render, and both linked into ~/Movies/Final Renders (hard links:
    no extra disk; not the Desktop, which syncs to iCloud)."""
    heavy_ok()
    d = V / F["dir"] / "renders"
    k4 = d / ("%s-4k.mp4" % F["dir"])
    phone = d / ("%s-phone.mp4" % F["dir"])
    kbps = int(min(9000, 29.0 * 8 * 1000 / duration(k4) - 192))
    run(["nice", "-n", "10", "ffmpeg", "-v", "error", "-y", "-i", str(k4), "-vf", "scale=1920:1080:flags=lanczos", "-c:v", "libx264",
         "-preset", "slow", "-b:v", "%dk" % kbps, "-maxrate", "%dk" % int(kbps * 1.4), "-bufsize", "%dk" % (kbps * 2), "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(phone)])
    FINAL.mkdir(exist_ok=True)
    name = FINAL_NAMES[F["dir"]]
    for src, label in ((k4, "4K"), (phone, "phone")):
        link(src, FINAL / ("%s (%s).mp4" % (name, label)))
    print("deliver %s: phone copy %.1f MB; linked into %s" % (F["dir"], phone.stat().st_size / 1e6, FINAL))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["prep", "voice", "voice2", "voice3", "edit", "mix", "render", "deliver"])
    ap.add_argument("films", nargs="*", default=["v1", "v2", "v3"])
    ap.add_argument("--draft", action="store_true")
    a = ap.parse_args()
    if a.step == "voice":
        voice_lines()
    if a.step == "voice2":
        voice_v2()
    if a.step == "voice3":
        voice_v3()
    for k in a.films if a.step not in ("voice", "voice2", "voice3") else []:
        F = FILMS[k]
        {"prep": prep, "edit": edit, "mix": mix, "render": lambda F: render(F, a.draft), "deliver": deliver}[a.step](F)
