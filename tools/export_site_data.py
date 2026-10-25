"""Export the real numbers the project website shows into site/data/site.json.

Everything here comes from files, not typed by hand:
  - the Oct 19 live test on the real camera (sessions/<live self-test>/selftest_report.json, each
    phase's metrics.csv and the bridge log), and the frame the agent was looking at for each change
  - the looks (agent/looks.py) and the approved ranges (config/safe_ranges.json)
sessions/ stays out of the repo; site/data/site.json and the copied frames are what gets published.

Usage: python tools/export_site_data.py [sessions/2026-10-19_184821_live-selftest]
"""
import csv
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent.looks import LOOKS  # noqa: E402

LIVE = ROOT / "sessions" / "2026-10-19_184821_live-selftest"
OUT = ROOT / "site" / "data" / "site.json"
FRAMES = ROOT / "site" / "media" / "real"
BEFORE, AFTER = 3.0, 22.0       # seconds of the exposure trace kept around Auto switching on
# How long each test then held with nothing to fix (docs/step5-live-test.md); not in the report itself.


def trace(metrics, settle_s):
    rows = list(csv.DictReader(open(metrics)))
    t_auto = next(float(r["t"]) for r in rows if r["state"] == "AUTO")
    out = []
    for r in rows:
        t = float(r["t"]) - t_auto
        if -BEFORE <= t <= max(AFTER, settle_s + 6):
            out.append([round(t, 2), float(r["key"]), int(r["iso"]), r["state"]])
    return out


def start_settings(path):
    """The four exposure settings at the start of a phase, in words (nothing else is exported)."""
    s = json.loads(path.read_text())
    cur = {k: s[k]["current"] for k in ("IsoSensitivity", "FNumber", "ShutterSpeed", "WhiteBalance", "Colortemp")}
    sh = cur["ShutterSpeed"]
    return {"iso": "ISO %d" % cur["IsoSensitivity"], "fnumber": "f/%g" % (cur["FNumber"] / 100),
            "shutter": "%d/%d" % ((sh >> 16) & 0xFFFF, sh & 0xFFFF),
            "wb": "%dK" % cur["Colortemp"] if cur["WhiteBalance"] == 0x100 else "AWB" if cur["WhiteBalance"] == 0 else "?"}


def phase(session, n, report, test, look, window, hold_s):
    p = report["phases"][str(n)]
    frames = sorted((session / ("phase%d" % n) / "frames").glob("change_*.jpg"))
    shown = []
    for k, f in enumerate(frames, 1):
        name = "%s_%02d.jpg" % (test, k)
        shutil.copyfile(f, FRAMES / name)
        shown.append("media/real/" + name)
    return {
        "name": p["name"], "result": p["result"], "look": look, "window": window,
        "start": start_settings(session / ("phase%d" % n) / "settings_start.json"),
        "setup": [{"setting": e["setting"], "to": e["new"], "reason": e["reason"]}       # done by the test, not the agent
                  for e in map(json.loads, open(session / ("phase%d" % n) / "changes.jsonl"))
                  if e.get("event") == "change" and e["reason"].startswith("Test setup")],
        "changes": [{"t": c["t_after_auto"], "setting": c["setting"], "from": c["from"], "to": c["to"],
                     "reason": c["reason"], "ms": round(c["ms_confirmed"])} for c in p["agent_changes"]],
        "frames": shown,                                  # frame k = what the agent saw when it made change k
        "settle_s": p["settle_s"], "settled_status": p["status_when_settled"],
        "changes_during_hold": p["changes_during_hold"], "hold_s": hold_s,
        "kill": p.get("kill"),
        "trace": trace(session / ("phase%d" % n) / "metrics.csv", p["settle_s"]),
    }


def main():
    session = Path(sys.argv[1]) if len(sys.argv) > 1 else LIVE
    report = json.loads((session / "selftest_report.json").read_text())
    FRAMES.mkdir(parents=True, exist_ok=True)
    sets = [json.loads(line) for line in open(session / "bridge_log.jsonl")]
    sets = [e for e in sets if e.get("event") == "set"]
    ranges = json.loads((ROOT / "config" / "safe_ranges.json").read_text())
    data = {
        "source": "Real Sony cinema camera over USB, 2026-10-19, white wall and one lamp, card out (%s)" % session.name,
        "date": report["started"][:10],
        "tests": {
            "test1": phase(session, 1, report, "test1", "Cinematic 24p", [-1.0, 1.0], hold_s=60),
            "test3": phase(session, 3, report, "test3", "Interview", [-1.5, 1.5], hold_s=30),
        },
        "safety": {"changes": len(sets), "confirmed": sum(1 for e in sets if e.get("confirmed")),
                   "refused": sum(1 for e in sets if e.get("ok") is False or e.get("error"))},
        "looks": [{"key": k, "name": v.name, "description": v.description, "aperture": v.aperture,
                   "aperture_range": list(v.aperture_range), "face_target": v.face_target,
                   "key_window": list(v.key_window), "max_clip_pct": v.max_clip_pct, "iso_policy": v.iso_policy,
                   "shutter_180": v.shutter_180, "react_after_s": v.react_after_s}
                  for k, v in LOOKS.items()],
        "ranges": {k: {f: v[f] for f in v if f not in ("note",)} for k, v in ranges["settings"].items()},
    }
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    print("wrote", OUT.relative_to(ROOT), "and", len(list(FRAMES.glob("*.jpg"))), "frames")


if __name__ == "__main__":
    main()
