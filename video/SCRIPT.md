# Exposure, Handled.: narrated film, script v1 (for the director's approval)

**Status:** draft for approval. Nothing is rendered with a voice until the lines are approved. The film itself is built (`video/film/`) with music and subtitles, ready for the voice. Line times are the edit's (`video/film/cues.json`). The words are unchanged since v1 went out; only some times moved by a few tenths of a second.

**Shape:** 70 s, 1920×1080 authored, rendered at 4K. The agent narrates in first person, like a camera assistant calling it on set. There are 14 short lines, about 38 s of talking, with music in every gap.

**Voice:** an AI voice (ElevenLabs), speaking as the agent. Every line paraphrases something the agent really did or really does. The end credits and the website's Nerd mode say it's an AI voice.

**Music:** "Penumbra" by Scott Buckley (CC BY 4.0), from 0:13.5 into the track. Its swells come about every 9.4 s, and the cuts land on them (♪ below). It ducks under every line, and it drops out for one beat at the kill switch.

**Tags on screen:**
- **REAL** (teal): the live test on the camera. Its 11 live-view frames, its log lines and its numbers.
- **ILLUSTRATION** (lavender): the website's 3D camera and its simulated picture.
- **PLACEHOLDER** (amber): the real dashboard software running on the fake camera.
- **STAND-IN** (yellow): until the Step 7 footage replaces it.

## Lines

| # | Time | Spoken | On screen | Tag | Where every number comes from |
|---|---|---|---|---|---|
| 1 | 0:00.8 | "I'm your camera's assistant." | Black → the website's viewfinder: REC, timecode, ISO 3200 · 1/48 · F2.8 · 3500K. A slow push in. | ILLUSTRATION | — |
| 2 | 0:03.6 | "You frame the shot. I'll handle the exposure." | The push keeps going. At 7 s it pulls back: the viewfinder is the 3D camera's rear screen. | ILLUSTRATION | — |
| — | ♪ 0:11.0 | *(music swell)* | The body comes apart, slowly, in a long orbit. The orange crew switches on. | ILLUSTRATION | — |
| 3 | 0:11.6 | "Twenty-four times a second, I read the picture. In stops. Like a DP." | Kinetic type: **24 frames a second** / **measured in stops** | ILLUSTRATION | Live view at 24 fps on the camera, measured in stops vs 18% grey (README; the live test) |
| 4 | 0:16.2 / 0:17.5 / 0:18.8 | "Sensor. Iris. Color." (one word on each shot) | The crew swarms each one in turn: a push into the sensor, the iris blades turning, the color chip repainting. | ILLUSTRATION | — |
| 5 | 0:19.6 | "Only inside the ranges you approve." | The three ranges draw on as arcs: **ISO 800–12800 · f/2.8–f/11 · 2800–7500 K** | ILLUSTRATION | `config/safe_ranges.json` (approved by the director) |
| — | ♪ 0:20.5 | *(music swell)* | A push into the sensor, which ends in light at 0:21.4, then the card **[the live test's date]** / *a real Sony cinema camera · over USB · a white wall and one lamp* | REAL | — |
| 6 | 0:22.0 | "[The live test's date.] A real camera." | (same card) | REAL | The live test, its self-test session |
| 7 | 0:24.0 | "Two and a half stops hot. Coming down a third." | The real live-view frames, full screen. ISO ticks **6400 → 5000 → 4000 → 3200 → 2500 → 2000** at the real pace (one step every ~1.7 s). The agent's own log lines type in beside it. | REAL | Test 1: the log says "Scene +2.6 st", and each step is a third of a stop |
| 8 | 0:33.0 | "Exposure good. Holding." | **Settled in 8.4 s** / **then 60 s, no changes** | REAL | Test 1: settled at 8.4 s, status "Exposure good", 0 changes in the 60 s hold |
| 9 | 0:35.6 | "Interview look. Shutter, one forty-eighth. Iris, f/4. White balance, twenty-eight hundred." | The four real changes pop in one at a time: **1/50 → 1/48 · f/8 → f/4 · ISO 3200 → 1600 · 3700 K → 2800 K** (small: *light measured ≈ 2642 K; 2800 K is the approved floor*) | REAL | Test 3, all four settings, settled in 12.5 s |
| 10 | 0:42.6 | "Every change is logged. Old value, new value, and why." | The dashboard. A push into its decision log, which becomes the real live-test log lines. **44 sent · 44 confirmed · 0 refused** | PLACEHOLDER (dashboard) + REAL (log lines, counts) | The live test's bridge log, whole session (the test's setup and restores included) |
| 11 | 0:47.2 | "Want it back? One key." | The assembled camera, the crew busy. | ILLUSTRATION | — |
| — | ♪ 0:49.0 | *(music drops out)* | KILL: the crew freezes and dims, a red KILLED state. | ILLUSTRATION | — |
| 12 | 0:49.8 | "Stopped. Thirty-three milliseconds. It's yours." | **33 ms** | REAL | The live kill switch test: the agent stopped in 33 ms and the bridge locked |
| 13 | 0:53.4 | "Next: a blind test. Me, the camera's own auto, and a human." | The S3 stand-in: the lamp goes off and ISO climbs back. **Next: the blind test** | STAND-IN | The Step 7 plan (agent vs Sony cinema camera Auto ISO vs by hand, rated blind) |
| — | ♪ 0:58.0 | *(music swell)* | The camera snaps back together and turns slowly. | ILLUSTRATION | — |
| 14 | 1:02.6 | "Exposure… handled." | Title: **Exposure, Handled.** | — | — |
| — | 1:04.5–1:10 | — | Credits: *Narration: an AI voice, speaking as the agent. The lines retell its real logs.* · *Music: "Penumbra" by Scott Buckley, CC BY 4.0, scottbuckley.com.au* · *Designed & built by Saad Hilal · S4D* · *github.com/saadhilalai/exposure-handled* | — | — |

**Subtitles:** burned in (D-DIN, small, low centre), plus a `.vtt` caption file for the website's player.

## What changes after the Step 7 shoot

- Line 13 and its clip become a real take (S3, the lamp goes off), with its real log line on screen. If the agent's real move differs, the line is re-recorded to match it.
- The dashboard shot (line 10) becomes a recording on the camera, and its PLACEHOLDER tag comes off.
- When the blind test is rated (after session 2), a results line can replace "Next: a blind test".

## Lines I chose not to use (and why)

- "Sky's starting to clip. Closing a third." In Step 7 the agent moves ISO only, and in the real tests it never closed the iris for a clipping sky. It opened f/8 → f/4 for a look.
- "Face is under. Bringing it up." The live face test on the camera hasn't happened yet: it's on the rehearsal's and Step 7's lists.
- "Locked. Recording." The agent never starts recording, and "Locked" means you're holding every setting, not that it is.
