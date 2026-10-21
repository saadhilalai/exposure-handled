"""Step 7 scoring: the measurements the test plan fixes BEFORE shooting, computed the same way
for every take (agent, FX2 auto, manual).

Input: a runner session folder (metrics.csv, 4 rows a second, and runner_log.jsonl with the
operator's marks). The runner records these in every mode, including a dry run that only
watches the FX2's own auto or your manual control, so all three are measured by the same eyes.

Definitions (frozen in docs/step7-test-plan.md; changing them after the shoot breaks the test):
  clipping   mean % of the frame clipped in important areas, and % of the time over the look's limit
  face       mean |face - target| in stops, and % of the time within 1/3 stop (rows with a face only).
             Clarification 2 (2026-10-21, before shooting): a row whose face wasn't recognized is scored against
             the target of the person named in the take (A in S1_R1_A_agent), not the look's default.
  settle     for each mark: seconds until the face (no face: the scene key) is back on target
             (face within 1/3 stop of its target; key within 1/3 stop of the look's window, the same
             tolerance as the brain's dead band) and STAYS there 2 s. Capped at 30 s.
  flicker    times the picture's overall brightness reverses direction within 5 s (each move at
             least 1/12 stop), ignoring moves that start in the 1.5 s after a mark (the light change)

Usage: python tools/score_take.py <session folder> [<session folder> ...] [--json out.json]
Folders that can't be scored (no data, or a session on the fake camera) are skipped and listed, so one bad
folder never stops the batch. A take whose name and mode disagree (an _agent take that ran as a dry run) is
scored but flagged.
"""
import argparse
import csv
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.looks import LOOKS  # noqa: E402

ON_TARGET = 1 / 3        # stops: the brain's dead band
HOLD_S = 2.0             # must stay on target this long to count as settled
SETTLE_CAP_S = 30.0
MOVE_MIN = 1 / 12        # stops: smaller brightness moves are ignored (noise)
MOVE_GAP_S = 1.0         # a pause longer than this ends a move
REVERSAL_S = 5.0         # a reverse move starting within this long after the last one = flicker
AFTER_MARK_S = 1.5       # the light change itself


def load(folder):
    folder = Path(folder)
    rows = []
    with (folder / "metrics.csv").open() as f:
        for r in csv.DictReader(f):
            rows.append({k: (None if v == "" else v if k in ("state", "who") else float(v)) for k, v in r.items()})
    log = [json.loads(line) for line in (folder / "runner_log.jsonl").read_text().splitlines()]
    start = next((e for e in log if e["event"] == "start"), {})
    marks = [e["t"] for e in log if e["event"] == "mark"]
    note = person_targets(rows, log, start.get("take") or folder.name)
    return rows, marks, start.get("look", "cinematic"), start.get("mode", "?"), note


TAKE_PERSON = re.compile(r"S\d_(?:R\d+|BONUS)_([A-Z])_")


def person_targets(rows, log, take):
    """Clarification 2: rows with a face nobody recognized get the take's person's target. Returns a note."""
    m = TAKE_PERSON.search(take)
    if not m:
        return None                                            # no person in the name (S5, S6): as logged
    if rows and "who" not in rows[0]:
        return "logged before 'who' was recorded: face targets as logged"
    letter = m.group(1)
    target = None
    for e in log:                                              # the target in effect: the last one set for them
        people = e.get("people", []) if e.get("event") == "start" else [e] if e.get("event") == "face" else []
        for p in people:
            if p.get("target") is not None and (p.get("name") or "").strip().upper() in (letter, "PERSON " + letter):
                target = p["target"]
    unknown = [r for r in rows if r["face"] is not None and not r.get("who")]
    if not unknown:
        return None
    if target is None:
        return "person %s's face target isn't in this session's log: %d unrecognized rows scored as logged" % (letter, len(unknown))
    for r in unknown:
        r["target"] = target
    return "%d unrecognized face rows scored against person %s's target (%+.2f st)" % (len(unknown), letter, target)


def on_target(row, look):
    if row["face"] is not None and row["target"] is not None:
        return abs(row["face"] - row["target"]) <= ON_TARGET + 1e-9
    lo, hi = look.key_window
    return lo - ON_TARGET <= row["key"] <= hi + ON_TARGET


def settle_times(rows, marks, look):
    out = []
    for te in marks:
        after = [r for r in rows if te <= r["t"] <= te + SETTLE_CAP_S + HOLD_S]
        found = None
        for i, r in enumerate(after):
            window = [x for x in after[i:] if x["t"] <= r["t"] + HOLD_S]
            if window[-1]["t"] - r["t"] >= HOLD_S - 0.26 and all(on_target(x, look) for x in window):
                found = round(r["t"] - te, 2)
                break
        out.append(found if found is not None and found <= SETTLE_CAP_S else None)
    return out


def moves(rows):
    """Runs of same-direction overall brightness change: [(t_start, t_end, stops)]."""
    out, cur = [], None
    for r in rows:
        s = r["shift"] or 0.0
        if cur and r["t"] - cur[1] > MOVE_GAP_S:
            out.append(cur)
            cur = None
        if s == 0:
            continue
        if cur and (s > 0) == (cur[2] > 0):
            cur = (cur[0], r["t"], cur[2] + s)
        else:
            if cur:
                out.append(cur)
            cur = (r["t"], r["t"], s)
    if cur:
        out.append(cur)
    return [m for m in out if abs(m[2]) >= MOVE_MIN]


def flickers(rows, marks):
    kept = [m for m in moves(rows) if not any(te <= m[0] <= te + AFTER_MARK_S for te in marks)]
    return sum(1 for a, b in zip(kept, kept[1:]) if (a[2] > 0) != (b[2] > 0) and b[0] - a[1] <= REVERSAL_S)


def score(folder):
    rows, marks, look_key, mode, note = load(folder)
    look = LOOKS[look_key]
    faces = [r for r in rows if r["face"] is not None and r["target"] is not None]
    settles = settle_times(rows, marks, look)
    return {
        "take": Path(folder).name, "mode": mode, "look": look_key, "seconds": round(rows[-1]["t"] - rows[0]["t"], 1),
        "clipping_mean_pct": round(statistics.fmean(r["clipped"] for r in rows), 2),
        "clipping_over_limit_pct_time": round(100 * sum(r["clipped"] > look.max_clip_pct for r in rows) / len(rows), 1),
        "face_rows_pct": round(100 * len(faces) / len(rows), 1),
        "face_error_mean_st": round(statistics.fmean(abs(r["face"] - r["target"]) for r in faces), 2) if faces else None,
        "face_on_target_pct_time": round(100 * sum(on_target(r, look) for r in faces) / len(faces), 1) if faces else None,
        "marks": len(marks), "settle_s": settles, "flickers": flickers(rows, marks), "face_target_note": note,
    }


def unscorable(folder, allow_fake=False):
    """Why this folder can't be scored as a take, or None."""
    f = Path(folder)
    if not (f / "metrics.csv").exists() or not (f / "runner_log.jsonl").exists():
        return "no metrics.csv / runner_log.jsonl (not a runner session, or it stopped before it began)"
    with (f / "metrics.csv").open() as fh:
        if sum(1 for _ in fh) < 3:
            return "fewer than 2 measurements (the take stopped almost at once)"
    start = next((json.loads(line) for line in (f / "runner_log.jsonl").read_text().splitlines()
                  if '"start"' in line and json.loads(line).get("event") == "start"), None)
    if start is None:
        return "no start in runner_log.jsonl"
    if not allow_fake and (f.name.endswith("-fake") or (start.get("bridge") or {}).get("fake")):
        return "recorded on the fake camera, not the FX2 (--allow-fake to score it anyway)"
    return None


def mismatch(folder):
    """A take name that disagrees with how it ran, or None."""
    log = [json.loads(line) for line in (Path(folder) / "runner_log.jsonl").read_text().splitlines()]
    start = next((e for e in log if e.get("event") == "start"), {})
    take, mode = start.get("take") or Path(folder).name, start.get("mode")
    if take.endswith("_agent") and mode != "live":
        return "an agent take that ran as a %s" % mode
    if take.endswith(("_fx2auto", "_manual")) and mode == "live":
        return "a camera take that ran live (the agent could change settings)"
    return None


def is_rehearsal(folder):
    """Rehearsal sessions live under sessions/REHEARSAL/ and carry a LABEL file: never Step 7 data."""
    return (Path(folder) / "LABEL").exists() or "REHEARSAL" in Path(folder).resolve().parts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--json")
    ap.add_argument("--allow-fake", action="store_true", help="score sessions recorded on the fake camera too")
    args = ap.parse_args()
    labels = {is_rehearsal(f) for f in args.folders}
    if len(labels) > 1:
        sys.exit("Some of these folders are rehearsal takes and some aren't. Score them separately: rehearsal data "
                 "never mixes with the Step 7 test.")
    if True in labels:
        print("REHEARSAL takes: not part of the Step 7 test.")
    skipped = [(f, unscorable(f, args.allow_fake)) for f in args.folders]
    for f, why in skipped:
        if why:
            print("SKIPPED %s: %s" % (f, why))
    args.folders = [f for f, why in skipped if not why]
    if not args.folders:
        sys.exit("Nothing to score.")
    for f in args.folders:
        why = mismatch(f)
        if why:
            print("CHECK %s: %s" % (f, why))
    results = [score(f) for f in args.folders]
    cols = ["take", "look", "seconds", "clipping_mean_pct", "clipping_over_limit_pct_time", "face_error_mean_st",
            "face_on_target_pct_time", "settle_s", "flickers"]
    print(" | ".join(cols))
    for r in results:
        print(" | ".join(str(r[c]) for c in cols))
    for r in results:
        if r.get("face_target_note"):
            print("NOTE %s: %s" % (r["take"], r["face_target_note"]))
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
