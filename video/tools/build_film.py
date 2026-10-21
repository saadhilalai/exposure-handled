"""Everything the narrated film needs besides its 3D shots (video/tools/capture_film.py makes those).

    python video/tools/build_film.py assets      copy the real frames, dashboard screenshots and the stand-in clip in
    python video/tools/build_film.py data        site/data/site.json (the Oct 19 logs) -> data.js: every logged number
                                                 the film shows comes from here, never typed by hand
    python video/tools/build_film.py captions    cues.json -> captions.js (burned-in subtitles) + captions.vtt (players)
    python video/tools/build_film.py mix         the soundtrack: music, ducked under the voice, out for a beat at the
                                                 kill switch; plus the voice lines when they exist
    python video/tools/build_film.py all

The voice lines go in video/film/assets/voice/lines/<id>.wav, one per cue in cues.json (an AI voice, made after the
script is approved). Without them, captions are timed from a reading-speed estimate and the mix is music only.
Music: "Penumbra" by Scott Buckley (CC BY 4.0), from 0:13.5 into the track (assets/music/penumbra-13.5s.wav; rebuild
with: ffmpeg -ss 11.5 -t 74 -i Penumbra.mp3 -af volume=7dB -ar 48000 -c:a pcm_s16le penumbra-13.5s.wav, 2 s of handle).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILM = ROOT / "video" / "film"
A = FILM / "assets"
VOICE = A / "voice" / "lines"
MUSIC = A / "music" / "penumbra-13.5s.wav"
HANDLE = 2.0          # seconds of music before film time 0 in the asset


def cues():
    return json.loads((FILM / "cues.json").read_text())


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def timed():
    """Each line with its end time: from the voice take's length when it exists, else a reading-speed estimate."""
    c = cues()
    out = []
    for line in c["lines"]:
        f = VOICE / (line["id"] + ".wav")
        dur = duration(f) if f.exists() else 0.35 + len(line["text"].split()) / 2.7
        out.append({**line, "end": round(line["t"] + dur, 2), "voiced": f.exists()})
    for a, b in zip(out, out[1:]):              # a subtitle never runs into the next line
        a["end"] = min(a["end"], round(b["t"] - 0.15, 2))
    return out, c


def assets():
    for sub, files in (("real", sorted((ROOT / "site" / "media" / "real").glob("*.jpg"))),
                       ("dash", [ROOT / "site" / "media" / "screens" / n for n in ("auto.jpg", "killed.jpg")]),
                       ("stills", [ROOT / "video" / "composition" / "assets" / "video" / n for n in ("clipA.mp4", "clipA.standin")])):
        (A / sub).mkdir(parents=True, exist_ok=True)
        for f in files:
            if f.exists():
                shutil.copy2(f, A / sub / f.name)
    print("copied the real frames, dashboard screenshots and the stand-in clip into", A.relative_to(ROOT))


def data():
    site = json.loads((ROOT / "site" / "data" / "site.json").read_text())
    out = {"source": site["source"], "safety": site["safety"]}
    for k in ("test1", "test3"):
        t = site["tests"][k]
        out[k] = {"look": t["look"], "window": t["window"], "settle_s": t["settle_s"], "settled_status": t["settled_status"],
                  "hold_s": t["hold_s"], "changes_during_hold": t["changes_during_hold"], "kill": t["kill"],
                  "changes": t["changes"], "trace": [[p[0], p[1]] for p in t["trace"]]}
    (FILM / "data.js").write_text("// Made by video/tools/build_film.py from site/data/site.json (the Oct 19 FX2 logs). Don't edit by hand.\n"
                                  "window.FILMDATA = %s;\n" % json.dumps(out, ensure_ascii=False))
    print("wrote data.js from site/data/site.json (%s)" % site["source"])


def ts(s):
    return "%02d:%02d:%06.3f" % (s // 3600, s // 60 % 60, s % 60)


def captions():
    lines, _ = timed()
    js = "// Made by video/tools/build_film.py from cues.json. Don't edit by hand.\nwindow.CUES = %s;\n" % json.dumps(
        [{"id": l["id"], "t": l["t"], "end": l["end"], "text": l["text"], "sub": not l.get("nosub")} for l in lines], ensure_ascii=False, indent=1)
    (FILM / "captions.js").write_text(js)
    vtt = ["WEBVTT", ""]
    for l in lines:
        vtt += [l["id"], "%s --> %s" % (ts(l["t"]), ts(l["end"] + 0.25)), l["text"], ""]
    (FILM / "captions.vtt").write_text("\n".join(vtt))
    voiced = sum(l["voiced"] for l in lines)
    print("wrote captions.js and captions.vtt (%d lines, %d timed from voice takes, %d estimated)" % (len(lines), voiced, len(lines) - voiced))


def mix():
    lines, c = timed()
    D = c["duration"]
    k0, k1 = c["kill_dropout"]
    # music: fade in, long fade out, and out for a beat at the kill switch (down in 0.1 s, back over 1.4 s)
    vol = ("if(lt(t,{a}),1,if(lt(t,{b}),1-0.94*(t-{a})/0.1,if(lt(t,{c}),0.06,if(lt(t,{d}),0.06+0.94*(t-{c})/({d}-{c}),1))))"
           .format(a=k0 - 0.05, b=k0 + 0.05, c=k1 - 0.5, d=k1 + 1.0))
    music = ("[0:a]atrim=start={h}:duration={D},asetpts=PTS-STARTPTS,volume=eval=frame:volume='{vol}',"
             "afade=t=in:st=0:d=2.2,afade=t=out:st={fo}:d=4[m]").format(h=HANDLE, D=D, vol=vol, fo=D - 4)
    inputs = ["-i", str(MUSIC)]
    voiced = [l for l in lines if l["voiced"]]
    graph = [music]
    if voiced:
        for i, l in enumerate(voiced):
            inputs += ["-i", str(VOICE / (l["id"] + ".wav"))]
            graph.append("[%d:a]aresample=48000,aformat=channel_layouts=stereo,adelay=%d|%d[v%d]" % (i + 1, l["t"] * 1000, l["t"] * 1000, i))
        graph.append("".join("[v%d]" % i for i in range(len(voiced))) + "amix=inputs=%d:normalize=0,apad=whole_dur=%s[vo]" % (len(voiced), D))
        graph.append("[vo]asplit=2[vo1][vo2]")
        # the music ducks about 9 dB under the voice, easing back between lines
        graph.append("[m][vo1]sidechaincompress=threshold=0.02:ratio=8:attack=30:release=600:makeup=1[md]")
        graph.append("[md][vo2]amix=inputs=2:normalize=0,atrim=duration={D}[mix]".format(D=D))
    else:
        graph.append("[m]anull[mix]")
    graph.append("[mix]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[out]")
    out = A / "audio" / "mix.m4a"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(graph), "-map", "[out]",
                    "-c:a", "aac", "-b:a", "256k", str(out)], check=True)
    print("wrote %s (%.1f s; music%s)" % (out.relative_to(ROOT), duration(out),
                                          " + %d voice lines, ducked" % len(voiced) if voiced else " only: no voice lines yet"))


if __name__ == "__main__":
    what = sys.argv[1:] or ["all"]
    for w in (["assets", "data", "captions", "mix"] if "all" in what else what):
        {"assets": assets, "data": data, "captions": captions, "mix": mix}[w]()
