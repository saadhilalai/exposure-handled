# Progress

Director: Saad Hilal. Code: an AI coding assistant. Work happens one numbered step at a time; each step ends with a check-in and a commit.

## Resumed 2026-10-17, 21:48: director's answers

1. **Out-of-range ISO/aperture:** warn and pause (the brain's default; now confirmed).
2. **Look numbers:** keep for now; tune after the live test.
3. **Pi RAM:** decide later (both 4GB and 8GB stay in the plan; nothing bought).
4. **Allow-list for the live brain test:** **ISO only (800–12800).** The brain plans every lever, but only ISO changes are made; shutter/aperture/WB proposals are shown as "would change". Expand after the director has seen it behave.

## ⏸ PARKED: 2026-10-17, 19:40 (director stepped away)

**Stopped at a clean point:** Steps 5 (no-camera part) and 8 are finished and committed. The last report to the director (Step 5 + Step 8 summary and four questions) was delivered and is awaiting replies. Nothing was half-done.

**State when parked:**
- Camera: **not connected**. No bridge running (`run/` empty), no camera tools running.
- Training: this project has none. The robot-walker training belongs to another project and was **not touched** (ground rule).
- Repo: everything committed; 37 tests pass (`.venv/bin/python -m pytest -q`).

**On "resume", in this order:**
1. Read this file. Ask the director for the four open answers (unless already given):
   - (a) out-of-range policy: warn-and-pause (current default) / bring in / ask on dashboard;
   - (b) are the look numbers OK (face +1 st, cinematic reacts after 1.5 s, etc.);
   - (c) Pi 4GB or 8GB (nothing to be bought without a go);
   - (d) OK to add shutter 1/48–1/100, aperture f/2.8–f/11, WB 2800–7500K to the bridge allow-list for live Step 5 tests.
2. **If the camera is available** (director says "camera ready"), in this order, each read-only unless stated:
   1. Grey card / paper calibration: `tools/calibrate_grey.py`. Bridge must run with `--read-only`; the director changes ISO by hand. Steps in docs/step4-eyes.md.
   2. Overlay screenshots: `tools/eyes_snapshot.py --live` (read-only bridge), on a lit scene with a face and a bright highlight.
   3. Live closed-loop brain test. Needs (d) approved and the allow-list updated; not started.
3. **If no camera:** don't start Step 6 or 7 without the director's go. Both are possible with recorded frames: the Step 6 dashboard (phone-friendly, per the Pi plan) and the Step 7 written test plan.

**How to start things again:**
- Build: `cmake --build build/bridge -j2`
- Read-only bridge: `cd build/bridge && ./camera_bridge ~/camera-agent/run/bridge.sock ~/camera-agent/sessions/<new folder> --read-only`
- Python: `~/camera-agent/.venv/bin/python`

## Steps

- [x] **Step 1: Read Sony's kit** (no camera). Findings: [docs/step1-sdk-findings.md](docs/step1-sdk-findings.md). Reviewed and approved by director.
- [x] **Step 2: First connection, read-only.** Results: [docs/step2-first-connection.md](docs/step2-first-connection.md). Connected, read 452 settings, saved frames, changed nothing (verified twice per run). Sigma recognized. Live view shows log whether Display LUT is On or Off. *Waiting for director review.*
- [x] **Step 3: The bridge (C++ ↔ Python).** Results: [docs/step3-bridge.md](docs/step3-bridge.md). Base ISOs from the camera: 800 / 4000. Live view 24 fps (matches 23.98p), 0 frames missed. ISO 800 → 1000 → 800 confirmed and restored exactly. The camera confirms a change in 119-172 ms, and it shows in the picture after 272-325 ms. *Waiting for director review.*
- [x] **Step 4: The eyes (read-only).** *Waiting for director review.* Notes: [docs/step4-eyes.md](docs/step4-eyes.md). Eyes + overlay built, 7 tests pass, live at 24 fps / about 10 ms per frame.
  - ✅ **Calibration done (2026-10-17, white wall):**
    - Measured: 20.63 levels/stop, clip 221, black 10.0, camera meter 1000/stop.
    - Derived: 18% grey = 95.2.
    - Validated: the real ISO third-stop measures +0.331 (truth +0.333).
    - Optional later: wall at f/8 and f/11 to check the deep-shadow range.
  - ✅ **Overlay screenshots done (22:14):** face found (94%), lamp flagged as a practical and zebra-striped, 24 fps. Saved in sessions/ (not committed: they show the director's face).
  - ✅ **Decided (22:20):** default face target lowered to **+0.5 st** for every look; the per-person "this face looks right" button goes in Step 6. README notes the agent is designed to expose correctly across skin tones.
- [~] **Step 5: The brain + the runner.** Notes: [docs/step5-brain.md](docs/step5-brain.md). Rules + 5 looks tested with no camera: simulator (14 scenes, 0 back-and-forth) and recorded frames.
  - ✅ Decided: ISO/aperture starting outside the approved range → warn and pause.
  - ✅ **Brain, ISO-only mode:** only approved settings change; shutter/aperture/WB show as "Would change, not approved yet: …".
  - ✅ **Runner built (no camera):** `tools/run_agent.py` (eyes → brain → safety gate → bridge). Dry run by default; `--live` needs typing LIVE on the real camera. Kill switch: SPACE / Ctrl-C / `tools/kill_switch.py` / USB. Runaway guard (20 changes/min). Session snapshot + offer to restore ISO.
  - ✅ **Tried on a fake camera** (`tools/fake_bridge.py`, same protocol as the bridge) with your real Step 4 frame. It caught a 6400 ↔ 5000 pumping bug, fixed with a "clipping memory" rule + regression test. Keys checked in a real terminal.
  - ✅ 49 tests pass (7 eyes, 33 brain, 9 runner).
  - ⏸ **Waiting on Saad:** decide when to run the **live ISO test** (tonight or tomorrow). Needs the camera, the bridge started *without* `--read-only`, and you at the keyboard (SPACE).
- [ ] Step 6: The dashboard
  - To include: the per-person **"this face looks right"** button (set each person once; the agent holds that face's exposure).
- [ ] Step 7: Prove it works (test plan written before shooting)
- [x] **Step 8: Raspberry Pi 5 plan (plan only, nothing bought).** [docs/step8-pi-plan.md](docs/step8-pi-plan.md). Pi 5 4GB build ≈ $244. Pi 5 likely fast enough (~33 ms/frame est. vs 41.7 ms budget); Jetson not needed. Risks: SDK unproven on Pi 5 (use Bookworm + 4K-page kernel), 5V/5A power from D-tap. *Waiting for director review.*
- [ ] Step 9: Package it (README, INTERVIEW.md, resume bullets)

## Step 1 summary

- SDK is C++ (Apple Silicon native). Bridge: small C++ helper program + Python brain over a local socket (decided).
- FX2 over USB: ISO, base ISO (High/Low), EI, shutter speed and angle, iris, WB preset and Kelvin, focus mode/point/nudge, record state: all readable, most changeable.
- Not on the FX2 via SDK: zebra (we draw our own), internal ND (it has none), WB tint, gain in dB.
- Live view: JPEG, 640 or 1024 px wide, up to 30 fps per Sony (to measure). Whether live view shows flat log or the Display LUT image is untested.
- License: our own code can be public and the app can be sold. Sony's files can't be published. Distributing to others requires a warranty/consent notice.
- Risks: macOS 27 isn't on Sony's tested list (14/15/26). CMake isn't installed and full Xcode isn't either. Pi 5 isn't on Sony's tested list.

## Decisions (2026-10-17)

1. Bridge: **A**, a C++ helper program with its own hard-coded safety blocks, plus a Python brain.
2. Step 2 first connection: **our own minimal read-only program**, not Sony's interactive sample app.
3. CMake: install with `brew install cmake` at the start of Step 2.
4. Warranty clause: director has read it and chose to continue.


## Approved safe ranges (director, 2026-10-17)

These go into the C++ allow-list. Anything not listed is blocked.

| Setting | Allowed range | Step 3 | Camera's options inside the range (from Step 2 snapshot) |
|---|---|---|---|
| ISO | 800 to 12800 | **Only setting Step 3 may change** (one step, confirm, put back) | 800, 1000, 1250, 1600, 2000, 2500, 3200, 4000, 5000, 6400, 8000, 10000, 12800 |
| Shutter | Video only, 1/48 to 1/100 | Never touch | 1/48, 1/50, 1/60, 1/80, 1/96, 1/100 |
| Aperture | f/2.8 to f/11 | Never touch | f/2.8 … f/11 (13 stops in 1/3 steps, Sigma 28-70) |
| White balance | 2800K to 7500K | Never touch | camera range 2500K-9900K in 100K steps |
| Focus | No changes yet | Never touch | |
| Everything else | Blocked | Blocked | |

Before any ISO change in Step 3:

- ✅ **FX2 base ISOs for S-Log3 confirmed from the camera itself: 800 (Low) and 4000 (High).** Source: the camera's own menu text via the read-only "Camera Gain BaseISO" display-string request (2026-10-17).
- Note: at the end of Step 2 the camera's own shutter was 1/250, outside the approved range. The range limits what the agent may *set*; it won't "correct" a value you set. How the agent should react to an out-of-range starting value is a question for Step 5.

## Ground rules (from the director, apply to every step)

- Everything lives in `~/camera-agent`. Never touch `~/rocket-lander`, `~/rocket-lander-hard-mode`, `~/robot-walker`. Keep CPU use light (the robot is training); ask before anything heavy.
- Stop and check in after every numbered step. Never guess: ask with 2-3 options and a recommendation.
- Report what doesn't work as clearly as what does; say "likely" for untested explanations.
- Commit at the end of every step and update this file. Sony SDK files never go in the repo.

## Camera safety rules

- Never format cards, delete files, update firmware, or change recording format, codec, frame rate, resolution, picture profile or media settings unless the director asks for that exact change.
- Never start or stop recording unless asked.
- First connection is read-only (settings + one live view frame).
- Every setting change goes through ONE safety function with director-approved ranges, and is logged (time, old value, new value, reason).
- Always a kill switch that stops all changes and hands control back.
- Snapshot the camera's settings at the start of each session; offer to restore them at the end.
- The C++ bridge uses an **allow-list**: only director-approved settings can be set; everything else is refused. Never allowed: card format, settings reset, pixel mapping, LUT import, settings-file upload, APS-C/FF switch, clock/FTP settings, deleting Base Looks. Record start/stop only if explicitly enabled.
- Read-only tools "poison" Sony's change functions so they can't even compile a change.
