"""When one of the director's limits stops a fix, the agent says which one and why (director, 2026-10-19:
"Light is warmer than your 2800K limit."). No camera: the brain on its own, then the runner on the fake camera."""
from dataclasses import replace

from agent.brain import Brain, CamState, Observation

ISOS = [800, 1000, 1250, 1600, 2000, 2500, 3200, 4000, 5000, 6400, 8000, 10000, 12800]
FS = [2.8, 3.2, 3.5, 4.0, 4.5, 5.0, 5.6, 6.3, 7.1, 8.0, 9.0, 10.0, 11.0]
SHUTTERS = [1 / 48, 1 / 50, 1 / 60, 1 / 80, 1 / 96, 1 / 100, 1 / 120, 1 / 125]
EVERYTHING = {"IsoSensitivity", "FNumber", "ShutterSpeed", "Colortemp", "WhiteBalance"}


def cam(**kw):
    base = dict(iso=1600, fnumber=4.0, shutter_s=1 / 48, fps=23.976, wb_mode="ColorTemp", wb_kelvin=3700,
                iso_options=ISOS, f_options=FS, shutter_options=SHUTTERS)
    return CamState(**dict(base, **kw))


def run(brain, c, seconds, t0=0.0, apply=True, **obs):
    """Feed the brain 24 observations a second; apply its changes to the camera like a camera would."""
    obs = dict(dict(key=0.0, headroom=3.0), **obs)
    out = None
    for k in range(int(seconds * 24)):
        out = brain.update(Observation(t=t0 + k / 24, **obs), c)
        if out.proposal and apply:
            p = out.proposal
            c = replace(c, **{"Colortemp": {"wb_kelvin": p.raw}, "IsoSensitivity": {"iso": p.raw},
                              "FNumber": {"fnumber": p.raw / 100},
                              "ShutterSpeed": {"shutter_s": 1 / (p.raw & 0xFFFF)}}[p.setting])
    return out, c


def texts(out):
    return [x["text"] for x in out.limits]


def test_wb_stops_at_2800k_and_says_the_light_is_warmer():
    """Test 3 on the real camera: the lamp measured about 2642K, WB went 3700K -> 2800K and stopped there."""
    brain = Brain("interview", allowed=EVERYTHING)
    out, c = run(brain, cam(), 6, light_k=2642, color_confidence="medium")
    assert c.wb_kelvin == 2800
    assert texts(out) == ["Light is warmer than your 2800K limit."]
    assert out.limits[0]["detail"] == "Measures about 2640K; WB held at 2800K"
    assert out.limits[0]["tiles"] == {"Colortemp": "At your 2800K limit"}


def test_the_change_itself_names_the_limit():
    brain = Brain("interview", allowed=EVERYTHING)
    reasons = []
    c = cam()
    for k in range(6 * 24):
        out = brain.update(Observation(t=k / 24, key=0.0, headroom=3.0, light_k=2642, color_confidence="medium"), c)
        if out.proposal:
            reasons.append(out.proposal.reason)
            c = replace(c, wb_kelvin=out.proposal.raw)
    assert reasons == ["Light measures about 2642K, WB is 3700K: setting 2800K, your limit"]


def test_wb_limit_stays_through_a_moment_of_low_confidence_and_clears_when_the_light_is_in_range():
    brain = Brain("interview", allowed=EVERYTHING)
    out, c = run(brain, cam(wb_kelvin=2800), 4, light_k=2642, color_confidence="medium")
    assert texts(out) == ["Light is warmer than your 2800K limit."]
    out, c = run(brain, c, 1, t0=4, light_k=None, color_confidence="low")         # someone walks in front
    assert texts(out) == ["Light is warmer than your 2800K limit."]
    out, c = run(brain, c, 6, t0=5, light_k=3200, color_confidence="medium")       # a warmer bulb swapped out
    assert out.limits == [] and c.wb_kelvin == 3200


def test_wb_close_to_the_limit_is_not_a_limit():
    """About 2700K is within ~20 mired of 2800K: close enough, so no change and no message."""
    out, c = run(Brain("interview", allowed=EVERYTHING), cam(wb_kelvin=2800), 5, light_k=2700,
                 color_confidence="medium")
    assert out.limits == [] and c.wb_kelvin == 2800


def test_wb_cooler_than_7500k():
    out, c = run(Brain("interview", allowed=EVERYTHING), cam(wb_kelvin=6500), 6, light_k=9500,
                 color_confidence="high")
    assert c.wb_kelvin == 7500 and texts(out) == ["Light is cooler than your 7500K limit."]


def test_no_wb_limit_when_wb_isnt_the_agents_to_change():
    out, _ = run(Brain("interview", allowed={"IsoSensitivity"}), cam(wb_kelvin=2800), 5, light_k=2642,
                 color_confidence="medium")
    assert out.limits == []


def test_shutter_at_its_limit_at_59_94p():
    out, c = run(Brain("run_and_gun", allowed=EVERYTHING), cam(fps=59.94, shutter_s=1 / 60, fnumber=5.6), 3)
    assert abs(c.shutter_s - 1 / 100) < 1e-9
    assert texts(out) == ["180° needs 1/120, faster than your 1/100 limit."]
    assert out.limits[0]["detail"] == "Shutter held at 1/100 (216°)"


def test_iso_only_too_dark_at_12800():
    out, c = run(Brain("low_light", allowed={"IsoSensitivity"}), cam(iso=12800, fnumber=2.8, wb_mode="AWB",
                                                                     wb_kelvin=None), 4, key=-4.0, headroom=6.0)
    assert c.iso == 12800
    assert texts(out) == ["Scene is too dark for your ISO 12800 limit."]
    assert out.limits[0]["tiles"] == {"IsoSensitivity": "At your 12800 limit"}
    assert out.limits[0]["detail"] == "Needs about 2 stops more light"   # the low-light window starts at -2


def test_too_dark_at_iso_12800_and_f28():
    out, _ = run(Brain("low_light", allowed=EVERYTHING), cam(iso=12800, fnumber=2.8, wb_mode="AWB", wb_kelvin=None),
                 4, key=-4.0, headroom=6.0)
    assert texts(out) == ["Scene is too dark for your ISO 12800 and f/2.8 limits."]
    assert set(out.limits[0]["tiles"]) == {"IsoSensitivity", "FNumber"}


def test_too_bright_names_iso_and_the_looks_aperture():
    out, c = run(Brain("cinematic", allowed=EVERYTHING), cam(iso=800, fnumber=2.8, wb_mode="AWB", wb_kelvin=None),
                 4, key=3.0, headroom=2.5)
    assert c.iso == 800 and c.fnumber == 2.8
    assert texts(out) == ["Scene is too bright for your ISO 800 limit."]
    assert out.limits[0]["detail"] == "Needs about 2 stops less light; f/2.8 is as far as the Cinematic 24p look goes"


def test_exposure_limit_clears_once_the_scene_is_fine_again():
    brain = Brain("low_light", allowed={"IsoSensitivity"})
    c = cam(iso=12800, fnumber=2.8, wb_mode="AWB", wb_kelvin=None)
    out, c = run(brain, c, 4, key=-4.0, headroom=6.0)
    assert out.limits
    out, c = run(brain, c, 3, t0=4, key=-1.0, headroom=6.0)       # a light went on
    assert out.limits == []


def test_no_limit_when_recording_locks_the_agent():
    brain = Brain("low_light", allowed={"IsoSensitivity"})
    c = cam(iso=12800, fnumber=2.8, wb_mode="AWB", wb_kelvin=None)
    out, c = run(brain, c, 4, key=-4.0, headroom=6.0)
    out, _ = run(brain, replace(c, recording=True), 1, t0=4, key=-4.0, headroom=6.0)
    assert out.limits == [] and out.status.startswith("Locked: recording")


def test_runner_shows_the_wb_limit_on_the_dashboard_and_logs_it_once(tmp_path):
    """End to end on the fake camera: a 2600K lamp, WB at 3700K, the exposure switch on."""
    import uuid
    from pathlib import Path

    from agent.eyes import Eyes
    from agent.runner import AgentRunner
    from tools.fake_bridge import FakeCamera, serve

    root = Path(__file__).resolve().parent.parent
    fake = FakeCamera(size=(512, 288), realtime=False, allow_exposure=True, light_k=2600, iso=1600, shutter=48,
                      fnumber=4.0)
    for name, raw in (("WhiteBalance", 0x100), ("Colortemp", 3700)):        # Color Temp mode at 3700K
        fake.props[name]["current"] = fake.start[name] = fake.visible[name] = raw
    fake.props["Colortemp"].update(can_set_now=True, enable="True")
    path = root / "run" / ("test-%s.sock" % uuid.uuid4().hex[:8])
    server = serve(fake, path)
    try:
        r = AgentRunner(path, tmp_path / "s", clock=fake.clock, eyes=Eyes(face_model=root / "no-face-model"),
                        live=True, exposure=True, look="interview")
        r.start()
        for _ in range(24 * 15):
            assert r.step()
        snap = r.snapshot()
        r.close()
    finally:
        server.shutdown()
        server.server_close()
        path.unlink(missing_ok=True)
    assert [(c["setting"], c["to"]) for c in r.changes] == [("Colortemp", "2800K")]
    assert r.changes[0]["reason"].endswith("setting 2800K, your limit")
    assert [x["text"] for x in snap["limits"]] == ["Light is warmer than your 2800K limit."]
    assert [e["kind"] for e in snap["events"]].count("limit") == 1
