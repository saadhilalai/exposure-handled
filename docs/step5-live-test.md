# Step 5, live: the agent on the real camera (2026-10-19)

**The director's go:** "Camera ready, and I'm leaving it to you." The camera was on a tripod, pointed at a white wall lit by one lamp, with the card out, so nothing could record. Tests 1–3 ran unattended, without anyone typing LIVE, and the dashboard showed the live view throughout.

Tool: `tools/live_selftest.py`. It was rehearsed end to end on the fake camera, using a frame of this same wall, before it touched the real one. Results are saved in `sessions/2026-10-19_184821_live-selftest/` (not committed). Total time: 5 min 15 s.

## How the camera was found (read-only first)

| | |
|---|---|
| Exposure | ISO 1600, 1/50, f/5.6 (Sigma 28-70), Movie M |
| White balance | **Auto** (the camera's stored Color Temp value was 5700K) |
| Format | S-Log3, Flexible ISO, 23.98p, MF, not recording |
| Display LUT | **OFF**; Base Look **"S-Log3"** (Preset 1, which applies no conversion). The other choices are s709, 709(800%) and 16 empty User slots. |

Every setting started inside the approved ranges, so each one could be put back through the safety gate.

## Test 1: live ISO test (bridge: ISO only) ✅ PASS

| What | Result |
|---|---|
| 60 s with Auto off, at your settings | "Exposure good: scene +0.6 st"; **no ISO suggestions** |
| Test setup | ISO 1600 → 6400 (2 stops too bright) |
| Auto on | **5 changes in 8.4 s**, ⅓ stop each: 6400 → 5000 → 4000 (base) → 3200 → 2500 → 2000, then "Exposure good: scene +0.9 st" |
| Camera confirms each change | 116–178 ms |
| 60 s with nothing to fix | **0 changes** |
| Dashboard kill switch | runner stopped in **33 ms**; bridge locked |
| Put back | ISO 1600; every other setting unchanged |

## Test 2: self-test of all four settings (bridge and gate: exposure switch on) ✅ PASS, one note

Each setting went one step up and back, then one step down and back. Each change was confirmed by the camera, and the picture's brightness change was measured.

| Setting | Steps | Camera confirms | Picture halfway there | Measured vs expected |
|---|---|---|---|---|
| ISO | 1600 ↔ 2000, 1600 ↔ 1250 | 118–208 ms | 346–403 ms | ±0.27 st (exp. ±0.32), ±0.41 (exp. ±0.36) |
| Aperture | f/5.6 ↔ f/6.3, f/5.6 ↔ f/5 | **250–399 ms** (the iris motor) | 351–457 ms | ±0.38 (exp. ±0.34), +0.27 / −0.22 (exp. ±0.33) |
| Shutter | 1/50 ↔ 1/48, 1/50 ↔ 1/60 | 150–250 ms | 322–354 ms (1/48 is too small to time) | ±0.02 (exp. ±0.06), **±0.43 (exp. ±0.26)** ⚠ |
| WB Kelvin | 2800 → 7500K sweep, then back to 5700K | 108–193 ms | **212–250 ms** | see calibration |
| WB mode | Auto ↔ Color Temp | 119–165 ms | 654–779 ms (Auto WB eases in) | |

**White-balance calibration on the wall** (saved to `config/liveview_calibration.json`, `slog3.white_balance`):
- The live view shows a WB error at **0.92×** its real size, with R² 0.993 over 8 points and residuals within 10 mired.
- **The lamp measures about 2620K.** That's below your approved 2800K floor, which suggests a warm household bulb.
- The agent's light reading across the whole 2800–7500K sweep: 2612–2782K before calibration, 2556–2702K after. Whatever the camera's WB was set to, it read the same light.

## Test 3: a short automatic run with all four settings (interview look) ✅ PASS

I deliberately set the camera wrong first: ISO 3200, f/8, WB Color Temp 3700K. Then Auto went on:

| After Auto on | The agent's change and its reason |
|---|---|
| 1.5 s | "180° shutter for 23.98p: 1/50 → 1/48" |
| 3.5 s | "Interview look wants f/4: f/8 → f/4" |
| 6.1 / 8.3 / 10.5 s | "Scene +2.8 st (window −1.5 to +1.5)": ISO 3200 → 2500 → 2000 → 1600 |
| 12.5 s | "Light measures about 2642K, WB is 3700K: setting 2800K" (the floor of your range) |
| then 30 s | **0 changes**; "Exposure good: scene +1.7 st" |

It used all four settings, made 6 changes and stayed within every range. Afterwards everything went back to how it was found.

## Safety record

- **44 changes in total, 0 refused, 0 unconfirmed.** Every one went through `SafetyGate.change_setting()` and the bridge's allow-list, and was logged with time, old value, new value and reason.
- After each test, the four settings were read back, plus the Kelvin value the camera stores for Color Temp mode, and all matched how they were found. A full comparison of all the camera's settings showed **no other differences**.
- The watchdog never fired. It would have stopped the test and put everything back on any of these:
  - a refused change
  - a setting outside its range
  - a change not made by the test
  - recording starting
  - the live view freezing for 3 s
  - the camera disconnecting
  - more changes than planned
- At the end the bridge disconnected from the camera; nothing is running.
- The dashboard ran on port **8770**, because robot-walker's web server already uses 8765 (left alone).

## What's new in the code

- **The exposure switch** (approved 2026-10-19; off by default). Aperture f/2.8–f/11, shutter 1/48–1/100 and WB can change only when all three layers agree:
  - the bridge was started with `--allow-exposure`
  - the safety gate has `exposure=True`
  - the runner (or `run_agent.py --allow-exposure`) has it on too

  Without it, only ISO changes, as before (and as the Step 7 plan requires).
- **WB mode:** only Auto and Color Temp are allowed. Color Temp is needed to set Kelvin, and Auto is how the camera was found. Presets and Custom WB stay blocked.
- **`camera_bridge --check-rules`** tests the compiled allow-list without a camera. A test checks it against the Python ranges on 35 values (e.g. 1/125, f/13, ISO AUTO, Daylight WB and focus are all refused by both).
- The fake camera has a color model for WB, so WB can be rehearsed without the camera.
- 89 tests pass.

## What didn't work as expected

1. **Shutter 1/50 ↔ 1/60 measured 0.43 stop instead of 0.26**, in both directions and steady from frame to frame. Not explained yet. One possibility is that the lamp flickers with the mains power and 1/50 doesn't line up with it. **To check:** repeat in daylight. It matters little in practice, because the agent only uses shutter to hold 180°.
2. **The agent only trusts its WB reading when WB is within about 100 mired of the light.** Further off, the picture is so tinted that the "is this pixel neutral?" test rejects everything ("confidence low"). Then the agent leaves WB alone; it doesn't guess. So it can fix a WB that's somewhat off, but not a daylight setting under tungsten. Likely fix: judge "neutral" relative to the picture's overall tint. That's why Test 3 started at 3700K, the farthest point it still trusted.
3. **The lamp is warmer than your WB range allows** (≈2620K vs the 2800K floor). The agent correctly stopped at 2800K, but it didn't say why. **Fixed the same evening** (your request): the dashboard now says "Light is warmer than your 2800K limit." See [step6-dashboard.md](step6-dashboard.md#limits-added-2026-10-19).
4. Aperture steps measured 0.22–0.38 stop for nominal ⅓ stops: the lens's marked steps aren't exact. That's fine for control.
5. The calibration assumes the wall is neutral white. Off-white paint would shift the light reading, not the gain.

## Still needs you

- **Lighting changes:** a lamp switched on and off, someone walking past, a window. Only a person can make those.
- **Face tests:** "this face looks right" on the real camera, and different skin tones (Step 7).
- **The LUT for the blind test:** the camera's Display LUT is off and its Base Look is plain S-Log3, so there's no LUT file to name yet (see PROGRESS.md).
