# Step 7 tools (built after the plan was approved)

The plan itself is frozen ([step7-test-plan.md](step7-test-plan.md), tag `step7-plan-final`). These are the tools it needs on the day and afterwards. None of them needed the camera to build; all were tried on the fake camera or with stand-in clips.

## 1. The recording switch (agent takes only, off by default)

The agent normally changes nothing while the camera records. For Step 7 agent takes only, you approved one exception: **ISO, and nothing else, may change while recording.** All three layers must agree, and each refuses on its own:

| Layer | How it's switched on | What it allows |
|---|---|---|
| C++ bridge | Started with `--allow-iso-while-recording` (startup only; can't be combined with `--read-only`; can't be turned on later) | ISO while recording; every other setting still refused |
| Safety gate | The runner's switch | ISO while recording; logs `while_recording` on every change |
| Runner | `--allow-iso-while-recording`, which only starts if it's live, has a take name like `S1_R3_A_agent`, and the bridge has its flag on | Lock still holds; kill switch still works |

The dashboard shows a red **REC** chip, plus an amber **"Rec switch on · S1_R3_A_agent"** chip while it's on.

![Switch on](screenshots/step7_rec_switch_on.png)

**On the day:** start the bridge with the flag for a Step 7 session and restart it without the flag afterwards. The runner's switch goes on per agent take, as the run sheet says. FX2-auto and manual takes run in dry run, so nothing is ever sent in those.

9 tests: off by default; refuses to start unless everything lines up; ISO changes while recording with both switches on; Lock holds; the gate allows only ISO; the bridge refuses if its own flag is off even when the gate says yes.

## 2. The Display LUT reader (read-only)

`python tools/read_display_lut.py sessions/<folder>`, with the bridge started `--read-only` (it refuses otherwise). It reads from the camera:
- **Display LUT** on or off (`MonitorLUTSetting`)
- **the selected Base Look** (`BaseLookValue`, decoded as Sony documents it: preset, user, scene file or temporary, plus an index)
- **the camera's own names** for every Base Look (Sony's display strings)

It prints one line to copy into the plan, e.g. *"Base Look: … (User, value 0x0101), Display LUT: ON, read on …"*. Then you find that LUT's `.cube` file and its exact file name goes into the plan **before any clip is graded**.

**Read on 2026-10-19:** Display LUT **OFF**, Base Look **"S-Log3"** (Preset, value 0x0001), which applies no conversion. The camera's other Base Looks are s709, 709(800%) and User1–16, all empty ("No Import"). So there's no LUT file to name yet: the director picks one before any grading, and the plan's LUT line records what was read.

## 3. The printable run sheet

`python tools/make_run_sheet.py` makes [step7-run-sheet.pdf](step7-run-sheet.pdf) (and `.html`): Letter, landscape.
- **Front:** consent per person, the face-memory choice, and the session checklist (bridge flag on, then off again; kill switch reachable).
- **Then every take in shooting order (87 rows):** 63 scored takes, 6 bonus takes and 18 sunset blocks, each with the exact command and tick boxes (Auto on / camera Auto ISO on and back off / Rec started / m / Rec stopped / q).
- **People are A and B.** Names are written on the paper, never in the repo.
- **Which takes go to the blind test is deliberately not on the sheet,** so nobody shoots those differently.
- It comes from the frozen order, and a test fails if that order ever changes.

## 4. The private rating page (blind test)

`tools/rater_server.py`, S4D style, phone first:

```
python tools/rater_server.py prepare clips.json     # copy the 21 exported clips in under random names
python tools/rater_server.py links 15               # 15 anonymous links (random codes)
python tools/rater_server.py serve --host 0.0.0.0   # phones on the same Wi-Fi can open it
python tools/rater_server.py results                # count it the way the plan says
```

- **Anonymous:** a link is a random 10-character code. No name or email is asked for or stored, and nothing records who got which link (don't write it down either). The server keeps no request log, so no IP addresses either.
- **Blind:**
  - each rater gets their own scene order and their own A/B/C labels, the same every time they reopen their link
  - clips are copied in under random file names and served under addresses made of random codes, so the page never learns the method or even the scene name
  - answers are saved by method on the server; each rater's A/B/C mapping is kept only for checking
- **Private:** everything lives in `sessions/step7-blind/` (never in the repo). Unknown codes get "not found".
- **Counting** is exactly the plan's rule:
  - pick share per method, per set and overall
  - mean rating per method with a 95% interval, resampling raters
  - "agent better" only if it has more picks **and** the rating-difference interval is above 0; otherwise "no clear difference"
- **Checked:**
  - two raters went through all 7 scenes on a phone-size screen in Chrome, with no errors
  - clips stream with the byte ranges iPhones need
  - 5 tests: own stable order per rater; the page never sees methods or scene names; last answer counts; "agent better" only when it clearly is, "no clear difference" when it isn't

| | |
|---|---|
| ![Intro](screenshots/step7_rater_intro.png) | ![A scene](screenshots/step7_rater_scene.png) |

(Stand-in clips from the fake camera, no people.)

**Not decided by the plan, so it needs your call before any ratings come in:**
1. **A rater who stops halfway.** Right now every answered scene counts. The alternative is to count only raters who finished all 7.
2. **Raters who aren't on your Wi-Fi.** The page runs on this Mac, so friends elsewhere need a way in. Options are a temporary secure tunnel, or meeting in person.
