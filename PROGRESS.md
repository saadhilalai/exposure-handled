# Progress

Director: Saad Hilal. Code: an AI coding assistant. Work happens one numbered step at a time; each step ends with a check-in and a commit.

## Steps

- [x] **Step 1: Read Sony's kit** (no camera). Findings: [docs/step1-sdk-findings.md](docs/step1-sdk-findings.md). Reviewed and approved by director.
- [x] **Step 2: First connection, read-only.** Results: [docs/step2-first-connection.md](docs/step2-first-connection.md). Connected, read 452 settings, saved frames, changed nothing (verified twice per run). Sigma recognized. Live view shows log whether Display LUT is On or Off. *Waiting for director review.*
- [x] **Step 3: The bridge (C++ ↔ Python).** Results: [docs/step3-bridge.md](docs/step3-bridge.md). Base ISOs from the camera: 800 / 4000. Live view 24 fps (matches 23.98p), 0 frames missed. ISO 800 → 1000 → 800 confirmed and restored exactly. The camera confirms a change in 119-172 ms, and it shows in the picture after 272-325 ms. *Waiting for director review.*
- [~] **Step 4: The eyes (read-only).** Notes: [docs/step4-eyes.md](docs/step4-eyes.md). Eyes + overlay built, 7 tests pass, live at 24 fps / about 10 ms per frame.
  - ⏸ **Waiting on Saad, needs camera:** grey card / white paper calibration (`tools/calibrate_grey.py`; setup steps in docs/step4-eyes.md).
  - ⏸ **Waiting on Saad, needs camera:** overlay screenshots on a well-lit scene with a face and a bright highlight.
- [~] **Step 5: The brain.** Notes: [docs/step5-brain.md](docs/step5-brain.md). Rules + 5 looks built and tested with no camera: simulator (14 scenes, 0 back-and-forth) and recorded frames. 37 tests pass.
  - ❓ **Decision needed:** what to do when ISO/aperture starts outside the approved range (default now: warn and pause).
  - ⏸ **Waiting on Saad, needs camera:** live closed-loop test (also needs your OK to add shutter/aperture/WB to the bridge allow-list).
- [ ] Step 6: The dashboard
- [ ] Step 7: Prove it works (test plan written before shooting)
- [ ] Step 8: Raspberry Pi 5 plan (plan only)
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

Next: Step 3 starts only when the director says **"camera ready"** (camera is out on a shoot as of 2026-10-17 evening).

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
