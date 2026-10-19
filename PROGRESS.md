# Progress

Director: Saad Hilal. Code: an AI coding assistant. Work happens one numbered step at a time; each step ends with a check-in and a commit.

## 📍 Where things stand (overnight 2026-10-17 → morning 2026-10-18)

The director went to sleep and asked for everything that doesn't need him or the camera. **The camera was not connected at any point overnight.** Only the fake camera and saved frames were used.

**Done overnight (each committed):**
- Step 6 dashboard: [docs/step6-dashboard.md](docs/step6-dashboard.md)
- Step 7 test plan (**DRAFT**) + scoring tools: [docs/step7-test-plan.md](docs/step7-test-plan.md)
- Step 8 Pi plan finished: [docs/step8-pi-plan.md](docs/step8-pi-plan.md)
- Step 9 started: README + [INTERVIEW.md](INTERVIEW.md)
- 62 tests pass.

**Director's decisions (2026-10-18 morning):**
1. ✅ Lock = hold every setting now.
2. ✅ Keep face memory: local only, never uploaded, Forget deletes it, **only for people who agree** (note added to the dashboard, README, Step 6 doc).
3. ✅ Face screenshots stay off the public repo.
4. ✅ Allow ISO changes while recording **only for Step 7 agent takes**, behind a switch that's **off by default** (to build: brain, Python gate and C++ bridge all refuse while recording today).
5. ✅ Pi: **4GB**.
6. ✅ Step 7's 8 questions answered (2026-10-18): ISO only; FX2 Auto ISO only; advice not followed in scored takes + one bonus take per face scene and person; Sony's official LUT; a private rater page I build; 2+ people with different skin tones (everyone in S1 and S4, others split); dates later.
7. ✅ Step 7 plan **approved as FINAL** (2026-10-18). LUT = the FX2's Display LUT, read from the camera (read-only) at the next connection, named in the plan before any grading. Built: the recording switch, the rater page (anonymous IDs, answers off the repo), the printable run sheet.

**Needs Saad at the camera:**
1. **Live ISO test (Step 5)**, ~10 min:
   - camera ready
   - bridge started *without* `--read-only` (ISO 800–12800 only)
   - you run `tools/run_agent.py --live --dashboard` in your own Terminal
   - a 1-minute dry run first, then Auto on
   - a scene with your face and a lamp; change a light; press SPACE once
2. **Face button on the real camera:** press "this face looks right" once during that test.
3. **Read the Display LUT** (read-only, ~1 min): `tools/read_display_lut.py` with the bridge `--read-only`, before starting the live bridge.
4. Later, the Step 7 shoot (plan approved; run sheet ready).
5. Optional: wall at f/8 and f/11, for the deep-shadow calibration.

**How to start things again:**
- Build: `cmake --build build/bridge -j2`
- Bridge, read-only: `cd build/bridge && ./camera_bridge ~/camera-agent/run/bridge.sock ~/camera-agent/sessions/<new folder> --read-only`
- Bridge, for the live ISO test: same command without `--read-only`.
- Agent: `~/camera-agent/.venv/bin/python tools/run_agent.py [--live] [--dashboard] [--fake]`

<details><summary>Earlier park notes (19:40, resolved)</summary>

Parked 2026-10-17, 19:40 (director stepped away)

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

</details>

## Resumed 2026-10-17, 21:48: director's answers

1. **Out-of-range ISO/aperture:** warn and pause (the brain's default; now confirmed).
2. **Look numbers:** keep for now; tune after the live test.
3. **Pi RAM:** decided 2026-10-18: **4GB** (nothing bought).
4. **Allow-list for the live brain test:** **ISO only (800–12800).** The brain plans every lever, but only ISO changes are made; shutter/aperture/WB proposals are shown as "would change". Expand after the director has seen it behave.

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
- [x] **Step 6: The dashboard** (built overnight 2026-10-17, fake camera only). [docs/step6-dashboard.md](docs/step6-dashboard.md). *Waiting for director review.*
  - Live view (clean / zebras / false color, face brackets, light sources), setting tiles, status + last change, Auto (starts Off in live, two presses to turn on), Lock, look picker, **"this face looks right"** (per person, stored only on this computer), highlight meters, 60 s exposure chart with tooltip + table, decisions feed, big kill switch (also Space). S4D style from LANDFALL. Phone layout with the kill switch pinned.
  - Checked with screenshots driven like a person; 5 bugs found and fixed. 58 tests pass.
  - ❓ For the director: (1) Lock = "hold everything now" (my reading of your Step 5 rule); (2) face signatures are stored locally (biometric data); (3) screenshots with your face are not committed.
- [~] **Step 7: Prove it works.** [docs/step7-test-plan.md](docs/step7-test-plan.md): **FINAL** (approved 2026-10-18, frozen). Shooting not started.
  - Ready, no camera needed: `metrics.csv` logging + `m` mark key, `tools/score_take.py` (measurement definitions fixed in code, 4 tests), balanced take order from a fixed seed (`tools/make_test_order.py`).
  - ✅ All 8 questions answered 2026-10-18 and written into the plan (63 scored takes + 6 bonus + sunset, ~3.5–4 h, two sessions).
  - ✅ **Approved as FINAL 2026-10-18; frozen at commit 22d1165 (tag `step7-plan-final`).**
  - ✅ Tools built (no camera): recording switch (all 3 layers, off by default, agent takes only), read-only Display LUT reader, printable run sheet (87 rows), private anonymous rating page + counting. [docs/step7-tools.md](docs/step7-tools.md).
  - ❓ Not in the frozen plan, needed before ratings: count partial raters' answered scenes or completers only; how remote raters reach the page.
  - ⏳ Needs the camera: read the Display LUT (read-only) and name the LUT file in the plan.
- [x] **Step 8: Raspberry Pi 5 plan (plan only, nothing bought).** [docs/step8-pi-plan.md](docs/step8-pi-plan.md). Pi 5 4GB build ≈ $244. Pi 5 likely fast enough (~33 ms/frame est. vs 41.7 ms budget); Jetson not needed. Risks: SDK unproven on Pi 5 (use Bookworm + 4K-page kernel), 5V/5A power from D-tap. *Waiting for director review.*
- [~] **Step 9: Package it.** Started overnight: README rewritten (what it does, how it thinks, safety, skin tones, results so far with sources, setup, honest limits, "How this was built"); [INTERVIEW.md](INTERVIEW.md) drafted with 10 Q&As + 3 draft resume bullets (real numbers only). Waiting on Step 7 results and a demo video.

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
