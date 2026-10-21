# Camera Agent: brag video storyboard (draft, placeholder footage)

**Status:** built with placeholders on 2026-10-21. On Saturday, after the Step 7 shoot, swap in the real clips and numbers (see "Swapping on Saturday" below). The storyboard and composition are in git; footage, music and renders never are.

**Same style as the robot's film ("Walk Before You Climb"):**
- One product window of real footage, short plain sentences in sentence case, and one honest caveat under every claim.
- Black #0b0b0c, Geist and Geist Mono, everything centred, no grain or HUD.
- Soft word builds, cross-dissolves and cuts through black, about one change every 4–5 s.
- Music only, no sound effects: **"Penumbra" by Scott Buckley** (CC BY 4.0), a different track from the robot's with the same calm, cinematic feel. Its strings swell lands on the window growing full screen at 12.2 s.
- The one accent is the site's AI orange (#ff6a1a) instead of the robot's lavender, used only for "the agent".

**Format:** 1920×1080 authored, rendered at 3840×2160, 30 fps, 40 s. No vertical version (same as the robot).

## Beats

| # | Time | On screen | Words | Footage | Status |
|---|---|---|---|---|---|
| 1 | 0–3.0 | Black | **"The light changed."** | — | final |
| 2 | 3.0–8.4 | The window, small and centred (0.6 scale, rounded), with a slow push-in | label: *S1 · window light · the blind opens* / **"The face went dark."** | **CLIP A**, part 1: S1 agent take. From 3 s before the mark, the blind opens and the face drops. | placeholder |
| 3 | 8.4–14.4 | Same window. At 12.2 it grows to full screen on the music's swell, then fades at 14.0 | label: *the agent's own log line for that moment* / **"It brought it back."** | **CLIP A**, part 2: the same take after the mark; the agent's ISO move brings the face back | placeholder (footage and the log line) |
| 4 | 14.4–17.2 | Black | **"Then we tested it blind."** | — | final |
| 5 | 17.2–25.6 | Three panes, same scene, same moment. They grow to full width at 21.4 | labels: *A* Camera auto · *B* By hand · ● *C* The agent. Status lines under each (from the results). Footnote: *One example: scene ?, round ?. Not the typical result.* | **CLIPS B1, B2, B3**: one scene and round, all three methods, from the same mark | placeholder (footage, status lines, footnote) |
| 6 | 25.6–32.4 | Black results card | kicker ● *The agent* / a big number / what it means / a thin rule / *the numbers · 63 takes, N raters, blind* / caveat | — | placeholder (all numbers) |
| 7 | 32.4–36.0 | Black | label: *kill switch · 33 ms · real FX2, Oct 19* / **"One key takes it back."** | — | final (33 ms is the real measurement from the Oct 19 live test) |
| 8 | 36.0–40.0 | End card | **Camera Agent** / Saad Hilal · S4D / github.com/saadhilalai | — | link is a placeholder until the repo is public |

**Why this order:** it shows the job in one moment (beats 2–3), then the test (5), then the result (6), then the trust line (7). It's the same shape as the robot film, which shows the skill, the test and the result.

**Honesty rules carried over:**
- Every number on screen comes from the Step 7 results or a session log, never from the simulator.
- The three-way example is labelled as one example, not the typical result.
- The results card gives the counts (takes and raters) and the caveat the results deserve.

## Swapping on Saturday

The composition is `video/composition/index.html`. Every placeholder has a yellow **PLACEHOLDER** tag (or yellow bracketed text) naming its slot, so nothing can slip through.

1. **Pick the takes.**
   - CLIP A: the S1 agent take whose face recovers most visibly.
   - B1–B3: one scene and round, all three methods. S3 "one lamp off" reads best side by side.
2. **Export** each clip from the card as H.264 1920×1080 at 29.97 or 30 fps, graded with the same LUT as the blind test. Save them in `video/composition/assets/video/` as `clipA.mp4`, `clipB1.mp4`, `clipB2.mp4` and `clipB3.mp4`.
3. **In-points:** each clip starts 3 s before its mark. The runner now logs Rec start, and the marks are in `runner_log.jsonl`. Exporting from (mark − 3 s) means no `data-media-start` maths.
4. **In `index.html`:** in each `<!-- SWAP ... -->` comment, uncomment the `<video>` line and delete the slate above it.
5. **Words and numbers:**
   - Copy the agent's real log line for the CLIP A take (its `change` event in `runner_log.jsonl`) into beat 3's label.
   - Write the three status lines and the footnote for beat 5 from what the clips show.
   - Fill in the results card from `score_take.py` and the rating page.
6. **Check, then render:** `npx --yes hyperframes@0.8.167 check`, then `render --resolution landscape-4k --quality delivery --fps 30`.

## Music

- **Track:** "Penumbra" by Scott Buckley, from his library (CC BY 4.0). Credit: *'Penumbra' by Scott Buckley - released under CC-BY 4.0. www.scottbuckley.com.au* (see CREDITS.md).
- **Why this track:**
  - It's quiet under the opening line.
  - Its strings swell (track 0:24.6) lands on the window growing full screen (12.2 s).
  - It builds slowly through the result and settles under the end card.
  - The excerpt was picked by measuring the track's loudness every half second, the same method as the robot film.
- **Rebuild the asset** (the audio isn't in git):
  ```
  ffmpeg -ss 10.4 -t 44 -i Penumbra.mp3 -af "volume=7dB" -ar 48000 -c:a aac -b:a 192k video/composition/assets/music/penumbra-scott-buckley-excerpt.m4a
  ```
  - The asset carries 2 s of handle on each side; the composition starts it at `data-media-start="2"`.
  - The 7 dB raise is a plain gain (no compression): the excerpt ends up at −17.6 LUFS, peaking at −1.9 dBTP.
- **Fades:** in over 0–2.2 s; out over 36.6–40 s.

## Still open

- **Title on the end card:** "Camera Agent" for now. Five names are suggested to the director.
