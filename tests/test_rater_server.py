"""The blind-test rating page (tools/rater_server.py): anonymous, blind, and counted as the plan says."""
import json
import random
import urllib.error
import urllib.request

import pytest

from tools.rater_server import METHODS, TUNNEL_URL, Study, count, last_answers, make_links, prepare, serve


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
    latest = last_answers(study.data)
    assert len(latest) == 1 and latest[0]["best"] == first["labels"]["B"]
    result = count(study.data, boot=200)
    assert result["answers"] == 0 and result["not_counted"] == {"raters": 1, "answers": 1}   # hasn't finished


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


def test_only_raters_who_finished_every_scene_count(study):
    """Director, 2026-10-19 (before any ratings): a rater who stops partway isn't counted at all."""
    fill(study, prefer=None)
    before = count(study.data, boot=200)
    quitter = make_links(1, "http://x", study.data)[0]
    study = Study(study.data)
    for p in study.plan(quitter)[:6]:                       # 6 of 7 scenes, all for one method
        label_of = {m: label for label, m in p["labels"].items()}
        study.answer(quitter, {"set": p["public"], "best": label_of["manual"],
                               "ratings": {label_of[m]: 5 if m == "manual" else 1 for m in METHODS}})
    after = count(study.data, boot=200)
    assert after["not_counted"] == {"raters": 1, "answers": 6}
    for k in ("raters", "answers", "picks", "mean_rating", "agent_vs_fx2auto", "agent_vs_manual"):
        assert after[k] == before[k], k
    assert "finished every scene" in after["rule"]


def test_ready_for_the_open_internet(study):
    """Online through a tunnel: clips stream in pieces, nothing is cached or indexed, and a link can't flood answers."""
    import threading
    token = sorted(study.tokens)[0]
    big = study.data / "clips" / study.sets[study.plan(token)[0]["id"]]["clips"]["agent"]
    big.write_bytes(bytes(range(256)) * 8192)                # 2 MB: more than one streamed chunk
    server = serve(study, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % server.server_address[1]
    try:
        page = urllib.request.urlopen(base + "/r/" + token)
        assert page.headers["Cache-Control"] == "no-store" and "noindex" in page.headers["X-Robots-Tag"]
        assert "frame-ancestors 'none'" in page.headers["Content-Security-Policy"]
        p = study.plan(token)[0]
        label = {m: label for label, m in p["labels"].items()}["agent"]
        url = base + "/clip/%s/%s/%s" % (token, p["public"], label)
        with urllib.request.urlopen(url) as r:
            assert r.read() == big.read_bytes()
        req = urllib.request.Request(url, headers={"Range": "bytes=1000000-"})
        with urllib.request.urlopen(req) as r:
            assert r.status == 206 and r.read() == big.read_bytes()[1000000:]
            assert r.headers["Content-Range"] == "bytes 1000000-2097151/2097152"
        for bad in ("/clips/", "/static/../tools/rater_server.py", "/clip/%s/%s/D" % (token, p["public"])):
            with pytest.raises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(base + bad)
            assert e.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
    answer = {"set": p["public"], "best": "A", "ratings": {"A": 3, "B": 3, "C": 3}}
    for _ in range(60):
        study.answer(token, answer)
    with pytest.raises(ValueError, match="too many"):
        study.answer(token, answer)


def test_finds_the_tunnel_address_in_cloudflared_output():
    line = "2026-10-19T21:30:01Z INF |  https://quiet-river-1234.trycloudflare.com                                 |"
    assert TUNNEL_URL.search(line).group(0) == "https://quiet-river-1234.trycloudflare.com"
    assert TUNNEL_URL.search("INF Requesting new quick Tunnel on trycloudflare.com...") is None
