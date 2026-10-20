"""The session watcher spots flicker, slow reactions, refusals and logged problems from the logs alone."""
import json

from tools.watch_session import analyse


def write(folder, log, changes):
    folder.mkdir()
    (folder / "runner_log.jsonl").write_text("".join(json.dumps(e) + "\n" for e in log))
    (folder / "changes.jsonl").write_text("".join(json.dumps(c) + "\n" for c in changes))


def iso(t, old, new):
    reason = "Scene: ISO %d → %d" % (old, new)
    return ({"t": t, "event": "change", "setting": "IsoSensitivity", "text": reason, "reason": reason, "old": str(old), "new": str(new)},
            {"setting": "IsoSensitivity", "reason": reason, "old_raw": old, "new_raw": new})


def test_flicker_slow_refused_and_problems_are_flagged(tmp_path):
    a, b, c = iso(10, 800, 1000), iso(14, 1000, 800), iso(18, 800, 1000)
    log = [{"t": 0, "event": "start", "mode": "LIVE", "label": "rehearsal", "take": "REH_x_agent"},
           {"t": 1, "event": "tick", "fps": 24, "eyes_ms": 12, "key": 0.1, "headroom": 2, "camera": "ISO 800"},
           a[0], b[0], c[0],
           {"t": 30, "event": "mark", "label": "light change"},
           {"t": 33, "event": "refused", "text": "Not changed (camera started recording)"},
           {"t": 35, "event": "problem", "note": "face too dark"},
           {"t": 50, "event": "end"}]
    write(tmp_path / "s", log, [a[1], b[1], c[1]])
    r = analyse(tmp_path / "s")
    kinds = [k for _, k, _ in r["flags"]]
    assert kinds.count("FLICKER") == 1 and "SLOW" in kinds and "REFUSED" in kinds and "PROBLEM" in kinds
    assert r["label"] == "rehearsal" and r["n_changes"] == 3


def test_a_steady_one_way_correction_is_not_flicker(tmp_path):
    steps = [iso(10 + 2 * i, 6400 // (2 ** i), 6400 // (2 ** (i + 1))) for i in range(4)]
    write(tmp_path / "s", [{"t": 0, "event": "start"}] + [s[0] for s in steps] + [{"t": 40, "event": "end"}], [s[1] for s in steps])
    assert [k for _, k, _ in analyse(tmp_path / "s")["flags"]] == []
