"""The blind-test rating page (tools/rater_server.py): anonymous, blind, and counted as the plan says."""
import json
import random
import urllib.error
import urllib.request

import pytest

from tools.rater_server import METHODS, Study, count, make_links, prepare, serve


@pytest.fixture
def study(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    sets = []
    for sid in ["S1_A", "S1_B", "S4_A", "S4_B", "S2_A", "S3_B", "S5"]:
        clips = {}
        for m in METHODS:
            f = src / ("%s_%s.mp4" % (sid, m))
            f.write_bytes(("%s %s " % (sid, m)).encode() * 50)
            clips[m] = str(f)
        sets.append({"id": sid, "clips": clips})
    (tmp_path / "clips.json").write_text(json.dumps({"sets": sets}))
    data = tmp_path / "study"
    data.mkdir()
    prepare(tmp_path / "clips.json", data)
    make_links(4, "http://x", data)
    return Study(data)


def test_each_rater_gets_their_own_stable_order_and_labels(study):
    a, b = sorted(study.tokens)[:2]
    assert study.plan(a) == study.plan(a)                                  # same every time they open it
    assert [p["id"] for p in study.plan(a)] != [p["id"] for p in study.plan(b)] or \
        [p["labels"] for p in study.plan(a)] != [p["labels"] for p in study.plan(b)]
    for p in study.plan(a):
        assert sorted(p["labels"].values()) == METHODS


def test_the_page_never_learns_methods_or_scene_names(study):
    token = sorted(study.tokens)[0]
    server = serve(study, port=0)
    import threading
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % server.server_address[1]
    plan = urllib.request.urlopen(base + "/api/%s/plan" % token).read().decode()
    assert not any(word in plan for word in METHODS + ["S1_A", "S5"])
    public = json.loads(plan)["sets"][0]["id"]
    req = urllib.request.Request(base + "/clip/%s/%s/B" % (token, public), headers={"Range": "bytes=0-9"})
    with urllib.request.urlopen(req) as r:
        assert r.status == 206 and len(r.read()) == 10
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(base + "/api/zzzzzzzzzz/plan")
    assert e.value.code == 404
    server.shutdown()
    server.server_close()


def test_answers_are_stored_by_method_and_the_last_one_counts(study):
    token = sorted(study.tokens)[0]
    first = study.plan(token)[0]
    study.answer(token, {"set": first["public"], "best": "A", "ratings": {"A": 5, "B": 2, "C": 3}})
    study.answer(token, {"set": first["public"], "best": "B", "ratings": {"A": 1, "B": 5, "C": 3}})
    with pytest.raises(ValueError):
        study.answer(token, {"set": first["public"], "best": "A", "ratings": {"A": 5}})
    result = count(study.data, boot=200)
    assert result["answers"] == 1 and result["picks"][first["labels"]["B"]] == 1


def fill(study, prefer=None, seed=3):
    rng = random.Random(seed)
    for token in sorted(study.tokens):
        for p in study.plan(token):
            score = {m: rng.randint(2, 4) for m in METHODS}
            if prefer:
                score[prefer] = 5
            best = max(score, key=lambda m: (score[m], rng.random()))
            label_of = {m: label for label, m in p["labels"].items()}
            study.answer(token, {"set": p["public"], "best": label_of[best],
                                 "ratings": {label_of[m]: v for m, v in score.items()}})


def test_counting_says_agent_better_only_when_it_clearly_is(study):
    fill(study, prefer="agent")
    result = count(study.data, boot=500)
    assert result["agent_vs_fx2auto"]["verdict"] == "agent better"
    assert result["agent_vs_manual"]["verdict"] == "agent better"


def test_counting_says_no_clear_difference_when_there_isnt_one(study):
    fill(study, prefer=None)
    result = count(study.data, boot=500)
    assert result["agent_vs_fx2auto"]["verdict"] == "no clear difference"
