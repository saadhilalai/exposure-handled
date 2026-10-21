"""Step 7 blind test: where to cut each of the 21 clips, worked out from the session logs.

The plan fixes the rule (docs/step7-test-plan.md, "Blind test"): the same 12-second window, starting 3 s before the
mark (S5: the middle 12 s of the block), for the clips drawn in advance. The runner logs when the camera started and
stopped recording and when you pressed m, so each window's place inside the camera's own clip is:
  in = (first mark - Rec start) - 3 s          out = in + 12 s
  S5: the middle 12 s between Rec start and Rec stop
The camera's recording state is read 4 times a second, so a point can be off by up to 0.25 s: check the first
frames by eye when you export.

Usage:
  python tools/blind_clips.py                      the table: take, session, in and out points, anything to check
  python tools/blind_clips.py --use S1_A=R6        a take was unusable for a non-exposure reason: use that round
                                                   instead (write down why before anyone rates)
  python tools/blind_clips.py --clips-json clips.json --export-dir ~/Desktop/step7-blind
                                                   also write the rating page's clips.json, naming where you'll
                                                   export each clip (then: python tools/rater_server.py prepare clips.json)
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SESSIONS = ROOT / "sessions"
METHODS = ("agent", "fx2auto", "manual")
FPS = 24000 / 1001
WINDOW_S, BEFORE_MARK_S = 12.0, 3.0
# The clips drawn in advance (the plan's "Which clips"): set id -> take name without the method.
SETS = {"S1_A": "S1_R5_A", "S1_B": "S1_R2_B", "S4_A": "S4_R1_A", "S4_B": "S4_R6_B",
        "S2_A": "S2_R3_A", "S3_B": "S3_R1_B", "S5": "S5_R2"}


def timecode(s):
    """Seconds into the clip as HH:MM:SS:FF at 23.976 (frames counted, the way an editor shows them)."""
    f = round(s * FPS)
    return "%02d:%02d:%02d:%02d" % (f // (24 * 3600), f // (24 * 60) % 60, f // 24 % 60, f % 24)


def find_session(take, sessions=SESSIONS):
    """The session folders for a take (Step 7 only: no rehearsal, no fake camera), oldest first."""
    found = [p for p in sessions.glob("*_" + take) if p.is_dir() and (p / "runner_log.jsonl").exists()]
    return sorted(found, key=lambda p: p.name)


def window(folder, s5=False):
    """(in_s, out_s, notes) inside the camera clip, from the session's log."""
    log = [json.loads(line) for line in (folder / "runner_log.jsonl").read_text().splitlines() if line.strip()]
    notes = []
    recs = [e for e in log if e.get("event") == "rec"]
    starts = [e["t"] for e in recs if e.get("recording")]
    if not starts:
        return None, None, ["no Rec start in the log (recording never seen, or a session from before Rec was logged)"]
    if recs[0].get("recording") and recs[0]["t"] < 0.5 and "already" in recs[0].get("text", ""):
        return None, None, ["the camera was already recording when the agent started: its clip start isn't in the log"]
    rec0 = starts[0]
    if len(starts) > 1:
        notes.append("recording started %d times: using the first" % len(starts))
    stops = [e["t"] for e in recs if not e.get("recording") and e["t"] > rec0]
    end = log[-1]["t"]
    rec1 = stops[0] if stops else end
    if not stops:
        notes.append("no Rec stop logged: using the session end")
    if s5:
        mid = (rec0 + rec1) / 2
        t_in = mid - WINDOW_S / 2 - rec0
    else:
        marks = [e["t"] for e in log if e.get("event") == "mark" and e["t"] >= rec0]
        if not marks:
            return None, None, notes + ["no mark (m) during the recording"]
        if len(marks) > 1:
            notes.append("%d marks: using the first" % len(marks))
        t_in = marks[0] - BEFORE_MARK_S - rec0
    t_out = t_in + WINDOW_S
    if t_in < 0:
        notes.append("the window starts %.1f s before Rec did" % -t_in)
    if t_out > rec1 - rec0 + 0.01:
        notes.append("the window runs %.1f s past Rec stop" % (t_out - (rec1 - rec0)))
    return t_in, t_out, notes


def plan(use=None, sessions=SESSIONS):
    """One row per clip: set, method, take, session folder, in, out, notes."""
    sets = dict(SETS)
    for k, v in (use or {}).items():
        if k not in sets:
            sys.exit("%s isn't a blind-test set (%s)" % (k, ", ".join(SETS)))
        parts = sets[k].split("_")
        parts[1] = v
        sets[k] = "_".join(parts)
    rows = []
    for set_id, base in sets.items():
        for m in METHODS:
            take = "%s_%s" % (base, m)
            found = find_session(take, sessions)
            if not found:
                rows.append({"set": set_id, "method": m, "take": take, "session": None, "in": None, "out": None,
                             "notes": ["no session yet"]})
                continue
            t_in, t_out, notes = window(found[-1], s5=set_id == "S5")
            if len(found) > 1:
                notes = ["%d sessions for this take: using the latest (%s)" % (len(found), found[-1].name)] + notes
            rows.append({"set": set_id, "method": m, "take": take, "session": found[-1].name, "in": t_in, "out": t_out,
                         "notes": notes})
    return rows


def main():
    ap = argparse.ArgumentParser(description="Where to cut the 21 blind-test clips, from the session logs.")
    ap.add_argument("--use", nargs="*", default=[], metavar="SET=ROUND", help="e.g. S1_A=R6 (a non-exposure problem)")
    ap.add_argument("--clips-json", help="also write the rating page's clips.json here")
    ap.add_argument("--export-dir", help="where you'll export the clips (named <set>_<method>.mp4)")
    args = ap.parse_args()
    use = dict(u.split("=", 1) for u in args.use)
    rows = plan(use)
    print("%-6s %-8s %-18s %-12s %-12s %s" % ("set", "method", "take", "in", "out", "check"))
    for r in rows:
        tc = lambda s: "-" if s is None else timecode(s)
        print("%-6s %-8s %-18s %-12s %-12s %s" % (r["set"], r["method"], r["take"], tc(r["in"]), tc(r["out"]),
                                                    "; ".join(r["notes"])))
    ready = sum(1 for r in rows if r["in"] is not None)
    print("\n%d of %d clips have a window. In and out are positions inside each camera clip (from its first frame), "
          "at 23.976 fps; the Rec state is read 4 times a second, so check the first frames by eye." % (ready, len(rows)))
    if args.clips_json:
        if not args.export_dir:
            sys.exit("--clips-json needs --export-dir (where the exported clips will be)")
        out = Path(args.export_dir).expanduser()
        spec = {"sets": [{"id": s, "clips": {m: str(out / ("%s_%s.mp4" % (s, m))) for m in METHODS}} for s in SETS]}
        Path(args.clips_json).write_text(json.dumps(spec, indent=1))
        print("wrote %s: export each window to %s/<set>_<method>.mp4, then run rater_server.py prepare on it"
              % (args.clips_json, out))


if __name__ == "__main__":
    main()
