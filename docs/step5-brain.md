# Step 5: The brain (the cinematographer) and the runner

The brain was built and tested with **no camera**, in a camera simulator and on recorded frames. The runner (eyes → brain → safety gate → bridge, with a kill switch) is built and tested against a **fake camera**. That was the state when this was written. **The live test has since run on the camera (2026-10-19): [step5-live-test.md](step5-live-test.md).**

## How it decides (`agent/brain.py`)

Explainable rules, no black box. Each update looks at what the eyes measured (smoothed over the last half second) plus the camera's current settings. It returns **at most one** proposed change with a one-line reason, plus **advice** for things only a person can do.

| # | Rule | In plain words |
|---|---|---|
| 0 | Recording lock | While the camera records, nothing changes (unless you allow it). |
| 1 | 180° shutter | Shutter = 1/(2 × frame rate), e.g. 1/48 at 23.98p. If the slower shutter would clip highlights, it lowers ISO first; if it can't, it asks for ND instead of moving. |
| 2 | Outside your ranges | If ISO or aperture starts outside your approved range, it **pauses exposure changes and tells you** (your decision, 2026-10-17). |
| 3 | Aperture from the look | Each look has its f-stop (shallow f/2.8, run-and-gun f/5.6…). |
| 4 | Exposure | **Protect important highlights first** (skies, windows, faces; small lamps and screens may clip), **then faces**, then the overall scene. ISO fills the gap, staying on **base ISO 800 / 4000** when possible, then aperture inside the look's range, then **ND advice**. In Cine EI it never touches ISO (the recorded ISO is locked there). |
| 5 | White balance | Only between takes, only when the light's color estimate is trusted and steady for about 3 s. On Auto WB it advises: "set a Kelvin value before rolling". |

**Only what you approved.** The brain gets the list of settings it may actually change (today: **ISO only**, from `config/safe_ranges.json`). It still plans every lever, and shows the rest as advice: *"Would change, not approved yet: 180° shutter for 23.98p: 1/50 → 1/48"*. With ISO only, it never lowers ISO "to make room" for a shutter move it isn't allowed to make.

**Smooth behavior:**
- **Dead band:** errors within ⅓ stop are left alone.
- **Reaction time:** each look waits its reaction time before acting (0.5–2 s), so a walk-by or a window flash never triggers a change.
- **Settling:** after any change, it waits ≥ 0.6 s (twice the 0.3 s the real camera needed to show an ISO change in Step 3), plus the look's minimum gap.
- **No back-and-forth:** it won't undo a change within 5 s unless the error is big.
- **Safety margin:** after darkening for clipping, it keeps double the safety margin for 15 s.
- **Clipping memory (new):** after darkening because an exposure clipped, it won't go back up to that exposure for 60 s, unless the light itself has dropped (measured from the picture). Then the limit moves up by exactly that much. Status while held: *"Holding: face −0.6 st (target +0.5); any brighter would clip"*, plus "add light to the subject".
- **Small steps:** ⅓ stop (run and gun: ⅔).

Every change carries one reason, e.g. *"Highlights clipping 1.5% (limit 0.5%): ISO 6400 → 5000"*, *"Face −1.9 st (target +0.5): ISO 2000 → 4000 (base ISO)"*, *"Too bright at ISO 800 and f/2.8 (the look's aperture): add at least 3 stops of ND"*.

## The five looks (`agent/looks.py`)

Starting points; every number is yours to tune. Exposure is in stops vs 18% grey (S-Log3 reference = 0).

| Look | Aperture | How it controls brightness | Face target | Reacts after | Clip allowed |
|---|---|---|---|---|---|
| **Cinematic 24p (shallow)** | f/2.8, kept for the look | Base ISO, then **asks for ND**; closes to f/4 only as a last resort if a sky/window keeps clipping and no ND is added for 5 s | +0.5 | 1.5 s | 0.5% |
| **Run and gun** | f/5.6 (f/4–f/8) for focus safety | ISO freely, then aperture; ⅔-stop steps | +0.5 | 0.5 s | 1.5% |
| **Interview (face priority)** | f/4 (f/2.8–f/5.6) | Holds the face; slow and steady; background may clip a little, the face never | +0.5 | 2 s | 2% |
| **Low light** | f/2.8 | ISO up to 12800, preferring high base 4000; accepts a darker key; asks for light | +0.5 | 1 s | 1% |
| **Photo portrait** | f/2.8 (–f/4) | Base ISO first; shutter left to you (approved range is video only) | +0.5 | 1 s | 0.5% |

**Face target +0.5 for every look** (your decision, 2026-10-17; it was +1.0). +1.0 suited lighter skin and pushed darker skin too bright. The planned Step 6 "this face looks right" button lets you set each person once, so the agent holds *your* exposure for that face instead of one number for everyone.

## Tests without a camera

**Simulator (`agent/sim.py`, `agent/scenes.py`):** a fake Sony cinema camera + scene that reacts to the brain with the delays measured in Step 3 (a change lands in 0.15 s and shows 0.15 s later). It runs your Step 7 situations plus stress tests. Full log: `docs/results/step5_simulator_scenes.txt` (re-run with the +0.5 face target).

| Scene | Look | Changes | Back-and-forth | Clipping (s) | What it did |
|---|---|---|---|---|---|
| Static shot | Cinematic | 0 | 0 | 0 | Left it alone |
| Window flashes in for 1 s (walk-by) | Cinematic | 0 | 0 | 1.0 (the flash) | Ignored it |
| Person crosses the lens 1.2 s | Cinematic | 0 | 0 | 0 | Ignored it |
| Face wobbling at the threshold (+0.05 to +0.35) | Cinematic | 1 | 0 | 0 | One ⅓-stop fix, no flicker |
| Sunset, −3 stops over 100 s | Cinematic | 6 | 0 | 0 | ⅓-stop ISO steps, one direction, ending on base 4000 |
| Window behind a darker face | Interview | 1 | 0 | 0 | Protected the window, then "add light to the subject" |
| Shade → sun (+3.8 st) | Run and gun | 6 | 0 | 1.1 | Down to base ISO 800 and f/8 within 3.7 s, then "add about 1 stop of ND" |
| Tungsten room, WB 5600K | Cinematic | 6 | 0 | 0 | ISO up to base 4000, WB → 3200K |
| Very low light | Low light | 5 | 0 | 0 | ISO to 12800, then "too dark by 1⅓ stops: add light" |
| Bright day, nobody adds ND | Cinematic | 3 | 0 | 9.9 | "Add at least 3⅓ stops of ND", then last resort f/4 |
| Bright day, operator adds ND | Cinematic | 0 | 0 | 4.7 | Aperture stayed f/2.8; ND fixed it |
| Sunset while recording 20–100 s | Cinematic | 0 while rolling | 0 | 0 | Locked, caught up after the cut |
| Cine EI mode | Cinematic | 0 | 0 | 0 | Never touched ISO; advised light |
| Starts at 1/160 | Cinematic | 1 | 0 | 0 | 1/160 → 1/48 |

**33 brain tests** (`tests/test_brain.py`) lock these behaviors in. One checks that **every proposal in every scene is inside your approved ranges** (ISO 800–12800, f/2.8–f/11, 1/100–1/48, 2800–7500K) and has a reason. Others check ISO-only mode and the clipping memory.

**Bugs the simulator caught (all fixed before touching a camera):**
- A jump to base ISO 4000 that clipped the sky.
- An 800 ↔ 1000 oscillation with a bright window behind a face.
- ND advice that said "⅓ stop" when about 3 were needed.
- A 180° shutter move that would have brightened an already clipping picture.

**Recorded frames (`tools/brain_replay.py`):** the eyes + brain on your real frames, with your camera's real saved settings and a "virtual camera" that pretends proposals were applied (approximate). Log: `docs/results/step5_replay_real_frames.txt`.
- *After your shoot (ISO 102400, 1/160, clipping 10%):* it changes nothing. It says the 180° shutter needs about 1⅔ stops less light first (add ND), and that ISO 102400 is outside your range.
- *Step 3 dark room (ISO 800, 1/160):* 1/160 → 1/48 first, then ⅓-stop ISO steps up as the room reads 3–5 stops under, while ignoring the chat window and the hand.

## The runner (`agent/runner.py`, `tools/run_agent.py`)

One live-view frame at a time: **eyes → brain → safety gate → bridge.**

```
live view ──► eyes (10-15 ms) ──► brain ──► proposal + one-line reason
                                              │
                    dry run (default): shown + logged as "would change", nothing sent
                    live: SafetyGate.change_setting()  ── checks your ranges, recording, kill switch, logs
                                              │
                                     C++ bridge  ── checks its own compiled-in allow-list (ISO 800-12800),
                                              │      read-only flag, lock, recording, value offered
                                              ▼
                                            Sony cinema camera
```

**Safety, layer by layer:**

| Layer | What it does |
|---|---|
| Dry run by default | Nothing is sent unless you start it with `--live`. On the real camera you also have to type `LIVE`. |
| Your approval list | Only settings with `change_allowed` in `config/safe_ranges.json` (today: ISO). The rest is advice. |
| Safety gate (Python) | Range check (ISO 800–12800), refuses while recording or after the kill switch, logs time, old, new, reason and timings to `changes.jsonl`. |
| Bridge (C++) | Its own allow-list compiled in, plus read-only, lock, recording and "value offered" checks. Live mode refuses to start on a read-only bridge. |
| **Kill switch** | **SPACE** (or Ctrl-C) locks the bridge over a separate connection, so it gets through even while a change is in flight, and stops the loop. A change already sent finishes (~0.15 s); nothing after it is sent. The bridge refuses every change until it's restarted. **`tools/kill_switch.py`** does the same from any other terminal; the runner notices within 1 s. And unplugging USB always works. |
| Runaway guard | More than 20 changes in a minute trips the kill switch (a smooth agent needs far fewer). |
| Refused change → pause | If the camera or the gate refuses a change (other than "recording started"), the agent pauses and says why. Press `p` to resume. |
| Session snapshot | Settings saved at the start and end (`settings_start.json`, `settings_end.json`). At the end it lists what changed, and who changed it (agent or by hand), and offers to put ISO back (through the same gate). After the kill switch it can't (the bridge is locked), so it tells you the value to set by hand. |

**Keys:** SPACE kill switch · `p` pause/resume · `1`–`5` look · `q` quit (offers restore) · Ctrl-C kill switch + quit · `h` help.

**Every session folder** (`sessions/<time>_runner-…`, not committed): `runner_log.jsonl` (start, every change / would-change / advice / status, a once-per-second summary with fps and eyes time, kill, end), `changes.jsonl` (the gate's log), `frames/change_NNN.jpg` (the frame that triggered each change), and the settings snapshots.

### Tried against a fake camera (no camera)

`tools/fake_bridge.py` is a fake Sony cinema camera that speaks the bridge's exact protocol, with the same checks as the real bridge. Its picture is a recorded frame made brighter or darker using the measured S-Log3 calibration, with the camera's measured delays (confirmed in 0.15 s, visible after 0.3 s).

**Demo on your real Step 4 frame** (ISO 1600, 1/50, f/5.6, face −2.3 st, lamp in frame), live against the fake, Cinematic look. The room light drops 1 stop at 20 s and rises at 32 s (to ½ stop brighter than the start):
- Start: "Would change, not approved yet: 1/50 → 1/48" and "f/5.6 → f/2.8" (advice only).
- ISO 1600 → 2000 → **4000 (base)** → 5000 → 6400 → clipping 1.5% → **back to 5000 and holds**: "any brighter would clip; add light to the subject".
- Light drops 1 stop → 6400 → 8000 → 10000, then holds again.
- Light comes up → highlights clip 8% → 10000 → 8000 → 6400 in 1.7 s steps.
- End: ISO put back to 1600 through the gate.
- 23.9 fps, eyes 15 ms per frame. Each change confirmed in 150 ms (the fake copies the camera's timing).

**A bug the fake camera caught (fixed):** the first run pumped 6400 ↔ 5000 three times. Cause: at ISO 6400 one more region next to your lamp counts as "very bright", so the lamp cluster grows to 5 regions, past the 4-region limit for a practical, and the lit wall suddenly counts as important clipping (0% at 5000, 1.5% at 6400). The fix is the clipping memory above, plus a permanent test (`test_no_pumping_when_one_step_brighter_clips`) that fails without it.

**Keyboard checked in a real terminal** (pseudo-terminal, keys sent like a person): `2` switched to Run and gun, `p` paused and resumed, SPACE killed it and locked the bridge, `q` + `y` restored ISO, Ctrl-C killed it cleanly, and `tools/kill_switch.py` from a second terminal stopped it within 1 s.

**9 runner tests** (`tests/test_runner.py`): dry run sends nothing · live sends only ISO, every change logged with a reason · kill switch locks the bridge and nothing more is sent · runaway guard · live refuses a read-only bridge · lock from another terminal stops it · no changes while recording · a refused change pauses · session end restores ISO through the gate.

**All tests: 49 passing** (7 eyes, 33 brain, 9 runner).

### Running it

```
python tools/run_agent.py --fake                # fake camera, made-up scene: no camera at all
python tools/run_agent.py --fake --live --frame <a live-view jpg> --iso 1600 --shutter 50 --fnumber 5.6 --light 20:-1
python tools/run_agent.py                       # dry run on the real bridge (run/bridge.sock)
python tools/run_agent.py --live                # live on the real camera: type LIVE to start, SPACE to kill
```

For the live test, run it in **your own Terminal window** so SPACE is under your finger. (Run in the background with no Terminal attached, there's no keyboard; then only `tools/kill_switch.py`, Ctrl-C or the USB cable stop it.)

## Honest limits

- **Simulator and fake camera ≠ camera.** Delays come from the real Step 3 measurements, but the scene and clipping models are simplified. The fake assumes clipped areas in a recorded frame are 1 stop over clip. The real test is the live ISO test, then Step 7.
- **The eyes' "practical vs important" split can flip** when a lit area around a lamp grows past 4 regions (seen above). The brain now copes (clipping memory), but the eyes rule itself is unchanged. Likely worth a softer rule after the live test.
- **Frames skipped during a change:** the runner waits for the camera to confirm each change (~150 ms on the camera), so about 4 frames are skipped each time (fps dips to ~18 for that second).
- **Ctrl-C during a change:** the change can still land on the camera, and then it's in the bridge's own log (`bridge_log.jsonl`) but not in `changes.jsonl`.
- **White balance** won't change on the real camera yet: not approved, and the color estimate is medium confidence at best. Today it only advises.
- **Focus:** no focus actions (your rule).
