"""tools/blind_clips.py: the blind-test windows come out where the plan says, from made-up session logs."""
import json

from tools import blind_clips as bc


def session(root, name, events):
    f = root / name
    f.mkdir()
    (f / "runner_log.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return f


def ev(t, event, **kw):
    return {"t": t, "event": event, **kw}


def test_window_starts_3_s_before_the_first_mark_after_rec(tmp_path):
    f = session(tmp_path, "0000-00-00_100000_S1_R5_A_agent",
                [ev(0, "start"), ev(4.0, "rec", recording=True, text="Camera started recording"),
                 ev(19.0, "mark"), ev(39.0, "mark"), ev(54.0, "rec", recording=False), ev(55, "end")])
    t_in, t_out, notes = bc.window(f)
    assert (t_in, t_out) == (12.0, 24.0) and "2 marks" in notes[0]
    assert bc.timecode(12.0) == "00:00:12:00"      # 288 frames: 23.976 footage counts 24-frame timecode


def test_s5_uses_the_middle_12_s_of_the_block(tmp_path):
    f = session(tmp_path, "0000-00-00_180000_S5_R2_agent",
                [ev(0, "start"), ev(2.0, "rec", recording=True, text="Camera started recording"),
                 ev(122.0, "rec", recording=False), ev(123, "end")])
    assert bc.window(f, s5=True)[:2] == (54.0, 66.0)


def test_problems_are_named_not_guessed(tmp_path):
    late = session(tmp_path, "a_S1_R2_B_manual", [ev(0, "start"), ev(10.0, "rec", recording=True, text="x"), ev(11.0, "mark"), ev(20, "end")])
    assert any("before Rec did" in n for n in bc.window(late)[2])
    already = session(tmp_path, "b_S4_R1_A_fx2auto", [ev(0.0, "rec", recording=True, text="Camera already recording at the start"), ev(5, "mark")])
    assert bc.window(already)[0] is None
    nomark = session(tmp_path, "c_S2_R3_A_agent", [ev(0, "start"), ev(1.0, "rec", recording=True, text="x"), ev(40, "end")])
    assert "no mark" in bc.window(nomark)[2][-1]


def test_the_plan_finds_the_latest_session_and_honours_a_replacement_round(tmp_path):
    session(tmp_path, "0000-00-00_100000_S1_R5_A_agent", [ev(0, "start")])
    session(tmp_path, "0000-00-00_101500_S1_R5_A_agent", [ev(0, "start"), ev(1.0, "rec", recording=True, text="x"), ev(10.0, "mark"), ev(30, "end")])
    session(tmp_path, "0000-00-00_100000_S1_R5_A_agent-fake", [ev(0, "start")])
    rows = {(r["set"], r["method"]): r for r in bc.plan(sessions=tmp_path)}
    assert len(rows) == 21
    r = rows[("S1_A", "agent")]
    assert r["session"] == "0000-00-00_101500_S1_R5_A_agent" and r["in"] == 6.0 and "2 sessions" in r["notes"][0]
    assert rows[("S1_A", "manual")]["notes"] == ["no session yet"]
    swapped = {(r["set"], r["method"]): r for r in bc.plan({"S1_A": "R6"}, sessions=tmp_path)}
    assert swapped[("S1_A", "agent")]["take"] == "S1_R6_A_agent"
