# Step 7: Prove it works — test plan

> **FINAL: approved by the director on 2026-10-18, before any shooting.** Frozen at the commit tagged `step7-plan-final` (hash recorded in PROGRESS.md). **No rule changes after seeing results.** If something has to change on the day, it goes under "Deviations" with the reason, and the original rule is still reported. The only blank this plan allows to be filled in later is the LUT file name (see the blind test), and it must be filled in before any clip is graded.

## The question

Does the agent expose like a cinematographer?
- as well as you do by hand
- better than the FX2's own auto
- for **different people and skin tones**
- in real situations where the light changes

It's measured by numbers, then judged blind by people who don't know which clip is which.

## The three methods

| | Who controls exposure | The agent's role |
|---|---|---|
| **Agent** | The agent, live, Auto on. It may change **ISO only** (800–12800). | Drives |
| **FX2 auto** | The camera's own **Auto ISO only**, range set to 800–12800. | Measures only (dry run, sends nothing) |
| **Manual** | You, by hand, as on a job (ISO, ND, iris if you want). You watch the camera's own monitor and zebras, not the agent's dashboard. | Measures only (dry run, sends nothing) |

**The same for all three in a scene:**
- 23.98p, S-Log3 (Flexible ISO)
- **1/48 shutter and the look's f-stop, both set by hand**
- WB set by hand to a Kelvin value for the scene
- the same starting ISO and ND
- tripod, marked framing and focal length, Sigma 28-70

**Advice:** in the scored takes, **nobody follows the agent's ND or light advice**. It's logged, so the write-up can say when it was right. Separately, each face scene gets **one bonus take per person where you follow its advice like an AC**. Bonus takes are shown in the write-up, but they're **not** part of the comparison or the blind test.

**Recording:** the agent normally changes nothing while the camera records. For Step 7 agent takes only, a switch lets it change ISO while recording. The switch is **off by default** and turned on per agent take. It will be built after you approve this plan; all three safety layers need it, since each refuses changes while recording today.

**One measuring instrument for everything:** the agent's calibrated eyes run in every take and log 4 times a second to `metrics.csv`. In FX2 auto and manual takes the runner is in dry run, so it can't change anything.

## People

- **At least two people with different skin tones** (Person A, Person B; names go on the run sheet, not in the repo).
- **Everyone does the two toughest face scenes:** the backlit window (S1) and low light (S4). The other face scenes are split: shade → sun (S2) with Person A, tungsten (S3) with Person B, and the sunset (S5) with whoever is free that evening.
- **Face targets are yours, not a formula.** Before a person's first take, you frame them and press **"this face looks right"** once. That exposure is what the agent holds, and what **all three methods are scored against** for that person.
- **Consent, before anything:** each person agrees to being filmed and to their clips being shown privately to the raters. Face memory is separate and optional. Anyone who'd rather not have it is scored against the look's +0.5 default, and the agent uses that default for them too. Clips go in the README or a demo video only with a separate OK.

## Scenes

| # | Scene | Look | What changes (the "event") | Who | Takes |
|---|---|---|---|---|---|
| S1 | **Window-backlit face**: seated, bright window behind (daylight) | Interview (f/4) | At 15 s: open the blind fully. Hold 35 s. | everyone | 2 people × 3 rounds × 3 methods = 18, + 2 bonus |
| S2 | **Shade → sun walk**: open shade into direct sun around midday, ND set for the shade | Run and gun (f/5.6) | At ~15 s, walk into the sun on a marked line and stand there. | Person A | 9 + 1 bonus |
| S3 | **Indoor tungsten**: two tungsten lamps, WB 3200K | Cinematic (f/2.8) | At 15 s one lamp off (≈ −1 stop); at 35 s back on. | Person B | 9 + 1 bonus |
| S4 | **Low light**: one dim practical on a dimmer | Low light (f/2.8) | At 15 s dim about 1 stop. | everyone | 18 + 2 bonus |
| S5 | **Sunset**: same framing from ~25 min before sunset | Cinematic (f/2.8) | Nothing staged: the light falls. 2-minute blocks, methods rotating. | one person | 18 blocks (36 min) |
| S6 | **Static control**: nothing changes | Cinematic | Nothing. Counts false moves. | nobody needed | 9 |

Takes are 50 s (S6: 60 s). Press **`m`** at the exact moment of each event, on the keyboard or the dashboard. Settle time is measured from that mark.

**Total:** 63 scored takes, 6 bonus takes and the 36-minute sunset, about **3.5–4 hours over two sessions**:
- **Session 1, daytime, indoors** (S1 needs daylight in the window): S1, S3, S4, S6, with both people.
- **Session 2, a clear day:** S2 around midday, then S5 at sunset.
- **Dates and places: you'll pick them later.** Rain only moves session 2.

### Take order (balanced, from a fixed seed: `tools/make_test_order.py`, seed 20261018)

For every scene and person, each method is shot first, second and third exactly once, so no method always gets the warm-up slot or the later light. In S1 and S4 the two people's rounds alternate (R1 = Person A, R2 = Person B, and so on), so neither always gets the earlier light. Bonus takes come after a person's scored rounds in that scene.

| Scene | Who | Rounds |
|---|---|---|
| S1 Window-backlit face | Person A | R1: Agent → Manual → FX2 auto · R3: FX2 auto → Agent → Manual · R5: Manual → FX2 auto → Agent |
| S1 Window-backlit face | Person B | R2: Agent → Manual → FX2 auto · R4: Manual → FX2 auto → Agent · R6: FX2 auto → Agent → Manual |
| S4 Low light | Person A | R1: Manual → Agent → FX2 auto · R3: Agent → FX2 auto → Manual · R5: FX2 auto → Manual → Agent |
| S4 Low light | Person B | R2: Agent → Manual → FX2 auto · R4: Manual → FX2 auto → Agent · R6: FX2 auto → Agent → Manual |
| S2 Shade to sun walk | Person A | R1: Agent → Manual → FX2 auto · R2: Manual → FX2 auto → Agent · R3: FX2 auto → Agent → Manual |
| S3 Tungsten interior | Person B | R1: Agent → Manual → FX2 auto · R2: FX2 auto → Agent → Manual · R3: Manual → FX2 auto → Agent |
| S6 Static control | nobody | R1: FX2 auto → Agent → Manual · R2: Agent → Manual → FX2 auto · R3: Manual → FX2 auto → Agent |

S5 Sunset, 2-minute blocks: Manual, Agent, FX2 auto / FX2 auto, Manual, Agent / Agent, FX2 auto, Manual / Manual, FX2 auto, Agent / Agent, Manual, FX2 auto / FX2 auto, Agent, Manual.

## Measurements (exact; computed by `tools/score_take.py`, written and tested before shooting)

| Measure | Definition |
|---|---|
| **Clipped highlights** | Mean % of the frame clipped in *important* areas (not small practicals), and % of the take's time over the look's limit (0.5–2%). |
| **Face brightness** | Mean distance from that person's target, in stops, and % of the time within ⅓ stop. Rows with a face only. |
| **Time to settle** | After each mark: seconds until the face (no face: the scene key) is on target and **stays there 2 s**. On target means within ⅓ stop of the person's target; for the key, within ⅓ stop of the look's window. That's the same tolerance as the agent's dead band, applied to all three methods. Capped at 30 s ("didn't settle"). |
| **Flickers** | Times the picture's overall brightness reverses direction within 5 s, with each move at least 1/12 stop. Moves in the 1.5 s after a mark are ignored (that's the light change itself). Measured from the picture, so it works for all three methods. |

Checked on made-up takes with known answers and on a fake-camera take (a 1-stop drop with the Cinematic look: settled in 5.25 s, 0 flickers). There are 4 tests in `tests/test_score_take.py`.

## What counts as "it works" (decided now)

| | Expectation | Scenes |
|---|---|---|
| H1 | The agent clips less than FX2 auto (lower mean important clipping in at least 2 of 3 rounds, per person) | S1, S2 |
| H2 | The agent's face error is within ⅓ stop of yours on average | S1–S5 |
| H3 | The agent flickers no more than FX2 auto, and **0** in the static control | all; S6 |
| H4 | The agent settles within 10 s after every mark | S3, S4 |
| H5 | **Fairness:** the agent's mean face error for Person A and Person B differ by no more than ⅓ stop (FX2 auto's and yours are reported alongside, for context) | S1, S4 |

Each one is reported as **supported / not supported / unclear**, with the numbers, failures included. Three rounds per scene and person is small: this is evidence, not proof, and the write-up will say so.

## Blind test

- **Which clips** (drawn in advance, same seed; the same round for all three methods):
  - S1: Person A R5, Person B R2
  - S4: Person A R1, Person B R6
  - S2 (Person A): round 3
  - S3 (Person B): round 1
  - S5: block round 2
  - That's 7 sets of 3 clips. If a take is unusable for a reason that **isn't** exposure (focus miss, someone walks in, recording failed), use that person's next round, and write down why *before* anyone rates.
- **Same treatment:**
  - **The same LUT your FX2's Display LUT is set to** (its selected Base Look), identical for every clip, no other grading. It's read from the camera, read-only, the next time it's connected (`tools/read_display_lut.py`), and the exact file is named here **before any clip is graded**:
    - **LUT file: Sony's official s709 LUT for S-Gamut3.Cine/S-Log3, from Sony's "s709 cubes" download (s709Cubes.zip, pro.sony LUT library), the director's pick on 2026-10-19; exact .cube name: ___ (written here when downloaded, before any grading)** (camera read on 2026-10-19: Base Look S-Log3 (Preset, value 0x0001), Display LUT OFF, so no LUT was selected on the camera; s709 is also one of the FX2's built-in Base Looks; movies record in S-Gamut3.Cine)
  - the same 12-second window, starting 3 s before the mark (S5: the middle 12 s of the block)
  - no audio, same export settings
  - file names are random codes
- **Raters:** at least 10 friends (15–20 is better) who weren't at the shoot and don't know which is which. You pick them.
- **How they rate:** a small private page I'll build. Each rater opens their own link on a phone; it shuffles the order of the sets and the A/B/C labels per person and collects the answers in one place.
- **Two questions per set:**
  1. "Which clip has the best exposure?" (pick one)
  2. "Rate each clip's exposure 1–5" (look for blown highlights, faces too dark or too bright, visible brightness jumps)
- **How it's counted:**
  - pick share per method, per set and overall
  - mean rating per method with a 95% interval (resampling raters)
  - the agent "beats" FX2 auto only if it gets more picks overall **and** the rating difference's interval is above 0; otherwise the result is "no clear difference"
  - same rule against Manual

## Run sheet (every take)

1. Reset the scene. Set by hand: start ISO, 1/48, the look's f-stop, WB Kelvin, ND start.
2. Start the session:
   - Agent: `python tools/run_agent.py --live --dashboard --look <look>`, with the recording switch on for this take, then Auto on.
   - FX2 auto: camera on Auto ISO, then `python tools/run_agent.py --look <look>` (dry run).
   - Manual: `python tools/run_agent.py --look <look>` (dry run).
3. **You** start recording on the camera (the agent never does).
4. At 15 s: make the event and press `m`.
5. At 50 s: stop recording, `q`, and write the take name (e.g. `S1_R3_A_agent`) next to the session folder on the sheet.
6. After agent takes: put ISO back (the runner offers).

## To build after you approve (no camera needed)

1. The record-while-agent switch (off by default; Step 7 agent takes only).
2. The private rater page.
3. A printable run sheet from the take order.

## Decisions (your answers, 2026-10-18)

1. Recording: allow ISO changes while recording **only for Step 7 agent takes**, behind a switch that's **off by default**.
2. Levers: **ISO only**.
3. FX2 auto: **Auto ISO only**.
4. Advice: **nobody follows it in scored takes**; one **bonus take** per face scene and person where you follow it, not scored against the others.
5. LUT: **the same LUT as the FX2's Display LUT**, read from the camera (read-only) at the next connection; the exact file is named above before any clip is graded (refines "Sony's official LUT", 2026-10-18).
6. Raters: **a small private page I build**; at least 10, ideally 15–20, none at the shoot.
7. Subjects: **2+ people with different skin tones**. Everyone does S1 and S4; S2, S3 and S5 are split.
8. Dates and places: **you'll pick them later** (one daytime indoor session, one clear-day session).

## Safety during the test

All camera safety rules stay:
- only ISO changes (800–12800)
- the recording switch is off unless it's an agent take
- kill switch at hand: Space, the dashboard button, or `tools/kill_switch.py`
- settings snapshot and restore every session
- the agent never starts or stops recording, and never touches format, codec, frame rate or media

## Deviations

None.
