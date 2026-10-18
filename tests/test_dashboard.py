"""The dashboard's web controls, against the fake camera. No real camera."""
import json
import urllib.error
import urllib.request

from agent.dashboard import Dashboard
from tests.test_runner import TOO_DARK, fake, runner_for  # noqa: F401  (fake is a fixture)


def call(dash, path, body=None, header=True, host=None):
    req = urllib.request.Request(dash.url.rstrip("/") + path, method="POST" if body is not None else "GET",
                                 data=None if body is None else json.dumps(body).encode())
    if header:
        req.add_header("X-Camera-Agent", "1")
    if host:
        req.add_header("Host", host)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def started(fake, tmp_path, **kw):
    cam, path = fake(scene_offset=TOO_DARK)
    r = runner_for(cam, path, tmp_path, **kw)
    dash = Dashboard(r, port=0).start()
    return cam, r, dash


def test_state_and_frame(fake, tmp_path):
    cam, r, dash = started(fake, tmp_path)
    r.run(seconds=1)
    code, body = call(dash, "/api/state")
    state = json.loads(body)
    assert code == 200 and state["state"] == "SUGGESTING" and state["mode"] == "dry run" and state["fake"]
    assert state["camera"]["iso"] == "ISO 800" and state["history"]
    code, jpeg = call(dash, "/api/frame.jpg?mode=false_color&after=-1")
    assert code == 200 and jpeg[:2] == b"\xff\xd8"
    dash.stop()


def test_buttons_need_the_header_and_the_right_host(fake, tmp_path):
    cam, r, dash = started(fake, tmp_path, live=True, auto=False)
    assert call(dash, "/api/kill", {}, header=False)[0] == 403
    assert call(dash, "/api/kill", {}, host="evil.example:%d" % dash.port)[0] == 403
    assert call(dash, "/../config/safe_ranges.json")[0] == 404
    assert not r.killed and not cam.locked
    dash.stop()


def test_auto_starts_off_and_changes_only_after_the_operator_turns_it_on(fake, tmp_path):
    cam, r, dash = started(fake, tmp_path, live=True, auto=False)
    r.run(seconds=4)
    assert cam.sets == []                                          # Auto off: suggestions only
    assert call(dash, "/api/auto", {"on": True})[0] == 200
    r.run(seconds=6)
    assert cam.sets and {name for _, name, _ in cam.sets} == {"IsoSensitivity"}
    dash.stop()


def test_auto_cannot_be_turned_on_in_a_dry_run(fake, tmp_path):
    cam, r, dash = started(fake, tmp_path)
    code, body = call(dash, "/api/auto", {"on": True})
    assert code == 409 and not json.loads(body)["ok"]
    dash.stop()


def test_lock_holds_and_kill_locks_the_bridge(fake, tmp_path):
    cam, r, dash = started(fake, tmp_path, live=True)
    call(dash, "/api/lock", {"on": True})
    r.run(seconds=5)
    assert cam.sets == [] and r.output.status.startswith("Locked by you")
    assert call(dash, "/api/kill", {})[0] == 200
    assert r.killed and cam.locked and not r.step()
    assert json.loads(call(dash, "/api/state")[1])["state"] == "KILLED"
    dash.stop()
