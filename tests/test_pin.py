"""Pairing a phone with the dashboard's PIN (agent/pin.py), against the fake camera. No real camera."""
import json
import urllib.error
import urllib.request

import pytest

from agent.dashboard import Dashboard
from agent.pin import FIRST_WAIT_S, MAX_TRIES, PinGuard, hash_pin, pin_matches
from tests.test_runner import TOO_DARK, fake, runner_for  # noqa: F401  (fake is a fixture)

PIN = "482915"
FAST = dict(iterations=1000)                   # the real hash is slow on purpose; tests don't need that


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_the_hash_checks_the_pin_and_never_holds_it():
    stored = hash_pin(PIN, **FAST)
    assert PIN not in stored and stored.startswith("pbkdf2_sha256$")
    assert pin_matches(PIN, stored) and not pin_matches("482916", stored)
    assert not pin_matches(PIN, "") and not pin_matches(PIN, "garbage") and not pin_matches(None, stored)
    assert hash_pin(PIN, **FAST) != stored                        # a new salt every time
    for bad in ("12345", "1234567", "12345a", ""):
        with pytest.raises(ValueError):
            hash_pin(bad)


def test_wrong_pins_are_slowed_down_and_the_wait_grows():
    clock = Clock()
    g = PinGuard(hash_pin(PIN, **FAST), clock=clock)
    for _ in range(MAX_TRIES - 1):
        assert g.check("000000") == (False, "wrong PIN")
    ok, error = g.check("000000")
    assert not ok and "try again in 60 s" in error
    assert not g.check(PIN)[0]                                    # even the right PIN waits
    clock.t += FIRST_WAIT_S
    for _ in range(MAX_TRIES):                                    # still guessing: the next wait is twice as long
        g.check("000000")
    clock.t += FIRST_WAIT_S
    assert not g.check(PIN)[0]
    clock.t += FIRST_WAIT_S
    assert g.check(PIN) == (True, None)                           # the right PIN, and the slow-down starts over
    assert g.wait_s == FIRST_WAIT_S


def test_paired_phones_are_remembered_across_restarts(tmp_path):
    f = tmp_path / "state" / "paired.json"
    g = PinGuard(hash_pin(PIN, **FAST), f)
    token, error = g.pair(PIN)
    assert token and error is None and g.is_paired(token) and not g.is_paired("someone-else") and not g.is_paired("")
    assert token not in f.read_text()                             # only a hash of the token is stored
    assert (f.stat().st_mode & 0o777) == 0o600
    assert PinGuard(hash_pin(PIN, **FAST), f).is_paired(token)    # after a restart
    f.write_text("not json")
    assert not PinGuard(hash_pin(PIN, **FAST), f).is_paired(token)   # unreadable: pair again, nothing worse


def test_no_pin_means_everyone_is_paired():
    g = PinGuard("")
    assert not g.enabled and g.is_paired(None)


def call(dash, path, body=None, cookie=None):
    req = urllib.request.Request(dash.url.rstrip("/") + path, method="POST" if body is not None else "GET",
                                 data=None if body is None else json.dumps(body).encode())
    req.add_header("X-Camera-Agent", "1")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


def test_the_dashboard_asks_for_the_pin_and_the_kill_switch_always_works(fake, tmp_path):
    cam, path = fake(scene_offset=TOO_DARK)
    r = runner_for(cam, path, tmp_path, live=True, auto=False)
    dash = Dashboard(r, port=0, guard=PinGuard(hash_pin(PIN, **FAST), tmp_path / "paired.json"),
                     names=("camera-pi.local",)).start()
    try:
        code, page, _ = call(dash, "/")
        assert code == 200 and b"Pair this phone" in page
        assert call(dash, "/api/state")[0] == 401
        assert call(dash, "/api/frame.jpg?mode=clean&after=-1")[0] == 401
        assert call(dash, "/api/auto", {"on": True})[0] == 401
        assert call(dash, "/style.css")[0] == 200                 # the PIN screen needs its style
        assert "camera-pi.local:%d" % dash.port in dash.allowed_hosts

        code, body, _ = call(dash, "/api/pair", {"pin": "111111"})
        assert code == 403 and json.loads(body)["error"] == "wrong PIN"
        code, body, headers = call(dash, "/api/pair", {"pin": PIN})
        set_cookie = headers["Set-Cookie"]
        assert code == 200 and "HttpOnly" in set_cookie and "SameSite=Strict" in set_cookie
        cookie = set_cookie.split(";")[0]
        assert call(dash, "/api/state", cookie=cookie)[0] == 200
        code, page, _ = call(dash, "/", cookie=cookie)
        assert b"Pair this phone" not in page
        assert call(dash, "/api/state", cookie="ca_pair=forged")[0] == 401

        assert call(dash, "/api/kill", {})[0] == 200              # not paired, and still stops everything
        assert r.killed and cam.locked
    finally:
        dash.stop()


def test_without_a_pin_the_dashboard_is_unchanged(fake, tmp_path):
    cam, path = fake(scene_offset=TOO_DARK)
    r = runner_for(cam, path, tmp_path)
    dash = Dashboard(r, port=0, guard=PinGuard("")).start()
    try:
        assert call(dash, "/api/state")[0] == 200
        assert call(dash, "/api/pair", {"pin": PIN})[0] == 404
        assert b"Pair this phone" not in call(dash, "/")[1]
    finally:
        dash.stop()
