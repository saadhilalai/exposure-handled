"""The brain, tested in the simulator (no camera). Each test is a behavior a good operator would show."""
import pytest

from agent.brain import Brain, Ranges
from agent.scenes import SCENES
from agent.sim import SimCamera, simulate

BY_NAME = {s.name: s for s in SCENES}


def run(name):
    spec = BY_NAME[name]
    cam = SimCamera(**spec.camera)
    result = simulate(spec.scene, cam, Brain(spec.look), spec.seconds,
                      recording=spec.recording, operator_nd_delay=spec.operator_nd_delay)
    return result, cam


@pytest.mark.parametrize("name", [s.name for s in SCENES])
def test_every_proposal_is_inside_the_approved_ranges(name):
    ranges = Ranges.from_file()
    result, _ = run(name)
    for _, p in result.changes:
        if p.setting == "IsoSensitivity":
            assert ranges.iso[0] <= p.raw <= ranges.iso[1]
        elif p.setting == "FNumber":
            assert ranges.fnumber[0] <= p.raw / 100 <= ranges.fnumber[1]
        elif p.setting == "ShutterSpeed":
            assert ranges.shutter_s[0] - 1e-6 <= 1 / (p.raw & 0xFFFF) <= ranges.shutter_s[1] + 1e-6
        elif p.setting == "Colortemp":
            assert ranges.kelvin[0] <= p.raw <= ranges.kelvin[1]
        else:
            pytest.fail("unexpected setting %s" % p.setting)
        assert p.reason, "every change needs a one-line reason"


@pytest.mark.parametrize("name", ["static", "walk_by_window", "person_walks_through"])
def test_leaves_a_good_or_briefly_disturbed_shot_alone(name):
    result, _ = run(name)
    assert result.changes == []


def test_no_back_and_forth_when_the_face_wobbles_at_the_threshold():
    result, _ = run("flicker_bait")
    assert result.reversals() == 0
    assert len(result.changes) <= 1


def test_sunset_moves_one_way_in_small_steps():
    result, cam = run("sunset")
    steps = [p.stops for _, p in result.exposure_changes()]
    assert steps and all(s > 0 for s in steps)
    assert max(steps) <= 1.0 + 1e-6
    assert result.reversals() == 0
    assert result.seconds_clipping(0.5, 1 / 24) == 0


def test_backlit_window_protects_highlights_and_asks_for_light():
    result, _ = run("backlit_window_face")
    assert result.reversals() == 0
    assert any("add light" in a for _, a in result.advice)
    assert result.log[-1][2].clipped_important <= 2.0


def test_shade_to_sun_comes_down_fast_and_asks_for_nd():
    result, _ = run("shade_to_sun")
    after = [t for t, _ in result.exposure_changes() if t >= 8]
    assert after and after[-1] - 8 <= 6.0
    assert any("of ND" in a for _, a in result.advice)


def test_bright_day_asks_for_enough_nd_then_last_resort_aperture():
    result, cam = run("bright_day_no_nd")
    first_nd = next(a for _, a in result.advice if "of ND" in a)
    assert "at least 3 stops" in first_nd
    assert cam.fnumber == 4.0                        # last resort, never past f/4 for this look


def test_with_an_operator_adding_nd_the_aperture_stays_at_f28():
    result, cam = run("bright_day_with_operator")
    assert not any(p.setting == "FNumber" for _, p in result.changes)
    assert cam.fnumber == 2.8 and cam.nd > 0


def test_nothing_changes_while_recording():
    result, _ = run("recording_lock")
    assert not [t for t, _ in result.changes if 20 <= t < 100]


def test_cine_ei_never_touches_iso():
    result, _ = run("cine_ei")
    assert not any(p.setting == "IsoSensitivity" for _, p in result.changes)


def test_shutter_goes_to_180_degrees_first():
    result, cam = run("wrong_shutter_start")
    assert result.changes[0][1].setting == "ShutterSpeed"
    assert abs(cam.shutter_s - 1 / 48) < 1e-9


def test_out_of_range_iso_pauses_by_default_and_can_be_brought_in():
    from agent.brain import Observation
    from agent.sim import SimCamera
    cam = SimCamera(iso=102400).state()
    obs = Observation(t=0.0, key=0.5, headroom=0.0, clipped_important=10.0)
    paused = Brain("cinematic").update(obs, cam)
    assert paused.proposal is None and "outside your approved" in paused.advice[-1]
    brought = Brain("cinematic", out_of_range="bring_in").update(obs, cam)
    assert brought.proposal.setting == "IsoSensitivity" and brought.proposal.raw == 12800


def test_180_shutter_never_pushes_highlights_into_clipping():
    """Starting at 1/160 with highlights near clipping: lower ISO first, then the shutter."""
    from agent.sim import SceneState
    scene = lambda t: SceneState(key=-0.5, face=0.8, highlight=3.9, highlight_area=20)
    cam = SimCamera(iso=4000, shutter_s=1 / 160)
    result = simulate(scene, cam, Brain("cinematic"), 15)
    assert result.changes[0][1].setting == "IsoSensitivity"
    assert any(p.setting == "ShutterSpeed" for _, p in result.changes)
    assert result.seconds_clipping(0.5, 1 / 24) == 0


def test_tungsten_prefers_base_iso_and_fixes_wb():
    result, cam = run("tungsten_interior")
    assert cam.iso == 4000
    assert cam.wb_kelvin == 3200


def test_low_light_says_it_needs_light():
    result, cam = run("low_light")
    assert cam.iso == 12800
    assert any("Too dark" in a for _, a in result.advice)
