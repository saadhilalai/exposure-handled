# Step 4: The eyes (read-only)

## What the eyes measure (`agent/eyes.py`)

Every live-view frame, in about 10 ms (keeps up with all 24 fps):

| Measurement | How |
|---|---|
| Log or normal? | From the camera's own settings first (Log shooting mode / Picture Profile gamma). Only if those are missing: a guess from how flat the picture is. Today: "Log shooting (Flexible ISO) records S-Log3". |
| Brightness histogram | 64 bins over the full 1024×576 frame |
| % clipped / near clip | At the measured clip level (221 in S-Log3 preview) / within half a stop of it |
| % crushed | More than 6 stops under 18% grey in log (no usable detail); at black in normal mode |
| Exposure ("key") | Picture split into an 8×6 grid (48 regions); each region converted to **stops vs 18% grey**; key = middle value of the regions, with **light sources** (regions 3+ stops brighter than the rest, or clipped) left out |
| Did exposure change? | Each region compared with the last frame. The **biggest group of regions that moved together** = the real exposure change. Regions that moved differently are flagged "changed" (a hand, a person, a screen). |
| Faces | YuNet face detector (OpenCV model zoo, MIT license, 232 KB), every 3rd frame; brightness of the middle of each face, in stops |
| Color | "Grey world" average of usable pixels, decoded to linear light → color temperature of the picture, leftover warm/cool and green/magenta cast. Gives the light's Kelvin only when the camera WB is a Kelvin value (on AWB only the leftover cast is known). Marked low confidence until calibrated. |
| Motion | % of pixels that changed more than the overall brightness change explains, plus which regions |

### Why screens, hands and people can't fool it

Tested on the real Step 3 frames, including the moment a chat window opened on the MacBook in shot and a hand came in:

| Real situation | Eyes measure | Truth |
|---|---|---|
| ISO 800 → 1000 | +0.31 stops (36/48 regions agree) | +0.33 |
| ISO 800 → 800 with chat window + hand | **0.00 stops**, 16 regions flagged "changed" | 0 |
| Nothing changed | 0.00 stops | 0 |

The first version used the plain middle value of all region changes and was fooled (−0.16 stops): the hand and screen touched more than half the regions, and in deep shadow one brightness level is a big jump in stops. The "biggest agreeing group" rule fixed it. Both cases are permanent tests in `tests/test_eyes.py` (7 tests, all passing).

## S-Log3: judging exposure in log

- The live view is always the flat log image (Step 2), so the agent converts each brightness level to **stops vs 18% grey using Sony's S-Log3 curve**, never "it looks dark, add ISO".
- The conversion has two calibration numbers (`config/liveview_calibration.json`): **A** = where 18% grey lands (guess 103.6/255) and **B** = levels per stop (guess 22.9). The grey card / white paper test measures them (`tools/calibrate_grey.py`).
- Early evidence the guess is close: a capped lens reads 9/255, exactly what the guess predicts for S-Log3 black, and the real ISO third-stop measured as +0.31 stops.
- **Open:** the camera's own meter read −3.3 (if its units are 1000 per stop) while the eyes said −6.5 stops for the same dark room. The calibration measures the meter's units and should explain the gap.

## Calibration result (2026-10-17, matte white wall, read-only)

The director changed ISO/aperture by hand; the bridge ran `--read-only` (0 change requests). Settings: S-Log3 Flexible ISO, 1/50, AWB.

| Capture | Wall (8-bit) | Camera meter |
|---|---|---|
| ISO 800, f/4 (first; light/AWB shifted, **left out**) | 85.3 | 0 |
| ISO 800, f/4 (repeat) | 83.1 | 0 |
| ISO 1600, f/5.6 (aperture step) | 82.1 | 0 |
| ISO 1600, f/4 | 102.1 | 700 |
| ISO 3200 | 123.1 | 1700 |
| ISO 6400 | 144.1 | 2700 |
| ISO 12800 | 164.1 | 3700 |
| ISO 51200 | 206.1 | 4300 (meter's ceiling) |
| ISO 102400 | 221.0 flat (clipped) | 4300 |
| Lens cap, ISO 800 | 10.0 | −7000 |

| Number | Guess | Result | Confidence |
|---|---|---|---|
| Levels per stop (B) | 22.9 | **20.63** | **Measured**: 7 points over 6 stops, all within ±1.1 levels of a straight line |
| Clip level | 221 | **221** | **Measured** (flat clipped frame) |
| Black | ~9 | **10.0** | **Measured** (lens cap) |
| 18% grey (A) | 103.6 | **95.2** | **Derived** from black + B + Sony's S-Log3 curve; assumes the line holds down to black (checked only from level ~82 up) |
| Camera meter | ? | **1000 per stop**, reads 0 within ~⅓ stop, tops out at 4300 | **Measured** |

What it means:
- The old guess read mid-tones about 0.4 stop too dark.
- Highlights clip about **6.2 stops above 18% grey**.
- **Independent check:** the real Step 3 ISO third-stop now measures **+0.331 stops (truth +0.333)**, up from +0.31 with the guess.
- The camera's own meter aims about ⅓ stop below Sony's S-Log3 grey.

**Not resolved:** in the very dark Step 4 room, the camera meter (≈ −3.6 on our scale) and the frame's average light by our scale (−5.3) differ by about 1.7 stops. Likely reasons: that room sits at levels 10-20, deep in the shadows, where our scale is extrapolated rather than measured; and the camera's own metering pattern. Optional check: the same wall at f/8 and f/11 to measure the lower range.

## Overlay (`agent/overlay.py`, `tools/eyes_snapshot.py`)

Zebras (red/white = clipped, yellow = within ½ stop of clip), false color in stops vs grey, face boxes with stops, a region view (light sources / changed), and a numbers panel. Screenshots are saved per session (not committed: they show the room and screen).

False-color scale: purple < −6 st (crushed) · dark blue −6 to −3 · green −¼ to +¼ (18% grey) · pink +½ to +1½ (light skin) · cyan +2 to +2.6 (90% white) · yellow within ½ stop of clip · red clipped · grey everything else.

## Read-only

The bridge has a `--read-only` switch (every change refused all session); the Step 4 tools refuse to run unless the bridge reports it. The camera was not changed in Step 4. One honest note: while checking the switch, one ISO change request was sent on purpose to confirm it gets refused. It was refused before reaching the camera (log: `set_refused`, 0 changes; ISO read back at 800). Locks will be tested only with automated tests or with the camera disconnected from now on.
