# Step 7: Prove it works — test plan

> **DRAFT, not final.** Written overnight 2026-10-17, before any shooting. It becomes final only when you approve it. Then it's frozen (the commit is recorded here) and **no rule changes after seeing results**. If something has to change on the day, it goes under "Deviations" with the reason, and the original rule is still reported.

## The question

Does the agent expose like a cinematographer? Specifically:
- as well as you do by hand,
- better than the FX2's own auto,
- in real situations where light changes,
- measured by numbers, then judged blind by people who don't know which clip is which.

## The three methods

| | Who controls exposure | The agent's role |
|---|---|---|
| **Agent** | The agent, live, Auto on. Changes only what you've approved (today: ISO 800–12800). | Drives |
| **FX2 auto** | The camera's own **Auto ISO**, range set to 800–12800 to match. | Measures only (dry run, sends nothing) |
| **Manual** | You, by hand, as on a job (ISO, ND, iris if you want). You watch the camera's own monitor and zebras, not the agent's dashboard. | Measures only (dry run, sends nothing) |

**The same for all three in a scene:**
- 23.98p, S-Log3 (Flexible ISO)
- 1/48 shutter, set by hand
- the look's f-stop, set by hand
- WB set by hand to a Kelvin value for the scene
- the same starting ISO and ND
- tripod, marked framing and focal length, same subject, Sigma 28-70

During agent takes **nobody follows the agent's ND or light advice** (it's logged), so the numbers measure the agent alone (open question Q4).

**One measuring instrument for everything:** the agent's own calibrated eyes run in every take, logging 4 times a second to `metrics.csv`. For FX2 auto and manual takes the runner is in dry run, so it can't change anything.

**Face targets: yours, not a formula.** Before the first take of each scene, you frame each subject and press **"this face looks right"** once. That target is what the agent holds, and what **all three methods are scored against**. So a darker-skinned subject is judged by your eye, not by +0.5.

## Scenes

| # | Scene | Look | What changes (the "event") | Repeats |
|---|---|---|---|---|
| S1 | **Window-backlit face**: subject seated, bright window behind | Interview (f/4) | At 15 s: open the blind fully (window brighter, more of it in frame). Hold 35 s. | 3 rounds × 3 methods |
| S2 | **Shade → sun walk**: open shade into direct sun, clear day, ND set for the shade | Run and gun (f/5.6) | At ~15 s the subject walks into the sun on a marked line, then stands there. | 3 × 3 |
| S3 | **Indoor tungsten**: two tungsten lamps, WB 3200K | Cinematic (f/2.8) | At 15 s one lamp off (≈ −1 stop); at 35 s back on. | 3 × 3 |
| S4 | **Low light**: one dim practical on a dimmer | Low light (f/2.8) | At 15 s dim about 1 stop. | 3 × 3 |
| S5 | **Sunset**: same framing from ~25 min before sunset | Cinematic (f/2.8) | Nothing staged: the light falls. 2-minute blocks, methods rotating. | 18 blocks (36 min) |
| S6 | **Static control**: nothing changes | Cinematic | Nothing. Counts false moves. | 3 × 3, 60 s |

Takes are 50 s (S6: 60 s). Press **`m`** at the exact moment of each event (`m` on the keyboard or on the dashboard). Settle time is measured from that mark.

### Take order (balanced, drawn from a fixed seed: `tools/make_test_order.py`, seed 20261018)

Every method is shot first, second and third once per scene, so no method always gets the warm-up slot or the later light.

| Scene | Round 1 | Round 2 | Round 3 |
|---|---|---|---|
| S1 Window-backlit face | Agent → Manual → FX2 auto | FX2 auto → Agent → Manual | Manual → FX2 auto → Agent |
| S2 Shade to sun walk | Agent → Manual → FX2 auto | Manual → FX2 auto → Agent | FX2 auto → Agent → Manual |
| S3 Tungsten interior | Manual → Agent → FX2 auto | Agent → FX2 auto → Manual | FX2 auto → Manual → Agent |
| S4 Low light | Agent → Manual → FX2 auto | Manual → FX2 auto → Agent | FX2 auto → Agent → Manual |
| S6 Static control | Agent → Manual → FX2 auto | Manual → FX2 auto → Agent | FX2 auto → Agent → Manual |

S5 Sunset, 2-minute blocks: Agent, Manual, FX2 auto / FX2 auto, Agent, Manual / Manual, FX2 auto, Agent / Agent, FX2 auto, Manual / Manual, Agent, FX2 auto / FX2 auto, Manual, Agent.

## Measurements (exact; computed by `tools/score_take.py`, written and tested before shooting)

| Measure | Definition |
|---|---|
| **Clipped highlights** | Mean % of the frame clipped in *important* areas (not small practicals), and % of the take's time over the look's limit (0.5–2%). |
| **Face brightness** | Mean distance from your target, in stops, and % of the time within ⅓ stop. Rows with a face only. |
| **Time to settle** | After each mark: seconds until the face (no face: the scene key) is on target and **stays there 2 s**. On target means within ⅓ stop of your face target; for the key, within ⅓ stop of the look's window. That's the same tolerance as the agent's dead band, applied to all three methods. Capped at 30 s ("didn't settle"). |
| **Flickers** | Times the picture's overall brightness reverses direction within 5 s, with each move at least 1/12 stop. Moves in the 1.5 s after a mark are ignored (that's the light change itself). Measured from the picture, so it works for all three methods. |

Checked on made-up takes with known answers and on a fake-camera take: a 1-stop drop with the Cinematic look settled in 5.25 s with 0 flickers. There are 4 tests in `tests/test_score_take.py`.

## What counts as "it works" (decided now)

| | Expectation | Scenes |
|---|---|---|
| H1 | The agent clips less than FX2 auto (lower mean important clipping in at least 2 of 3 rounds) | S1, S2 |
| H2 | The agent's face error is within ⅓ stop of yours on average | S1–S5 |
| H3 | The agent flickers no more than FX2 auto, and **0** in the static control | all; S6 |
| H4 | The agent settles within 10 s after every mark | S3, S4 |

Each one is reported as **supported / not supported / unclear**, with the numbers, failures included. Three rounds per scene is small: this is evidence, not proof, and the write-up will say so.

## Blind test

- **Which clips:** the take number drawn in advance (same seed): S1 take 3, S2 take 1, S3 take 3, S4 take 3, S5 block round 5, using the same take number for all three methods. If a take is unusable for a reason that **isn't** exposure (focus miss, someone in frame, recording failed), use the next take number, and write down why *before* anyone rates.
- **Same treatment:**
  - one LUT for every clip (Q5), no other grading
  - the same 12-second window, starting 3 s before the mark (S5: the middle 12 s of the block)
  - no audio, same export settings
  - file names are random codes
- **Raters:** at least 10 friends who weren't at the shoot and don't know which is which. Each sees S1–S5, with the three clips in a different random order per rater, labeled A/B/C.
- **Two questions per scene:**
  1. "Which clip has the best exposure?" (pick one)
  2. "Rate each clip's exposure 1–5" (look for blown highlights, faces too dark or too bright, visible brightness jumps)
- **How it's counted:**
  - pick share per method, per scene and overall
  - mean rating per method with a 95% interval (resampling raters)
  - the agent "beats" FX2 auto only if it gets more picks overall **and** the rating difference's interval is above 0; otherwise the result is "no clear difference"
  - same rule against Manual

## Run sheet (every take)

1. Reset the scene. Set by hand: start ISO, 1/48, the look's f-stop, WB Kelvin, ND start.
2. Start the session:
   - Agent: `python tools/run_agent.py --live --dashboard --look <look>`, then Auto on.
   - FX2 auto: camera on Auto ISO, then `python tools/run_agent.py --look <look>` (dry run).
   - Manual: `python tools/run_agent.py --look <look>` (dry run).
3. **You** start recording on the camera (the agent never does; see Q1).
4. At 15 s: make the event and press `m`.
5. At 50 s: stop recording, `q`, and write the take name (e.g. `S3_r2_agent`) next to the session folder in the sheet.
6. After agent takes: put ISO back (the runner offers).

Estimated time: about 45 indoor/outdoor takes plus the 36-minute sunset, so roughly 2.5–3 hours over two sessions (S2 and S5 outdoors).

## Open questions for you (before this becomes final)

1. **Recording (the big one).** Your Step 5 rule: the agent locks while the camera records. But the blind test needs clips recorded *while the agent works*.
   - **A (recommended):** allow ISO changes while recording, **only for Step 7 agent takes**, behind a flag that's off by default.
   - **B:** record the FX2's HDMI on an external recorder while the camera itself isn't recording (needs a recorder).
   - **C:** use the Mac's live-view stream (too low quality for a blind test).
2. **Levers:**
   - **ISO only (recommended):** shutter and aperture are fixed by the look anyway, and it keeps the comparison with FX2 Auto ISO fair.
   - **ISO + others:** also approve shutter, aperture or WB for the test.
3. **FX2 auto:**
   - **Auto ISO only (recommended):** same lever as the agent.
   - **Full auto exposure:** the camera's auto iris, shutter and ISO.
4. **Advice during agent takes:**
   - **Nobody follows it (recommended):** measures the agent alone.
   - **You follow it like an AC would.**
5. **LUT for the blind test:**
   - **Sony's official S-Log3 → Rec.709 LUT (recommended)**
   - **Your own grade,** applied identically to every clip.
6. **Raters:** 10 at minimum. Who, and Google Form or a small page I build?
7. **Subjects:** I recommend **at least two people with different skin tones**, each set once with "this face looks right". That tests the fairness goal for real.
8. **Dates and places:** a clear day for S2 and S5 (with sunset time), and a rain backup.

## Ready now (no camera needed)

- `metrics.csv` logging and the `m` mark (keyboard and dashboard)
- the scoring script
- the take order
- the dashboard

**To build after you approve:** the record-while-agent flag (if Q1 = A) and, optionally, the rater page.

## Safety during the test

All camera safety rules stay:
- only approved settings change (today ISO 800–12800)
- kill switch at hand: Space, the dashboard button, or `tools/kill_switch.py`
- settings snapshot and restore every session
- the agent never starts or stops recording, never touches format, codec, frame rate or media

## Deviations

None yet (the plan isn't final).
