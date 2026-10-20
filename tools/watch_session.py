"""Watch a session from another terminal, read-only: what the agent is doing, and anything that looks wrong.
It only reads the session's log files on this Mac: no camera, no bridge, no internet.

Usage:
  python tools/watch_session.py                 # newest session under sessions/REHEARSAL/ (else sessions/), every 15 s
  python tools/watch_session.py --once          # one summary of the last 2 minutes
  python tools/watch_session.py --report        # the whole session: every flag, for the after-shoot list
  python tools/watch_session.py <folder> [...]

Flags it raises:
  FLICKER   exposure went brighter/darker/brighter (or the reverse) within 20 s
  SLOW      after a mark (m), the agent took more than 10 s to finish reacting, or never reacted
  FPS       live view under 15 frames a second
  LAG       the eyes took over 60 ms on a frame (median)
  REFUSED   a change was refused (by the gate or the bridge)
  ERROR     an error event
  STALE     no new frame logged for 10 s (agent stopped, frozen or the Mac slept)
  PROBLEM   you logged one (x key or the dashboard)
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLICKER_WINDOW_S, SLOW_S, MIN_FPS, MAX_EYES_MS, STALE_S = 20.0, 10.0, 15.0, 60.0, 10.0


def newest_session():
    for base in (ROOT / "sessions" / "REHEARSAL", ROOT / "sessions"):
        folders = [p for p in base.glob("*") if p.is_dir() and (p / "runner_log.jsonl").exists()]
        if folders:
            return max(folders, key=lambda p: (p / "runner_log.jsonl").stat().st_mtime)
    sys.exit("No session with a runner log yet.")


def read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass                                    # the agent may be mid-write on the last line
    return rows


def brightness_sign(c):
    """+1 if a change makes the picture brighter, -1 darker, 0 for colour or unknown."""
    try:
        old, new = c["old_raw"], c["new_raw"]
        if c["setting"] == "IsoSensitivity":
            return (new > old) - (new < old)
        if c["setting"] == "FNumber":
            return (new < old) - (new > old)
        if c["setting"] == "ShutterSpeed":
            t_old, t_new = (old >> 16) / (old & 0xFFFF), (new >> 16) / (new & 0xFFFF)
            return (t_new > t_old) - (t_new < t_old)
    except (KeyError, TypeError, ZeroDivisionError):
        pass
    return 0


def analyse(folder, since=None):
    log = read_jsonl(folder / "runner_log.jsonl")
    if not log:
        return None
    t_end = log[-1].get("t", 0.0)
    t0 = -1e9 if since is None else t_end - since
    ticks = [e for e in log if e["event"] == "tick" and e["t"] >= t0]
    changes = [e for e in log if e["event"] == "change" and e["t"] >= t0]
    full_changes = read_jsonl(folder / "changes.jsonl")
    marks = [e for e in log if e["event"] == "mark"]
    flags = []

    # flicker: brightness direction reversing twice inside the window
    signed = []
    for c in (e for e in log if e["event"] == "change"):
        match = next((f for f in full_changes if f.get("reason") == c.get("reason") and f.get("setting") == c.get("setting")), None)
        s = brightness_sign(match) if match else 0
        if s:
            signed.append((c["t"], s, c.get("setting"), c.get("old"), c.get("new")))
    for i in range(2, len(signed)):
        (ta, sa, *_), (tb, sb, *_), (tc, sc, *rest) = signed[i - 2:i + 1]
        if sa != sb and sb != sc and tc - ta <= FLICKER_WINDOW_S and tc >= t0:
            flags.append((tc, "FLICKER", "brighter/darker/brighter within %.0f s (last: %s %s → %s)" % (tc - ta, *rest)))

    # slow reactions after each mark
    all_changes = [e for e in log if e["event"] == "change"]
    for m in marks:
        if m["t"] < t0:
            continue
        after = [c for c in all_changes if m["t"] <= c["t"] <= m["t"] + 30]
        if not after and t_end - m["t"] > SLOW_S:
            flags.append((m["t"], "SLOW", "no change in %.0f s after the mark '%s'" % (min(30, t_end - m["t"]), m.get("label", ""))))
        elif after and after[-1]["t"] - m["t"] > SLOW_S:
            flags.append((m["t"], "SLOW", "took %.1f s to finish reacting after the mark (%d changes)" % (after[-1]["t"] - m["t"], len(after))))

    fps = [e["fps"] for e in ticks if e.get("fps")]
    eyes = [e["eyes_ms"] for e in ticks if e.get("eyes_ms")]
    if fps and statistics.median(fps) < MIN_FPS:
        flags.append((ticks[-1]["t"], "FPS", "live view at %.0f fps (median)" % statistics.median(fps)))
    if eyes and statistics.median(eyes) > MAX_EYES_MS:
        flags.append((ticks[-1]["t"], "LAG", "eyes take %.0f ms a frame (median)" % statistics.median(eyes)))
    for e in log:
        if e["t"] < t0:
            continue
        if e["event"] == "refused":
            flags.append((e["t"], "REFUSED", e.get("text", "")))
        elif e["event"] == "error":
            flags.append((e["t"], "ERROR", e.get("text", "")))
        elif e["event"] == "problem":
            flags.append((e["t"], "PROBLEM", e.get("note") or "(no note)"))
    age = time.time() - (folder / "runner_log.jsonl").stat().st_mtime
    ended = any(e["event"] == "end" for e in log)
    if STALE_S < age < 1800 and not ended:            # only while a session is live (not when reviewing an old one)
        flags.append((t_end, "STALE", "nothing logged for %.0f s (agent stopped, frozen, or the Mac slept)" % age))
    last_tick = ticks[-1] if ticks else next((e for e in reversed(log) if e["event"] == "tick"), None)
    status = next((e.get("text") for e in reversed(log) if e["event"] == "status"), "")
    start = log[0]
    return {"folder": folder, "t": t_end, "ended": ended, "label": start.get("label"), "take": start.get("take"),
            "mode": start.get("mode"), "tick": last_tick, "status": status, "changes": changes,
            "n_changes": len(all_changes), "while_rec": sum(1 for c in full_changes if c.get("while_recording")),
            "fps": statistics.median(fps) if fps else None, "eyes": statistics.median(eyes) if eyes else None,
            "flags": sorted(flags, key=lambda f: f[0]), "marks": len(marks),
            "problems": len(read_jsonl(folder / "problems.jsonl"))}


def show(a, report=False):
    if a is None:
        print("No log yet.")
        return
    tk = a["tick"] or {}
    head = "%s · %s · %s%s · t=%.0f s%s" % (a["folder"].name, a["label"] or "no label", a["mode"] or "?",
                                            " · take " + a["take"] if a["take"] else "", a["t"], " · ENDED" if a["ended"] else "")
    print("\n" + head)
    print("  camera  %s%s" % (tk.get("camera", "?"), " · paused" if tk.get("paused") else ""))
    print("  scene   key %+.1f st%s · headroom %.1f · fps %s · eyes %s ms" % (
        tk.get("key") or 0, (" · face %+.1f" % tk["face"]) if tk.get("face") is not None else "", tk.get("headroom") or 0,
        "%.0f" % a["fps"] if a["fps"] else "?", "%.0f" % a["eyes"] if a["eyes"] else "?"))
    print("  status  %s" % a["status"])
    print("  totals  %d changes (%d while recording) · %d marks · %d problems logged" % (
        a["n_changes"], a["while_rec"], a["marks"], a["problems"]))
    for c in a["changes"][-6:]:
        print("  change  %6.1f s  %s" % (c["t"], c.get("text", "")))
    flags = a["flags"] if report else a["flags"][-12:]
    for t, kind, text in flags:
        print("  %-8s%6.1f s  %s" % (kind, t, text))
    if not flags:
        print("  no flags")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folders", nargs="*")
    ap.add_argument("--once", action="store_true", help="one summary of the last --since seconds, then stop")
    ap.add_argument("--report", action="store_true", help="the whole session, every flag")
    ap.add_argument("--since", type=float, default=120.0)
    ap.add_argument("--every", type=float, default=15.0)
    args = ap.parse_args()
    folders = [Path(f) for f in args.folders] or [newest_session()]
    if args.once or args.report:
        for f in folders:
            show(analyse(f, None if args.report else args.since), report=args.report)
        return
    try:
        while True:
            show(analyse(folders[0] if args.folders else newest_session(), args.since))
            time.sleep(args.every)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
