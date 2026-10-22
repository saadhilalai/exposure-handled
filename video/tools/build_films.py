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
    dir="v1-abstract", title="Exposure, Handled. (calm)", duration=52.0,
    # in the manner of the AI-lab launch films (refs R02-R04, R13): a quote hard on black; the agent speaking first, almost
    # alone; points of light gathering; a montage of the camera's own "instruments" on a pulse that quickens; silence; the
    # hit; slow, warm, lots of black; one line; the title hard on black.
    look="sepia(0.28) saturate(0.82) contrast(1.06) brightness(1.04)",
    music=dict(file=V / "music-candidates/film1/petrichor-scott-buckley/sb_petrichor.mp3", start=123.0, fade_in=1.5, fade_out=(50.0, 2.0), gain=0.0,
               env=[(0, -15), (6.2, -15), (6.8, -11), (13.0, -11), (14.0, 0), (17.35, 0), (17.5, -45), (18.15, -45), (18.2, 1)]),
    shots=[
        ("form", "3d:a_form", 6.75, 14.0, dict(ms=1.75, push=[1.0, 1.04])),
        # the instruments: each cut shorter than the last (0.85 -> 0.15 s)
        ("m_eye", "3d:h_eye", 14.0, 14.85, dict(ms=0.1, push=[1.0, 1.02])),
        ("m_iris1", "3d:h_iris", 14.85, 15.55, dict(ms=0.15, push=[1.0, 1.02])),
        ("m_dial", "3d:h_dial", 15.55, 16.1, dict(ms=0.1)),
        ("m_ring", "3d:h_ring", 16.1, 16.55, dict(ms=0.25)),
        ("m_iris2", "3d:h_iris", 16.55, 16.9, dict(ms=1.15)),
        ("m_agent", "3d:h_agent", 16.9, 17.2, dict(ms=1.6)),
        ("m_iris3", "3d:h_iris", 17.2, 17.45, dict(ms=1.65)),
        ("solid", "3d:a_solid", 18.2, 21.1, dict(ms=0.1, push=[1.0, 1.02])),
        ("open", "3d:a_open", 20.7, 28.7, dict(fadeIn=0.4, push=[1.0, 1.02])),
        ("agent", "3d:a_agent", 28.3, 35.3, dict(fadeIn=0.4, push=[1.0, 1.03])),
        ("close", "3d:a_close", 34.9, 43.875, dict(fadeIn=0.4, push=[1.0, 1.02])),
    ],
    panels="montage",
    cards=[(0.0, 6.75), (17.45, 18.2), (47.0, 52.0)],
    words=[
        dict(at=0.8, to=4.9, style="quote", html="I propose to consider the question,", y=45, cut=True),
        dict(at=2.3, to=4.9, style="quote", html="<em>‘Can machines think?’</em>", y=55, cut=True),
        dict(at=5.1, to=6.5, style="name", html="Alan Turing, 1950", cut=True),
        dict(at=36.6, to=41.4, style="line", html="A camera that thinks", y=45, cut=True),
        dict(at=36.6, to=41.4, style="line", html="like a <em>cinematographer.</em>", y=56, cut=True),
        dict(at=47.0, to=52.0, style="title", html="Exposure, <em>Handled</em>.", y=46, size=112, cut=True, out=False),
        dict(at=48.6, to=52.0, style="link", html=SITE_URL, y=58, size=34, cut=True, out=False),
    ],
    voice=[("v1a", 7.2), ("v1b", 9.4), ("v1c", 11.6), ("v1d", 13.6), ("h11", 47.4)],
    sfx=[(18.2, "lowFrequency_explosion_000.ogg", -12)],
    flashes=[(18.2, 0.45, 0.6)],
    dims=[],
    blacks=[(50.8, 52.0, 0.0, 1.0)],
)

# The hype film keeps the hype draft's music edit: "Beast" (115 BPM), film beat 0 = track beat -16, the drop at film
# beat 16, a splice at film beat 64 to the track's last bar, and the music dropping out for the kill switch.
V2 = dict(
    dir="v2-hype", title="Exposure, Handled. (hype)", duration=s(70),
    music=dict(file=HYPE / "music" / "beast.mp3", beast=True),
    shots=[
        ("reveal", "3d:h_reveal", 0, s(4), dict(push=[1.0, 1.04])),
        ("dial", "3d:h_dial", s(4), s(5.5), dict(punch=1.06)),
        ("vents", "3d:h_vents", s(5.5), s(7), dict(punch=1.06)),
        ("ring", "3d:h_ring", s(7), s(8), dict(ms=s(0.5), punch=1.06)),
        ("orbit", "3d:h_orbit", s(8), s(12), dict(punch=1.04)),
        ("smash", "3d:h_smash", s(12), s(16), dict(push=[1.0, 1.12], pushEase="power2.in")),
        ("burst", "3d:h_burst", s(16), s(24), dict(punch=1.08)),
        ("iris", "3d:h_iris", s(24), s(28), dict(punch=1.05)),
        ("agent", "3d:h_agent", s(28), s(32), dict(punch=1.04)),
        ("eye", "3d:h_eye", s(32), s(34), dict(punch=1.03)),
        ("dial2", "3d:h_dial", s(34), s(35), dict(ms=s(0.4), punch=1.05)),
        ("ring2", "3d:h_ring", s(35), s(36), dict(ms=s(0.4), punch=1.05)),
        ("swarm", "3d:h_swarm", s(36), s(40), dict(punch=1.06)),
        ("burst2", "3d:h_burst", s(40), s(44), dict(ms=s(4), punch=1.05)),
        ("iris2", "3d:h_iris", s(44), s(47), dict(ms=0.0, punch=1.04)),
        ("kill", "3d:h_kill", s(47), s(50), dict(punch=1.02)),
        ("slam", "3d:h_slam", s(50), s(58), dict(push=[1.0, 1.03])),
    ],
    cards=[(s(58), s(70))],
    words=[
        dict(at=s(0.25), to=s(1.45), style="huge", html="A camera"),
        dict(at=s(1.5), to=s(2.95), style="huge", html="that thinks", size=250),
        dict(at=s(3.0), to=s(6.4), style="serif", html="like a <em>cinematographer.</em>"),
        dict(at=s(24.15), to=s(27.7), style="huge", html="It sees."),
        dict(at=s(28.15), to=s(31.7), style="huge", html="It decides.", size=250),
        dict(at=s(58), to=s(70), style="title", html="Exposure, <em>Handled</em>.", y=46, cut=True, out=False),
        dict(at=s(62), to=s(70), style="link", html=SITE_URL, y=60, cut=True, out=False),
    ],
    voice=[("h01", s(8.2)), ("v2a", s(12.2)), ("v2b", s(29.4)), ("v2c", s(30.9)), ("h06", s(33.2)), ("h07", s(44.2)),
           ("h08", s(46.2)), ("h09", s(48.35)), ("h10", s(50.3)), ("h11", s(58.3))],
    sfx=[(0, "impactPunch_heavy_000.ogg", -6), (0, "swish-7.wav", -9), (4, "impactMetal_light_001.ogg", -12), (5.5, "swish-3.wav", -12),
         (7, "impactMetal_light_003.ogg", -12), (8, "swish-11.wav", -10), (12, "swish-7.wav", -11),
         (16, "lowFrequency_explosion_000.ogg", -3), (16, "impactPunch_heavy_002.ogg", -6), (24, "impactMetal_002.ogg", -12),
         (25, "impactMetal_002.ogg", -12), (26, "impactMetal_002.ogg", -12), (27, "impactMetal_002.ogg", -11), (28, "forceField_001.ogg", -14),
         (36, "swish-3.wav", -10), (40, "swish-7.wav", -10), (45, "impactMetal_002.ogg", -13), (46, "impactMetal_002.ogg", -13),
         (48, "lowFrequency_explosion_001.ogg", -4), (48, "impactPlate_heavy_002.ogg", -8),
         (52, "lowFrequency_explosion_000.ogg", -2), (52, "impactMetal_heavy_001.ogg", -8), (52, "explosionCrunch_002.ogg", -10),
         (58, "impactBell_heavy_001.ogg", -14), (58, "impactPunch_heavy_000.ogg", -10)],
    flashes=[(s(16), 0.85, 0.35), (s(24), 0.35, 0.2), (s(28), 0.3, 0.2), (s(36), 0.4, 0.25), (s(52), 0.9, 0.5)],
    streaks=[(s(8), 38, 1), (s(16.02), 52, -1), (s(36), 30, 1), (s(52.02), 60, -1)],
    kill=(s(48), s(50)),
    dims=[],
    blacks=[(s(68.6), s(70), 0.0, 1.0)],
)

# The story film: Saad's own footage (personal days out on an Osmo Pocket 3: no client work, no faces), graded to one
# look, the light falling in the grade, the agent catching it. Cut to the hits of "Cassini" (3.18, 6.02, 8.98, 10.98, 13.82,
# 16.78, 19.60, 22.70, 25.60, 28.66, 37.34 and the big one at 43.04 s).
ICLOUD = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
FOOTAGE = {   # id: (source, in, out, crop or None, "709" or "hlg")
    "field": (ICLOUD / "DJI_20260430183909_0314_D.MP4", 9.0, 21.0, None, "709"),
    "beach": (ICLOUD / "DJI_20260426192545_0352_D.MP4", 0.0, 5.0, None, "hlg"),
    "fence": (ICLOUD / "DJI_20260428180930_0354_D.MP4", 0.5, 6.6, None, "hlg"),
    "head": (ICLOUD / "DJI_20260425202029_0011_D.MP4", 16.2, 17.2, "crop=2560:1440:1280:720", "709"),
    "train": (ICLOUD / "DJI_20260428180846_0353_D.MP4", 0.0, 11.6, None, "hlg"),
}
DARK = 0.42
V3 = dict(
    dir="v3-story", title="Exposure, Handled. (story)", duration=55.0, letterbox=True,
    music=dict(file=V / "music-candidates/film3/cassini-scott-buckley/sb_cassini.mp3", start=180.4, fade_in=0.3, fade_out=(53.4, 1.6), gain=-2.0,
               env=[(0, 0), (28.05, 0), (28.2, -26), (28.6, -26), (28.66, 0)]),
    shots=[
        ("field_a", "ft:field.mp4", 10.98, 16.78, dict(push=[1.0, 1.06])),
        ("beach", "ft:beach.mp4", 16.78, 19.60, dict(ms=0.3, push=[1.04, 1.0])),
        ("fence", "ft:fence.mp4", 19.60, 25.60, dict(push=[1.0, 1.05], grade=[(19.6, 1.0, 1.0), (20.3, 1.0, 1.0), (22.4, DARK, 0.7, "power2.inOut")])),
        ("beach_dark", "ft:beach.mp4", 25.60, 26.80, dict(ms=3.2, push=[1.08, 1.12], grade=[(25.6, DARK, 0.7)])),
        ("head", "ft:head.mp4", 26.80, 27.60, dict(push=[1.0, 1.04], grade=[(26.8, DARK, 0.7)])),
        ("train_q", "ft:train.mp4", 27.60, 28.10, dict(ms=0.2, push=[1.1, 1.14], grade=[(27.6, DARK, 0.7)])),
        ("catch", "3d:s_catch", 28.66, 32.60, dict(punch=1.03)),
        ("train", "ft:train.mp4", 32.60, 43.04, dict(ms=1.0, push=[1.0, 1.07], grade=[(32.6, DARK, 0.7), (33.4, 1.0, 1.0, "power3.out")])),
        ("field_b", "ft:field.mp4", 43.04, 47.60, dict(ms=7.0, push=[1.08, 1.0], pushEase="power1.out")),
        ("hero", "3d:s_hero", 47.00, 50.20, dict(fadeIn=0.6, push=[1.0, 1.04])),
    ],
    words=[
        dict(at=3.18, to=8.9, style="quote", html="There is nothing in this world", y=45, cut=True),
        dict(at=6.02, to=8.9, style="quote", html="that does not have a <em>decisive moment.</em>", y=55, cut=True),
        dict(at=8.98, to=10.8, style="name", html="Cardinal de Retz", cut=True),
        dict(at=13.82, to=16.7, style="line", html="The light won’t wait.", cut=True),
        dict(at=22.7, to=25.5, style="line", html="Neither will the moment.", cut=True),
        dict(at=43.5, to=47.3, style="line", html="What if your camera had", y=45, cut=True),
        dict(at=43.5, to=47.3, style="line", html="a <em>cinematographer</em> inside it?", y=56, cut=True),
        dict(at=50.2, to=55.0, style="title", html="Exposure, <em>Handled</em>.", y=46, cut=True, out=False),
        dict(at=51.6, to=55.0, style="link", html=SITE_URL, y=60, cut=True, out=False),
    ],
    voice=[("h01", 20.2), ("h04", 30.2), ("v3a", 47.8)],
    sfx=[(28.66, "impactPunch_heavy_002.ogg", -14), (43.04, "lowFrequency_explosion_000.ogg", -8)],
    flashes=[(28.66, 0.35, 0.3), (43.04, 0.7, 0.6)],
    cards=[(0.0, 10.98), (50.2, 55.0)],
    dims=[(13.6, 13.9, 0.0, 0.3), (16.5, 16.78, 0.3, 0.0), (22.5, 22.8, 0.0, 0.3), (25.35, 25.6, 0.3, 0.0),
          (43.2, 43.5, 0.0, 0.35), (47.0, 47.4, 0.35, 0.0)],
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
V1["panels"] = montage()
V1["sfx"] = V1["sfx"] + [(p["at"], "impactGeneric_light_002.ogg", -27) for p in V1["panels"]]


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
    src, t0, t1, crop, kind = FOOTAGE[name.rsplit(".", 1)[0]]
    vf = ",".join(x for x in (crop, (HLG if kind == "hlg" else "") + LOOK, "scale=3840:2160:flags=lanczos", "format=yuv420p") if x)
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(["nice", "-n", "10", "ffmpeg", "-v", "error", "-y", "-ss", str(t0), "-t", str(t1 - t0), "-i", str(src), "-an", "-vf", vf,
         "-c:v", "libx264", "-preset", "medium", "-crf", "15", "-g", "24", "-keyint_min", "24",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
         "-movflags", "+faststart", str(dst)])


# ---------------------------------------------------------------- steps
def prep(F):
    d = V / F["dir"]
    a = d / "assets"
    for sub in ("fonts", "vendor"):
        (a / sub).mkdir(parents=True, exist_ok=True)
    for f in (HYPE / "fonts").iterdir():
        link(f, a / "fonts" / f.name)
    link(HYPE / "vendor" / "gsap.min.js", a / "vendor" / "gsap.min.js")
    link(HYPE / "grain.png", a / "grain.png")
    (d / "meta.json").write_text(json.dumps({"id": "exposure-handled-" + F["dir"], "name": "exposure-handled-" + F["dir"],
                                             "createdAt": "2026-10-22T05:00:00.000Z"}, indent=2) + "\n")
    (d / "package.json").write_text(json.dumps({"name": "camera-agent-" + F["dir"], "private": True, "type": "module", "scripts": {
        "dev": "npx --yes hyperframes@0.8.167 preview", "check": "npx --yes hyperframes@0.8.167 check",
        "render": "npx --yes hyperframes@0.8.167 render"}}, indent=2) + "\n")
    missing = []
    for sid, src, *_ in all_shots(F):
        if src.startswith("ft:"):
            footage(src[3:], a / "footage" / src[3:])
        if src.startswith("3d:"):
            g = glow(src[3:])
            if g:
                link(g, a / "3d" / (src[3:] + ".mp4"))
            else:                                   # a black stand-in, so a draft can render before the shot exists
                missing.append(src[3:])
                ph = a / "3d" / (src[3:] + ".mp4")
                if not ph.exists():
                    ph.parent.mkdir(parents=True, exist_ok=True)
                    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x101010:s=1920x1080:r=24:d=12", "-c:v", "libx264",
                         "-g", "24", "-pix_fmt", "yuv420p", str(ph)])
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


def edit(F):
    d = V / F["dir"]
    shots, html = [], []
    for i, (sid, src, at, to, ex) in enumerate(all_shots(F)):
        e = dict(id=sid, at=round(at, 3), to=round(to, 3))
        for k in ("push", "punch", "fadeIn", "fadeOut", "origin", "grade", "pushEase"):
            if k in ex:
                e[k] = ex[k]
        kind, name = src.split(":", 1)
        path = "3d/%s.mp4" % name if kind == "3d" else "footage/%s" % name
        ms = ex.get("ms", 0.0)
        html.append('      <div class="shot" id="%s"><video id="v_%s" class="clip" src="assets/%s" data-start="%s" data-duration="%s" '
                    'data-media-start="%s" data-track-index="%d" muted playsinline></video></div>'
                    % (sid, sid, path, round(at, 3), round(to - at, 3), round(ms, 3), i + 1))
        shots.append(e)
    E = dict(duration=round(F["duration"], 3), shots=shots,
             words=[dict(w, at=round(w["at"], 3), to=round(w["to"], 3)) for w in F["words"]],
             flashes=F.get("flashes", []), streaks=F.get("streaks", []), kill=F.get("kill"), dims=F.get("dims", []), blacks=F.get("blacks", []),
             letterbox=F.get("letterbox", False), cards=F.get("cards", []), look=F.get("look"), panels=F.get("panels", []))
    (d / "edit.js").write_text("// Made by video/tools/build_films.py. Don't edit by hand.\nwindow.EDIT = %s;\n" % json.dumps(E, ensure_ascii=False, indent=1))
    page = (V / "tools" / "films_template.html").read_text().replace("{{DURATION}}", str(round(F["duration"], 3))).replace("{{SHOTS}}", "\n".join(html))
    (d / "index.html").write_text(page)
    vtt = ["WEBVTT", ""]
    texts = {"v1a": "I watch the light.", "v1b": "I read it in stops.", "v1c": "I keep your look.", "v1d": "You keep the moment.",
             "v2a": "On it.", "v2b": "Highlights first.", "v2c": "Faces next.", "v3a": "You frame. I'll handle the light.",
             "h01": "Light's changing.", "h04": "Got it.", "h06": "Done.", "h07": "Want it back?", "h08": "One key.", "h09": "Stopped.",
             "h10": "It's yours.", "h11": "Exposure… handled."}
    for vid, at in F["voice"]:
        f = VOICE / "lines" / (vid + ".wav")
        dur = duration(f) if f.exists() else 1.0
        vtt += ["%s --> %s" % (ts(at), ts(at + dur + 0.3)), texts[vid], ""]
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
              "volume=eval=frame:volume='%s',afade=t=out:st=%.3f:d=%.3f,atrim=duration=%.3f[mus]" % (vol, s(68.6), s(70) - s(68.6) + 0.5, D)]
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
    for vid, at in F["voice"]:
        f = VOICE / "lines" / (vid + ".wav")
        inputs += ["-i", str(f)]
        ms = int(at * 1000)
        g.append("[%d:a]aresample=48000,aformat=channel_layouts=stereo,adelay=%d|%d[v%d]" % (n, ms, ms, n))
        vo.append("[v%d]" % n)
        n += 1
    g.append("%samix=inputs=%d:normalize=0,apad=whole_dur=%.3f,atrim=duration=%.3f,volume=2.2,asplit=2[vo1][vo2]" % ("".join(vo), len(vo), D, D))
    g.append("[mus][vo1]sidechaincompress=threshold=0.02:ratio=7:attack=10:release=320:makeup=1[md]")
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


def render(F, draft=False):
    d = V / F["dir"]
    hf = ["npx", "--yes", "hyperframes@0.8.167"]
    subprocess.run(hf + ["lint"], cwd=d)            # shown, not fatal: a draft may run before every 3D shot exists
    name = "%s-%s.mp4" % (F["dir"], "draft" if draft else "4k")
    (d / "renders").mkdir(exist_ok=True)
    args = ["render", "--fps", "24", "--workers", "2", "-o", "renders/" + name]
    args += ["--quality", "looks"] if draft else ["--resolution", "landscape-4k", "--quality", "delivery", "--video-frame-format", "png"]
    run(["nice", "-n", "5"] + hf + args, cwd=d)
    print("render %s -> %s" % (F["dir"], d / "renders" / name))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["prep", "voice", "edit", "mix", "render"])
    ap.add_argument("films", nargs="*", default=["v1", "v2", "v3"])
    ap.add_argument("--draft", action="store_true")
    a = ap.parse_args()
    if a.step == "voice":
        voice_lines()
    for k in a.films if a.step != "voice" else []:
        F = FILMS[k]
        {"prep": prep, "edit": edit, "mix": mix, "render": lambda F: render(F, a.draft)}[a.step](F)
