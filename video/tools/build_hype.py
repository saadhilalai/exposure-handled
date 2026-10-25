"""The hype cut: its edit, voice and soundtrack (video/tools/capture_hype.py renders its 3D shots).

    python video/tools/build_hype.py voice     the chosen voice's takes -> assets/voice/lines/<id>.wav, trimmed tight
    python video/tools/build_hype.py edit      the edit below (in beats of the music) -> edit.js, index.html, captions.vtt
    python video/tools/build_hype.py mix       music + effects + voice -> assets/audio/mix.m4a
    python video/tools/build_hype.py all       (also: --voice imogen|sloane|orion)

Everything is keyed in beats of the music, so cuts, words, voice lines and hits land on the beat. Every real number
comes from site/data/site.json (the Oct 19 Sony cinema camera logs), never typed by hand.

Media (not in git; see video/CREDITS.md for the sources):
    assets/music/beast.mp3      "Beast" by Sascha Ende, CC BY 4.0, https://ende.app/en/song/10415-beast
    assets/sfx/*                Kenney "Impact Sounds" + "Sci-fi Sounds" (CC0), OpenGameArt "Swishes" by artisticdude (CC0)
    assets/voice/takes/<voice>/h01..h11.mp3   the AI voice's takes, one line each (ids in VOICE below)
    assets/real, assets/dash, assets/stills    copies of site/media/real, site/media/screens and the stand-in clip
"""
import argparse
import html
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HYPE = ROOT / "video" / "hype"
A = HYPE / "assets"

# ---------------------------------------------------------------- the music and its beat grid
BPM = 115.0
B = 60 / BPM                       # one beat, seconds
TRACK_DROP = 20.90                 # "Beast": its first drop, track seconds (beat 0 of its grid; measured from the kicks)
FILM0 = -16                        # film beat 0 = track beat -16: the last four bars of the riser
SPLICE = (64, 264)                 # at film beat 64 jump to track beat 264: its last bar and final hit (both bar starts)
END = 70                           # film length, beats (36.5 s)
KILL = (48, 50)                    # the kill switch: the music drops out (its own break, track beats 32-35), red wash
s = lambda b: round(b * B, 3)      # film beat -> film seconds

# ---------------------------------------------------------------- the edit (film beats)
SHOTS = [
    dict(id="orbit", at=0, to=2, src="3d/orbit.mp4", sb=0, tag="ill", push=[1.0, 1.05]),
    dict(id="lens", at=2, to=4, src="3d/lens.mp4", sb=0.4, tag="ill", push=[1.0, 1.06]),
    dict(id="vf", at=4, to=8, src="3d/vf.mp4", sb=0, tag="ill", push=[1.0, 1.0]),
    dict(id="real1", at=8, to=12, frames="test1", tag="real", push=[1.02, 1.12], punch=1.12),
    dict(id="dive", at=12, to=28, src="3d/dive.mp4", sb=0, tag="ill", push=[1.0, 1.0]),
    dict(id="decide", at=28, to=36, src="3d/decide.mp4", sb=0, tag="ill", push=[1.0, 1.04]),
    dict(id="standin", at=36, to=38, src="stills/clipA.mp4", ss=2.4, tag="stand", push=[1.14, 1.22], punch=1.1, origin="50% 22%"),   # crops the clip's own label: the tag says it
    dict(id="real3", at=38, to=41, frames="test3", tag="real", push=[1.02, 1.1], punch=1.1),
    dict(id="dash1", at=41, to=41.5, img="dash/falsecolor.jpg", tag="ph", push=[1.18, 1.24], punch=1.2),
    dict(id="dash2", at=41.5, to=42, img="dash/auto.jpg", tag="ph", push=[1.3, 1.38], punch=1.15),
    dict(id="swarm", at=42, to=46, src="3d/swarm.mp4", sb=0, tag="ill", push=[1.0, 1.03]),
    dict(id="kill", at=46, to=50, src="3d/kill.mp4", sb=0, tag="ill", push=[1.0, 1.06]),
    dict(id="slam", at=50, to=END, src="3d/slam.mp4", sb=0, tag="ill", tag_to=64, push=[1.0, 1.0]),
]
TAGS = {"ill": "3D ILLUSTRATION", "real": "REAL · SONY CINEMA CAMERA · OCT 19 · SPED UP", "ph": "PLACEHOLDER · REAL DASHBOARD, FAKE CAMERA",
        "stand": "STAND-IN · UNTIL SATURDAY’S FOOTAGE"}
TICKS1 = [10.4, 10.75, 11.1, 11.45, 11.8]          # test 1's five ISO steps, sped up onto the beat
FLIPS3 = {"ShutterSpeed": [38.6], "FNumber": [39.1], "IsoSensitivity": [39.6, 39.85, 40.1], "Colortemp": [40.45]}
WORDS = [
    dict(at=0.25, to=1.45, style="caps", html="A camera"),
    dict(at=1.5, to=2.95, style="caps", html="that thinks"),
    dict(at=3.0, to=6.5, style="serif", html='<span class="pre">like a</span><em>cinematographer.</em>'),
    dict(at=24.8, to=27.7, style="caps", html='It sees<span class="dot">.</span>'),
    dict(at=28.25, to=31.7, style="caps", html='It decides<span class="dot">.</span>'),
    dict(at=54.0, to=END, style="title", html='Exposure, <em>Handled</em><span class="dot">.</span>', out=False),
]
FLASHES = [(0, .9, .3), (2, .3, .14), (8, .7, .25), (16, .45, .3), (24.6, .25, .3), (28, .3, .2), (29, .22, .12), (30, .22, .12),
           (31, .22, .12), (36, .4, .18), (38, .4, .18), (41, .5, .15), (41.5, .3, .1), (42, .35, .18), (48.9, .3, .16),
           (52, 1.0, .45), (54, .22, .3)]
STREAKS = [(0, 46, 1), (16, 52, -1), (24.6, 40, 1), (41, 60, -1), (52, 50, 1), (52.06, 56, -1), (54, 44, 1)]
END_CARD = 64
FADE = (68.6, END)

# the voice: id, film beat, subtitle (ids match the takes: assets/voice/takes/<voice>/<id>.mp3)
VOICE = [("h02", 8.2, "Too hot."), ("h03", 10.15, "Coming down."), ("h04", 12.15, "Got it."),
         ("h01", 36.15, "Light’s changing."), ("h05", 38.15, "Interview look."), ("h06", 41.2, "Done."),
         ("h07", 44.2, "Want it back?"), ("h08", 46.0, "One key."), ("h09", 48.35, "Stopped."),
         ("h10", 50.3, "It’s yours."), ("h11", 54.0, "Exposure… handled.")]

# effects: film beat, file, gain dB
SFX = [(0, "impactPunch_heavy_000.ogg", -6), (0, "swish-7.wav", -9), (2, "swish-3.wav", -11), (8, "impactMetal_light_001.ogg", -10),
       *[(t, "impactGeneric_light_002.ogg", -15) for t in TICKS1], (11.85, "impactMetal_light_003.ogg", -14),
       (16, "lowFrequency_explosion_000.ogg", -3), (16, "impactPunch_heavy_002.ogg", -6), (24.6, "forceField_001.ogg", -13),
       (29, "impactMetal_002.ogg", -12), (30, "impactMetal_002.ogg", -12), (31, "impactMetal_002.ogg", -12),
       (36, "swish-3.wav", -10), (38, "swish-7.wav", -10), *[(t, "impactGeneric_light_002.ogg", -15) for v in FLIPS3.values() for t in v],
       (41, "impactPunch_heavy_000.ogg", -12), (42, "swish-11.wav", -10),
       (48, "lowFrequency_explosion_001.ogg", -4), (48, "impactPlate_heavy_002.ogg", -8), (48.9, "impactPunch_heavy_002.ogg", -6),
       (52, "lowFrequency_explosion_000.ogg", -2), (52, "impactMetal_heavy_001.ogg", -8), (52, "explosionCrunch_002.ogg", -10),
       (54, "impactBell_heavy_001.ogg", -15)]


def site():
    return json.loads((ROOT / "site" / "data" / "site.json").read_text())


def duration(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                capture_output=True, text=True, check=True).stdout)


# ---------------------------------------------------------------- voice
def voice(name):
    out = A / "voice" / "lines"
    out.mkdir(parents=True, exist_ok=True)
    trim = ("silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.01,areverse,"
            "silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.04,areverse,highpass=f=80")
    for vid, _, _ in VOICE:
        src = A / "voice" / "takes" / name / (vid + ".mp3")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", trim, "-ar", "48000", "-ac", "1", str(out / (vid + ".wav"))], check=True)
    (out / "VOICE").write_text(name + "\n")
    print("voice: %s, %d lines trimmed into %s" % (name, len(VOICE), out.relative_to(ROOT)))


# ---------------------------------------------------------------- the edit -> edit.js, index.html, captions.vtt
def edit():
    d = site()
    t1, t3 = d["tests"]["test1"], d["tests"]["test3"]
    iso1 = [c for c in t1["changes"] if c["setting"] == "IsoSensitivity"]
    assert len(iso1) == len(TICKS1), "test 1 has %d ISO steps" % len(iso1)
    num = lambda v: v.replace("ISO ", "")
    shots, huds, statuses, tags, html_shots = [], [], [], [], []
    track = 1
    for sh in SHOTS:
        at, to = s(sh["at"]), s(sh["to"])
        e = dict(id=sh["id"], at=at, to=to, push=sh.get("push"), punch=sh.get("punch"), origin=sh.get("origin"))
        if "src" in sh:
            ms = s(sh["sb"]) if "sb" in sh else sh["ss"]
            html_shots.append('      <div class="shot" id="%s"><video id="v_%s" class="clip" src="assets/%s" data-start="%s" data-duration="%s" '
                              'data-media-start="%s" data-track-index="%d" muted playsinline></video></div>'
                              % (sh["id"], sh["id"], sh["src"], at, round(to - at, 3), round(ms, 3), track))
            track += 1
        elif "img" in sh:
            e["img"] = True
            html_shots.append('      <div class="shot" id="%s"><img src="assets/%s" alt=""></div>' % (sh["id"], sh["img"]))
        else:                                       # a run of real live-view frames, with the camera HUD
            if sh["frames"] == "test1":
                frames = [dict(src="real/test1_0%d.jpg" % (i + 1), at=at if i == 0 else s(TICKS1[i - 1])) for i in range(5)]
                cells = [dict(k="ISO", **{"from": num(iso1[0]["from"])}, steps=[[s(b), num(c["to"])] for b, c in zip(TICKS1, iso1)])]
                statuses += [dict(shot=sh["id"], kind="ai", text="AGENT · AUTO", at=s(8.1), to=s(11.8)),
                             dict(shot=sh["id"], kind="good", text=t1["settled_status"].split(":")[0].upper(), at=s(11.85), to=to)]
            else:
                by = {}
                for c in t3["changes"]:
                    by.setdefault(c["setting"], []).append(c)
                flips = sorted((b, c) for k, v in FLIPS3.items() for b, c in zip(v, by[k]))
                frames = [dict(src="real/test3_01.jpg", at=at)] + [dict(src="real/test3_0%d.jpg" % (i + 2), at=s(b))
                                                                    for i, (b, c) in enumerate(flips[:2] + flips[2:5:2] + flips[5:])]
                names = [("ShutterSpeed", "SHUTTER"), ("FNumber", "IRIS"), ("IsoSensitivity", "ISO"), ("Colortemp", "WB")]
                cells = [dict(k=label, **{"from": num(by[k][0]["from"])}, steps=[[s(b), num(c["to"])] for b, c in zip(FLIPS3[k], by[k])])
                         for k, label in names]
                statuses += [dict(shot=sh["id"], kind="ai", text=t3["look"].upper() + " LOOK", at=s(38.1), to=s(40.7)),
                             dict(shot=sh["id"], kind="good", text=t3["settled_status"].split(":")[0].upper(), at=s(40.75), to=to)]
            e["frames"] = frames
            huds.append(dict(id=sh["id"] + "_hud", at=at + 0.05, cells=cells))
            imgs = "".join('<img src="assets/%s" alt="">' % f["src"] for f in frames)
            cells_html = "".join('<div class="cell"><div class="k">%s</div><div class="v">%s</div></div>' % (c["k"], c["from"]) for c in cells)
            html_shots.append('      <div class="shot" id="%s">%s<div class="hud%s" id="%s_hud">%s</div></div>'
                              % (sh["id"], imgs, " big" if len(cells) == 1 else "", sh["id"], cells_html))
        shots.append(e)
        # one tag per run of shots with the same kind
        tto = s(sh.get("tag_to", sh["to"]))
        if tags and tags[-1]["kind"] == sh["tag"] and abs(tags[-1]["to"] - at) < 1e-6:
            tags[-1]["to"] = tto
        else:
            tags.append(dict(kind=sh["tag"], text=TAGS[sh["tag"]], at=at, to=tto))
    edit_js = dict(
        duration=s(END), bpm=BPM, shots=shots, huds=huds, statuses=statuses, tags=tags,
        words=[dict(at=s(w["at"]), to=s(w["to"]), style=w["style"], html=w["html"], out=w.get("out", True)) for w in WORDS],
        stat=dict(n=t1["kill"]["ms_to_stop"], at=s(48.9), to=s(50.6),
                  label="KILL SWITCH · <b>REAL</b> TEST · SONY CINEMA CAMERA · OCT 19"),
        flashes=[[s(b), o, dd] for b, o, dd in FLASHES], streaks=[[s(b), top, dr] for b, top, dr in STREAKS],
        kill=[s(KILL[0]), s(KILL[1])], end=s(END_CARD), dimUnderEnd=SHOTS[-1]["id"], fadeOut=[s(FADE[0]), s(FADE[1])],
        fine=("Narration: an AI voice, speaking as the agent · Music: “Beast” by Sascha Ende (ende.app), CC BY 4.0<br>"
              "3D: illustration · REAL: the Oct 19 test on a Sony cinema camera, sped up · PLACEHOLDER: the real dashboard on a fake camera · "
              "STAND-IN: until Saturday’s footage"),
        source=d["source"])
    (HYPE / "edit.js").write_text("// Made by video/tools/build_hype.py (the edit, in seconds; the source is in beats there). Don't edit by hand.\n"
                                  "window.EDIT = %s;\n" % json.dumps(edit_js, ensure_ascii=False, indent=1))
    page = (ROOT / "video" / "tools" / "hype_template.html").read_text().replace("{{DURATION}}", str(s(END))).replace("{{SHOTS}}", "\n".join(html_shots))
    (HYPE / "index.html").write_text(page)
    # captions (a file for players; the cut itself carries no subtitles)
    vtt = ["WEBVTT", ""]
    for vid, b, text in VOICE:
        f = A / "voice" / "lines" / (vid + ".wav")
        dur = duration(f) if f.exists() else 0.9
        a = s(b)
        vtt += [vid, "%s --> %s" % (ts(a), ts(a + dur + 0.3)), text, ""]
    (HYPE / "captions.vtt").write_text("\n".join(vtt))
    print("edit: %d shots, %.2f s; wrote edit.js, index.html, captions.vtt" % (len(SHOTS), s(END)))


def ts(x):
    return "%02d:%02d:%06.3f" % (x // 3600, x // 60 % 60, x % 60)


# ---------------------------------------------------------------- the soundtrack
def mix():
    music = A / "music" / "beast.mp3"
    a0 = TRACK_DROP + FILM0 * B                     # track seconds at film beat 0
    seg1 = SPLICE[0] * B                            # film seconds before the splice
    b0 = TRACK_DROP + SPLICE[1] * B                 # track seconds after it
    D = s(END) + 0.6
    # the kill: the music drops out for three beats, then its own fill builds back in over the beat before the slam
    vol = "if(lt(t,{a}),1,if(lt(t,{b}),0.04,if(lt(t,{c}),0.04+0.96*(t-{b})/({c}-{b}),1)))".format(a=s(KILL[0]), b=s(KILL[0] + 3), c=s(KILL[0] + 4))
    inputs = ["-i", str(music), "-i", str(music)]
    g = ["[0:a]atrim=start=%.3f:duration=%.3f,asetpts=PTS-STARTPTS[m1]" % (a0, seg1 + 0.03),
         "[1:a]atrim=start=%.3f,asetpts=PTS-STARTPTS[m2]" % (b0 - 0.0),
         "[m1][m2]acrossfade=d=0.03:c1=tri:c2=tri,aresample=48000,aformat=channel_layouts=stereo,"
         "volume=eval=frame:volume='%s',afade=t=out:st=%.3f:d=%.3f,atrim=duration=%.3f[mus]" % (vol, s(FADE[0]), s(FADE[1]) - s(FADE[0]) + 0.6, D)]
    n = 2
    fx = []
    for b, f, gain in SFX:
        inputs += ["-i", str(A / "sfx" / f)]
        ms = int(s(b) * 1000)
        g.append("[%d:a]aresample=48000,aformat=channel_layouts=stereo,volume=%sdB,adelay=%d|%d[x%d]" % (n, gain, ms, ms, n))
        fx.append("[x%d]" % n); n += 1
    g.append("%samix=inputs=%d:normalize=0,apad=whole_dur=%.3f,atrim=duration=%.3f[sfx]" % ("".join(fx), len(fx), D, D))
    vo = []
    for vid, b, _ in VOICE:
        f = A / "voice" / "lines" / (vid + ".wav")
        if not f.exists():
            continue
        inputs += ["-i", str(f)]
        ms = int(s(b) * 1000)
        g.append("[%d:a]aresample=48000,aformat=channel_layouts=stereo,adelay=%d|%d[v%d]" % (n, ms, ms, n))
        vo.append("[v%d]" % n); n += 1
    if vo:
        g.append("%samix=inputs=%d:normalize=0,apad=whole_dur=%.3f,atrim=duration=%.3f,"
                 "acompressor=threshold=0.1:ratio=3:attack=5:release=80:makeup=1.5,asplit=2[vo1][vo2]" % ("".join(vo), len(vo), D, D))
        g.append("[mus][vo1]sidechaincompress=threshold=0.03:ratio=5:attack=15:release=260:makeup=1[md]")
        g.append("[md][sfx][vo2]amix=inputs=3:normalize=0,atrim=duration=%.3f[mx]" % D)
    else:
        g.append("[mus][sfx]amix=inputs=2:normalize=0,atrim=duration=%.3f[mx]" % D)
    g.append("[mx]loudnorm=I=-14:TP=-1.2:LRA=9,aresample=48000[out]")
    out = A / "audio" / "mix.m4a"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(g), "-map", "[out]", "-c:a", "aac", "-b:a", "256k", str(out)], check=True)
    print("mix: %s (%.2f s; music from %.2f s of the track, spliced to %.2f s at film %.2f s; %d effects; %d voice lines)"
          % (out.relative_to(ROOT), duration(out), a0, b0, seg1, len(SFX), len(vo)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", nargs="*", default=["all"])
    ap.add_argument("--voice", default="imogen")
    a = ap.parse_args()
    for w in (["voice", "edit", "mix"] if "all" in a.what else a.what):
        {"voice": lambda: voice(a.voice), "edit": edit, "mix": mix}[w]()
