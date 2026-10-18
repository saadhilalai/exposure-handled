"""Tests for the eyes. Synthetic tests run anywhere; real-frame tests use Step 3
session frames that exist only on the dev Mac (skipped elsewhere)."""
from pathlib import Path

import cv2
import numpy as np
import pytest

from agent.eyes import GRID_COLS, GRID_ROWS, CameraContext, Eyes
from agent.overlay import CLIPPED, zebras
from agent.tone import ToneModel, load_calibration, slog3_code, slog3_reflectance

ROOT = Path(__file__).resolve().parent.parent
ISO_FRAMES = ROOT / "sessions" / "2026-10-17_184612_step3-iso-test" / "iso_frames"
LOG = CameraContext(tone="slog3", tone_source="test")


def test_slog3_reference_points():
    assert slog3_code(0.18) == pytest.approx(420.0, abs=0.01)
    assert slog3_code(0.90) == pytest.approx(597.9, abs=0.2)
    assert slog3_code(0.0) == pytest.approx(95.0)
    for x in (0.005, 0.05, 0.18, 0.9, 5.0):
        assert slog3_reflectance(slog3_code(x)) == pytest.approx(x, rel=1e-6)


def test_tone_model_guess_points():
    tm = ToneModel("slog3", load_calibration())
    cal = load_calibration()["slog3"]
    assert float(tm.to_stops(round(cal["grey_level"]))) == pytest.approx(0.0, abs=0.05)
    assert np.all(np.diff(tm.stops_lut) >= 0)          # brighter pixel never means fewer stops


def synthetic(level, screen_level=None):
    """Even scene at `level`, with an optional 'screen' covering 2x2 regions."""
    rng = np.random.default_rng(0)
    img = np.clip(rng.normal(level, 1.5, (576, 1024)), 0, 255).astype(np.uint8)
    if screen_level is not None:
        ch, cw = 576 // GRID_ROWS, 1024 // GRID_COLS
        img[1 * ch:3 * ch, 5 * cw:7 * cw] = screen_level
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def grey_level():
    """8-bit level of 18% grey, from the current calibration (not hard-coded)."""
    return ToneModel("slog3", load_calibration()).level_for_stops(0.0)


def test_bright_screen_does_not_move_the_key():
    eyes = Eyes(face_model="none")
    plain = eyes.analyze(synthetic(grey_level()), LOG, compare=False)
    with_screen = eyes.analyze(synthetic(grey_level(), screen_level=230), LOG, compare=False)
    assert plain.key_stops == pytest.approx(0.0, abs=0.05)
    assert with_screen.key_stops == pytest.approx(plain.key_stops, abs=0.05)
    assert {(1, 5), (1, 6), (2, 5), (2, 6)} <= set(with_screen.light_source_regions)


def test_exposure_shift_ignores_a_screen_going_dark():
    """A third of a stop brighter overall while a bright screen in shot goes dark."""
    eyes = Eyes(face_model="none")
    tm = eyes.tone_model("slog3")
    eyes.analyze(synthetic(grey_level(), screen_level=230), LOG)
    third_stop_up = tm.level_for_stops(1 / 3)
    after = eyes.analyze(synthetic(third_stop_up, screen_level=40), LOG)
    assert after.change["exposure_shift_stops"] == pytest.approx(1 / 3, abs=0.06)
    assert {(1, 5), (1, 6), (2, 5), (2, 6)} <= set(map(tuple, after.change["changed_regions"]))


def test_zebras_mark_clipped_pixels_only():
    tm = ToneModel("slog3", load_calibration())
    img = np.full((60, 60, 3), 100, np.uint8)
    img[:30] = tm.clip_level
    out = zebras(img, tm)
    top = out[:30].reshape(-1, 3)
    assert any((px == CLIPPED).all() for px in top[:50])
    assert (out[30:] == 100).all()


needs_frames = pytest.mark.skipif(not ISO_FRAMES.exists(), reason="Step 3 session frames not on this machine")


def load(frame_no):
    return cv2.imread(str(ISO_FRAMES / ("%06d.jpg" % frame_no)))


@needs_frames
def test_real_iso_step_is_seen_as_exposure_shift():
    eyes = Eyes(face_model="none")
    eyes.analyze(load(450), LOG)               # ISO 800
    up = eyes.analyze(load(486), LOG)          # ISO 1000 = +1/3 stop
    assert up.change["exposure_shift_stops"] == pytest.approx(1 / 3, abs=0.1)


@needs_frames
def test_real_chat_window_is_not_an_exposure_change():
    """Step 3: ISO back at 800, but a chat window opened on the laptop screen in shot."""
    eyes = Eyes(face_model="none")
    eyes.analyze(load(450), LOG)               # before the test, ISO 800
    after = eyes.analyze(load(537), LOG)       # after the restore, ISO 800, window open
    assert abs(after.change["exposure_shift_stops"]) < 0.1
    assert after.change["changed_regions"], "the screen area should be flagged as changed"
