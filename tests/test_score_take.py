"""Step 7 scoring (tools/score_take.py): on made-up takes with known answers, then on a fake-camera take."""
import json

from tests.test_runner import fake, runner_for  # noqa: F401  (fake is a fixture)
from tools.score_take import flickers, score

COLS = ["t", "key", "face", "target", "headroom", "clipped", "iso", "shift", "state"]


def take(tmp_path, rows, marks=(), look="cinematic"):
    folder = tmp_path / "take"
    folder.mkdir()
    lines = [",".join(COLS)] + [",".join("" if r.get(c) is None else str(r.get(c)) for c in COLS) for r in rows]
    (folder / "metrics.csv").write_text("\n".join(lines) + "\n")
    log = [{"event": "start", "t": 0.0, "look": look, "mode": "live"}] + [{"event": "mark", "t": t} for t in marks]
    (folder / "runner_log.jsonl").write_text("\n".join(json.dumps(e) for e in log) + "\n")
    return folder


def row(t, face=0.5, shift=0.0, clipped=0.0, key=0.0):
    return {"t": t, "key": key, "face": face, "target": 0.5, "headroom": 3.0, "clipped": clipped, "iso": 800,
            "shift": shift, "state": "AUTO"}




def test_settle_flicker_and_clipping_on_a_made_up_take(tmp_path):
    rows = []
    for k in range(0, 160):                      # 40 s at 4 rows a second
        t = k / 4
        face = 0.5 if t < 10 else -0.5 if t < 13 else 0.5      # light drops at 10 s, fixed by 13 s
        rows.append(row(t, face=face, clipped=1.0 if t < 4 else 0.0,
                        shift=-1.0 if t == 10 else 0.25 if 11 <= t < 13 else 0.0))
    r = score(take(tmp_path, rows, marks=[10.0]))
    assert r["settle_s"] == [3.0]
    assert r["flickers"] == 0                    # the drop (ignored) then one move back up: no reversal
    assert r["clipping_mean_pct"] == 0.1 and r["clipping_over_limit_pct_time"] == 10.0
    assert r["face_on_target_pct_time"] == round(100 * (160 - 12) / 160, 1)


def test_flicker_counts_reversals_within_5_s_only():
    up_down = [row(1, shift=0.2), row(2, shift=-0.2)]                     # pumping
    up_later_down = [row(1, shift=0.2), row(9, shift=-0.2)]               # 8 s apart: two separate fixes
    tiny = [row(1, shift=0.05), row(2, shift=-0.05)]                      # below 1/12 stop: noise
    assert flickers(up_down, []) == 1
    assert flickers(up_later_down, []) == 0
    assert flickers(tiny, []) == 0


def test_a_take_that_never_settles_says_so(tmp_path):
    rows = [row(k / 4, face=0.5 if k < 20 else -1.5) for k in range(200)]
    assert score(take(tmp_path, rows, marks=[5.0]))["settle_s"] == [None]


def test_scores_a_fake_camera_take_end_to_end(fake, tmp_path):
    cam, path = fake(scene_offset=-1.0, light=[(10.0, -1.0)])   # key -1.5 st, then the room drops a stop
    r = runner_for(cam, path, tmp_path, live=True)
    r.run(seconds=10)
    r.mark()
    r.run(seconds=20)
    result = score(tmp_path / "session")
    assert result["marks"] == 1 and result["settle_s"][0] is not None and result["settle_s"][0] < 10
    assert result["flickers"] == 0 and result["clipping_mean_pct"] == 0.0


def test_bad_and_fake_folders_are_skipped_not_fatal(tmp_path, capsys):
    import sys
    from tools import score_take
    good = take(tmp_path, [row(t / 4) for t in range(40)])
    empty = tmp_path / "S1_R1_A_manual"
    empty.mkdir()
    fake_take = tmp_path / "2026-10-18_220854_S1_R1_A_agent-fake"
    fake_take.mkdir()
    for name in ("metrics.csv", "runner_log.jsonl"):
        (fake_take / name).write_text((good / name).read_text())
    assert score_take.unscorable(good) is None
    assert "no metrics.csv" in score_take.unscorable(empty)
    assert "fake camera" in score_take.unscorable(fake_take)
    assert score_take.unscorable(fake_take, allow_fake=True) is None
    sys.argv = ["score_take.py", str(empty), str(fake_take), str(good)]
    score_take.main()
    out = capsys.readouterr().out
    assert out.count("SKIPPED") == 2 and "take | cinematic" in out


def test_a_name_that_disagrees_with_the_mode_is_flagged(tmp_path):
    from tools.score_take import mismatch
    folder = take(tmp_path, [row(t / 4) for t in range(8)])
    log = folder / "runner_log.jsonl"
    log.write_text(log.read_text().replace('"mode": "live"', '"mode": "dry run", "take": "S1_R1_A_agent"'))
    assert "agent take" in mismatch(folder)
