"""Replay recorded frames through the eyes + brain, with the camera's real saved settings.

Nothing is sent anywhere. A "virtual camera" pretends each proposal was applied
(0.3 s later, like the real camera) by updating the settings and shifting the measured
brightness by the change's stops. That shift is an APPROXIMATION: real frames can't
show detail that was clipped, so how much clipping appears or disappears is estimated.
No camera involved.

Usage: python tools/brain_replay.py [--look cinematic]
"""
import argparse
import re
import json
import sys
from dataclasses import replace
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.brain import Brain, cam_state_from_settings, observation_from_report  # noqa: E402
from agent.eyes import Eyes, context_from_settings  # noqa: E402
from agent.sony_values import load_enums  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SESSIONS = ROOT / "sessions"


def load_settings(path):
    data = json.loads(Path(path).read_text())
    props = data["properties"] if "properties" in data else data
    return {p["name"]: p for p in props} if isinstance(props, list) else props


def adjust(obs, v):
    """Shift an observation by v stops of virtual exposure (approximate)."""
    o = replace(obs, key=obs.key + v, face=None if obs.face is None else obs.face + v)
    if v <= 0:
        o.clipped_important = obs.clipped_important * max(0.0, 1 + v)   # clipped area gone ~1 stop darker
        o.headroom = obs.headroom - v if obs.clipped_important == 0 else max(0.0, -v - 1.0)
    else:
        o.headroom = obs.headroom - v
        if o.headroom < 0:
            o.clipped_important = obs.clipped_important + 5.0 * min(1.0, -o.headroom)   # unknown size: assume 5%/stop
    return o


def replay(title, frames, props, look, hold_s=0.0, iso_at=None):
    """frames: list of (t_seconds, jpg_path). hold_s: repeat the last frame this long."""
    enums = load_enums()
    ctx = context_from_settings(props, enums)
    cam = cam_state_from_settings(props, enums)
    eyes, brain = Eyes(), Brain(look)
    if hold_s:
        t_last = frames[-1][0]
        frames = frames + [(t_last + k / 24, frames[-1][1]) for k in range(1, int(hold_s * 24) + 1)]
    print("\n=== %s  [%s]" % (title, brain.look.name))
    print("    camera: ISO %d  %s  f/%g  WB %s  %s  %s" % (cam.iso, "1/%d" % round(1 / cam.shutter_s), cam.fnumber,
                                                         cam.wb_mode, cam.log_mode, ctx.tone_source))
    last_status, virtual_ev, pending, shown = None, 0.0, [], set()
    base_iso_at = iso_at
    for t, path in frames:
        for item in [x for x in pending if x[0] <= t]:          # virtual camera applies the change
            _, prop = item
            virtual_ev += prop.stops
            if prop.setting == "ShutterSpeed":
                cam = replace(cam, shutter_s=1 / (prop.raw & 0xFFFF))
            elif prop.setting == "FNumber":
                cam = replace(cam, fnumber=prop.raw / 100)
            elif prop.setting == "IsoSensitivity":
                cam = replace(cam, iso=prop.raw)
                base_iso_at = None                              # the virtual ISO now rules
            pending.remove(item)
        state = replace(cam, iso=base_iso_at(t)) if base_iso_at else cam
        report = eyes.analyze(cv2.imread(str(path)), ctx)
        out = brain.update(adjust(observation_from_report(report, t), virtual_ev), state)
        if out.proposal:
            print("    %5.2f s  WOULD CHANGE  %s" % (t, out.proposal.reason))
            pending.append((t + 0.3, out.proposal))
        for a in out.advice:
            if a not in shown:
                print("    %5.2f s  ADVICE        %s" % (t, a))
                shown.add(a)
        quiet = re.sub(r"waiting [0-9.]+ s", "waiting", out.status)     # don't print every countdown tick
        if quiet != last_status and not out.proposal and not out.advice:
            print("    %5.2f s  status        %s" % (t, quiet))
            last_status = quiet
    print("    virtual camera at the end: ISO %d  1/%d  f/%g  (%+.2f stops vs the recording)"
          % (state.iso, round(1 / state.shutter_s), state.fnumber, virtual_ev))
    print("    eyes on the last real frame: key %+.1f st, clipped %.1f%% (important %.1f%%), headroom %.1f st, faces %d"
          % (report.key_stops, report.clipped_pct, report.clipped_important_pct, report.headroom_stops, len(report.faces)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--look", default="cinematic")
    look = ap.parse_args().look

    over = SESSIONS / "2026-10-17_183226_step3-start"
    if over.exists():
        replay("Real frame: after your shoot, ISO 102400 (overexposed)", [(0.0, over / "liveview.jpg")],
               load_settings(over / "settings_start.json"), look, hold_s=4.0)

    iso = SESSIONS / "2026-10-17_184612_step3-iso-test"
    if iso.exists():
        index = json.loads((iso / "iso_frames" / "index.json").read_text())
        res = json.loads((iso / "step3_results.json").read_text())["iso_test"]
        up, back = res["up"]["t_ms"] / 1000 + 0.3, res["back"]["t_ms"] / 1000 + 0.3
        frames = [(f["t_ms"] / 1000, iso / "iso_frames" / f["file"]) for f in index]
        replay("Real frames: Step 3 ISO test (dark room, laptop screen, chat window + hand)", frames,
               load_settings(iso / "settings_before.json"), look, hold_s=2.0,
               iso_at=lambda t: 1000 if up <= t < back else 800)


if __name__ == "__main__":
    main()
