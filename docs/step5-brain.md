# Step 5: The brain (the cinematographer)

Built and tested with **no camera**: in a camera simulator and on recorded frames. Nothing here talks to the FX2.

## How it decides (`agent/brain.py`)

Explainable rules, no black box. Each update looks at what the eyes measured (smoothed over the last half second) plus the camera's current settings. It returns **at most one** proposed change with a one-line reason, plus **advice** for things only a person can do.

| # | Rule | In plain words |
|---|---|---|
| 0 | Recording lock | While the camera records, nothing changes (unless you allow it). |
| 1 | 180° shutter | Shutter = 1/(2 × frame rate), e.g. 1/48 at 23.98p. If the slower shutter would clip highlights, it lowers ISO first; if it can't, it asks for ND instead of moving. |
| 2 | Outside your ranges | If ISO or aperture starts outside your approved range, it **pauses exposure changes and tells you** (default; **your decision pending**, see below). |
| 3 | Aperture from the look | Each look has its f-stop (shallow f/2.8, run-and-gun f/5.6…). |
| 4 | Exposure | **Protect important highlights first** (skies, windows, faces; small lamps and screens may clip), **then faces**, then the overall scene. ISO fills the gap, staying on **base ISO 800 / 4000** when possible, then aperture inside the look's range, then **ND advice**. In Cine EI it never touches ISO (the recorded ISO is locked there). |
| 5 | White balance | Only between takes, only when the light's color estimate is trusted and steady for about 3 s. On Auto WB it advises: "set a Kelvin value before rolling". |

**Smooth behavior:**
- **Dead band:** errors within ⅓ stop are left alone.
- **Reaction time:** each look waits its reaction time before acting (0.5–2 s), so a walk-by or a window flash never triggers a change.
- **Settling:** after any change, it waits ≥ 0.6 s (twice the 0.3 s the real FX2 needed to show an ISO change in Step 3), plus the look's minimum gap.
- **No back-and-forth:** it won't undo a change within 5 s unless the error is big.
- **Safety margin:** after darkening for clipping, it keeps double the safety margin for 15 s.
- **Small steps:** ⅓ stop (run and gun: ⅔).

Every change carries one reason, e.g. *"Highlights clipping 25.0% (limit 1.5%): ISO 3200 → 2000"*, *"Face −1.0 st (target +1.0): ISO 2000 → 4000 (base ISO)"*, *"Too bright at ISO 800 and f/2.8 (the look's aperture): add at least 3 stops of ND"*.

## The five looks (`agent/looks.py`)

Starting points; every number is yours to tune. Exposure is in stops vs 18% grey (S-Log3 reference = 0).

| Look | Aperture | How it controls brightness | Face target | Reacts after | Clip allowed |
|---|---|---|---|---|---|
| **Cinematic 24p (shallow)** | f/2.8, kept for the look | Base ISO, then **asks for ND**; closes to f/4 only as a last resort if a sky/window keeps clipping and no ND is added for 5 s | +1.0 | 1.5 s | 0.5% |
| **Run and gun** | f/5.6 (f/4–f/8) for focus safety | ISO freely, then aperture; ⅔-stop steps | +1.0 | 0.5 s | 1.5% |
| **Interview (face priority)** | f/4 (f/2.8–f/5.6) | Holds the face; slow and steady; background may clip a little, the face never | +1.0 | 2 s | 2% |
| **Low light** | f/2.8 | ISO up to 12800, preferring high base 4000; accepts a darker key; asks for light | +0.5 | 1 s | 1% |
| **Photo portrait** | f/2.8 (–f/4) | Base ISO first; shutter left to you (approved range is video only) | +1.0 | 1 s | 0.5% |

## Tests without a camera

**Simulator (`agent/sim.py`, `agent/scenes.py`):** a fake FX2 + scene that reacts to the brain with the delays measured in Step 3 (a change lands in 0.15 s and shows 0.15 s later). It runs your Step 7 situations plus stress tests. Full log: `docs/results/step5_simulator_scenes.txt`.

| Scene | Look | Changes | Back-and-forth | Clipping (s) | What it did |
|---|---|---|---|---|---|
| Static shot | Cinematic | 0 | 0 | 0 | Left it alone |
| Window flashes in for 1 s (walk-by) | Cinematic | 0 | 0 | 1.0 (the flash) | Ignored it |
| Person crosses the lens 1.2 s | Cinematic | 0 | 0 | 0 | Ignored it |
| Face wobbling at the threshold | Cinematic | 1 | 0 | 0 | One ⅓-stop fix, no flicker |
| Sunset, −3 stops over 100 s | Cinematic | 9 | 0 | 0 | ⅓-stop ISO steps, one direction; used 2500/3200 because jumping to base 4000 would have clipped the sky |
| Window behind a darker face | Interview | 1 | 0 | 2.3 | Protected the window, then "add light to the subject" |
| Shade → sun (+3.8 st) | Run and gun | 5 | 0 | 2.3 | Down to base ISO and f/8 within 3.7 s, then "add ⅔ stop ND" |
| Tungsten room, WB 5600K | Cinematic | 6 | 0 | 0 | ISO up to base 4000, WB → 3200K |
| Very low light | Low light | 5 | 0 | 0 | ISO to 12800, then "too dark by 1⅓ stops: add light" |
| Bright day, nobody adds ND | Cinematic | 3 | 0 | 30 | "Add at least 3 stops of ND", then last resort f/4 |
| Bright day, operator adds ND | Cinematic | 0 | 0 | 4.7 | Aperture stayed f/2.8; ND fixed it |
| Sunset while recording 20–100 s | Cinematic | 0 while rolling | 0 | 0 | Locked, caught up after the cut |
| Cine EI mode | Cinematic | 0 | 0 | 0 | Never touched ISO; advised light |
| Starts at 1/160 | Cinematic | 1 | 0 | 0 | 1/160 → 1/48 |

**30 brain tests** (`tests/test_brain.py`) lock these behaviors in. One of them checks that **every proposal in every scene is inside your approved ranges** (ISO 800–12800, f/2.8–f/11, 1/100–1/48, 2800–7500K) and has a reason. With the 7 eyes tests: **37 tests, all passing.**

**Bugs the simulator caught (all fixed before touching a camera):**
- A jump to base ISO 4000 that clipped the sky.
- An 800 ↔ 1000 oscillation with a bright window behind a face.
- ND advice that said "⅓ stop" when about 3 were needed.
- A 180° shutter move that would have brightened an already clipping picture.

**Recorded frames (`tools/brain_replay.py`):** the eyes + brain on your real frames, with your camera's real saved settings and a "virtual camera" that pretends proposals were applied (approximate). Log: `docs/results/step5_replay_real_frames.txt`.
- *After your shoot (ISO 102400, 1/160, clipping 10%):* it changes nothing. It says the 180° shutter needs about 1⅔ stops less light first (add ND), and that ISO 102400 is outside your range.
- *Step 3 dark room (ISO 800, 1/160):* 1/160 → 1/48 first, then ⅓-stop ISO steps up as the room reads 3–5 stops under, while ignoring the chat window and the hand.

## Honest limits

- **Simulator ≠ camera.** Delays come from the real Step 3 measurements, but the scene and clipping model are simplified. The real test is Step 7.
- **Exposure numbers depend on the live-view calibration**, which is still a guess (A = 103.6, B = 22.9) until the grey card/paper test.
- **Face target +1.0 stop** suits typical lighter skin; darker skin correctly sits lower. A one-tap "this face is right" reference per person is planned for the dashboard, so the agent holds *your* exposure choice instead of a single number.
- **White balance** won't change on the real camera yet: the color estimate is marked low confidence until calibrated. Today it only advises.
- **Focus:** no focus actions (your rule).
- **Not wired to the camera.** The bridge allow-list still only allows ISO, so shutter, aperture and WB proposals would be refused until you approve them for a live test.
