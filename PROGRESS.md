# Progress

Director: Saad Hilal. Code: an AI coding assistant. Work happens one numbered step at a time; each step ends with a check-in and a commit.

## Steps

- [x] **Step 1: Read Sony's kit** (no camera). Findings: [docs/step1-sdk-findings.md](docs/step1-sdk-findings.md). Reviewed and approved by director.
- [ ] Step 2: First connection, read-only (waits for "camera ready")
- [ ] Step 3: The bridge (C++ ↔ Python), speed and latency measurements
- [ ] Step 4: The eyes (image analysis, log handling, overlays)
- [ ] Step 5: The brain (cinematography rules, look presets)
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

Next: Step 2 starts only when the director says **"camera ready"** (FX2 firmware update to 1.01 in progress).

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
- Hard-blocked in the C++ bridge: card format, settings reset, pixel mapping, LUT import, settings-file upload, APS-C/FF switch, clock/FTP settings, and record start/stop unless explicitly enabled.
