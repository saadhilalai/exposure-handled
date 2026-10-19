"""The Step 7 take order is frozen (tag step7-plan-final): these must never change."""
from tools.make_run_sheet import takes
from tools.make_test_order import build_order


def test_order_matches_the_approved_plan():
    order = build_order()
    rounds = {(scene.split()[0], who): [(n, " → ".join(m)) for n, m in r] for scene, who, r in order["rows"]}
    assert rounds[("S1", "Person A")][0] == (1, "Agent → Manual → FX2 auto")
    assert rounds[("S4", "Person B")][2] == (6, "FX2 auto → Agent → Manual")
    assert rounds[("S6", "nobody needed")][0] == (1, "FX2 auto → Agent → Manual")
    assert order["sunset"][0] == ["Manual", "Agent", "FX2 auto"]
    assert [p[2] for p in order["picks"]] == ["R5 (their round 3)", "R2 (their round 1)", "R1 (their round 1)",
                                              "R6 (their round 3)", "round 3", "round 1", "block round 2"]


def test_run_sheet_has_every_take_once():
    t = takes(build_order())
    names = [row[1] for rows in t.values() for row in rows]
    assert len(names) == len(set(names)) == 63 + 6 + 18
    assert sum(1 for rows in t.values() for row in rows if row[5]) == 6          # bonus takes
