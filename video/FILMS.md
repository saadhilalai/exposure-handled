# Exposure, Handled.: three launch films

**Status:** three drafts, made overnight on 2026-10-21/22 for the director to pick from. None of them is on the website.

| | Film | Length | Feel | Music |
|---|---|---|---|---|
| 1 | **Calm** (`v1-abstract/`) | 50 s | Minimal, quiet, intelligent: a quote, light gathering into the camera, the crew inside, the line | "Petrichor", Scott Buckley |
| 2 | **Hype** (`v2-hype/`) | 36.5 s | A product drop: cut on the beat, smash into the lens, parts blowing apart and slamming back | "Beast", Sascha Ende |
| 3 | **Story** (`v3-story/`) | 55 s | A filmmaker alone, the light changing, the moment you'd miss, the agent catching it | "Cassini", Scott Buckley |

All three are built the same way:
- **3D:** a new photoreal camera, path-traced in Blender (`blender/build_camera.py` builds it from code; `blender/shots.py` animates and renders every shot).
- **Edit:** HyperFrames projects, made by `tools/build_films.py` (edit, voice placement, mix and render).

## The rules the films follow (from the director's brief)

- **Words:** barely any, solid colour only (no gradient text).
- **No small print:** no tags, labels or side notes, and no small grey text. The only small text is the website link at the very end.
- **Pure black:** every text-only card (the quotes, every "Exposure, Handled." title) sits on pure black (#000), with no grain. Honesty notes live here, in `CREDITS.md`, and in the website's Nerd mode when a film is published.
- **The voice:** the agent's AI voice, loud and clear on top of the music, in short lines.
- **Camera name:** the films never say "FX2". On screen it is just *the camera*; in words, "Sony cinema camera".
- **No schedules:** no mention of upcoming shoots or schedules.
- **No AI-company names:** no mention of any AI company or assistant.
- **Every claim true:** no "first ever". See `docs/framing-research.md`.

## What the references taught (the five techniques used)

The full breakdown of the twelve references, plus one the director mentioned, is private, in `refs/BREAKDOWN.md` (git-ignored, like the films themselves). The five strongest techniques, and where each film uses them:

1. **Silence, then the hit.**
   - What: 3–5 moments per film land to the frame. Before each, the sound goes away for 0.4–1.2 s (true silence, or 20 dB down). Ordinary cuts don't chase every beat.
   - Calm film: 0.75 s of silence, then the camera lands.
   - Hype film: the track's own near-silence before the drop, and the music cut for the kill switch.
   - Story film: the music dips while the agent catches the light.
2. **Speed up, stop, hold.**
   - What: shots shrink toward a few frames, then a long hold of 3–6 s.
   - Hype film: the macro cuts into the smash zoom, then the slow-motion explode.
   - Story film: the cuts quicken into the moment, then the hold.
3. **One shape, many worlds.**
   - What: a circle that stays put while the world changes around it: the lens, the iris, the sensor, the sun.
4. **Light builds the product on black.**
   - What: hard edge light, a light sweep, the product revealed piece by piece. One accent colour: the agents' orange.
   - Calm film: points of light gather into the camera.
5. **Few words, lots of space.**
   - What: one short line at a time, white serif, cap height about 5% of the frame, hard on and hard off on a cut.
   - The voice speaks at under 2.8 words a second, with at least a second of air after each line.

## Framing

The research is in `docs/framing-research.md`.
- **The short answer:** the pieces exist, but nothing public combines them. The closest is an iPhone app, FrameCoach. It suggests changes with reasons, but each one needs a tap.
- **No "first" in the films.** A narrow first claim that might hold is written below, under the decisions, for the director to approve before it's used anywhere.
- **What the films say instead:** "A camera that thinks like a cinematographer," and, in the story, "What if your camera had a cinematographer inside it?"

## Honesty notes (for Nerd mode and the credits)

- **The 3D camera** is an original design: no maker's name or logo, and not a copy of any product.
- **The orange agents inside it are an illustration.** The real agent runs on a laptop and talks to a Sony cinema camera over USB.
- **What's real:**
  - The agent reads the live image and decides exposure by the chosen look.
  - It changes ISO, iris, shutter and white balance within approved ranges, and explains each change in one line.
  - The kill switch stopped it in 33 ms on the real camera.
- **Story film:** the footage is Saad's own, with no client work and no faces. The light dropping and coming back is done in the grade, to illustrate what the agent does. It isn't a recording of the agent working.
- **Narration:** an AI voice. Its lines are things the agent really does (watching the light, reading the picture in stops, keeping the look).
- **Rendering:**
  - Path-traced 4K runs about 50 s a frame on this Mac. So the moving shots are path-traced at 1920×1080 and scaled up to 4K, with a light glow pass.
  - The three stills are true 4K.

## Film 1: Calm (50 s)

| Time | Picture | Words / voice |
|---|---|---|
| 0.0 | Black | **I propose to consider the question,** (then) ***'Can machines think?'*** |
| 5.1 | Black | **Alan Turing, 1950** |
| 6.75 | Points of light drifting, slowly gathering into the shape of a camera | The agent, almost alone over the music: "I watch the light." · "I read it in stops." · "I keep your look." · "You keep the moment." (music swells under the last line) |
| 15.75 | Black, true silence (0.75 s) | |
| 16.5 | The hit: the solid camera, a soft flash and a low boom | |
| 19.0 | The camera opens like a flower; the crew glows inside | |
| 26.6 | One agent, close: its visor's histogram moving, its arm reaching to the sensor | |
| 33.2 | The camera closes; the crew settles | **A camera that thinks / like a *cinematographer.*** (on the music's lift) |
| 45.2 | Pure black (text-only cards are always #000, no grain) | **Exposure, *Handled*.** · "Exposure… handled." · the website link |

## Film 2: Hype (36.5 s, cut on the beat of "Beast", 115 BPM)

| Time | Picture | Words / voice |
|---|---|---|
| 0.0 | Black; a strip of light rakes the silhouette | **A CAMERA** · **THAT THINKS** · *like a cinematographer.* |
| 2.1 | Macro cuts: the dial's knurling, the vents, the orange ring | |
| 4.2 | A whip orbit round the camera, hard rim light | "Light's changing." |
| 6.3 | The smash zoom down the lens axis into the glass | "On it." |
| 8.3 | **The drop:** the body blows apart in slow motion, the crew bursts out of the AI core | |
| 12.5 | Inside the lens: the iris snaps on four beats | **IT SEES.** |
| 14.6 | Deep into one agent at the sensor: its visor's histogram, its arm on the sensor frame, a scan line | **IT DECIDES.** · "Highlights first." · "Faces next." |
| 16.7 | The break: the front glass, the dial, the ring | "Done." |
| 18.8 | The crew racing round the exploded camera; the iris again | "Want it back?" · "One key." |
| 24.5 | The kill switch: the crew freezes red, the music drops out | "Stopped." |
| 26.1 | The parts drift, then slam home on the beat: flash, shake; the hero turns, held | "It's yours." |
| 30.3 | Pure black | **Exposure, *Handled*.** · "Exposure… handled." · the website link |

## Film 3: Story (55 s)

Cut to the hits of "Cassini" (3.18, 6.02, 8.98, 10.98 … 28.66, 37.34, and the big one at 43.04 s), in a 2.39:1 letterbox. The footage is graded to one look: a soft highlight roll-off, muted colour, cool shadows and warm highlights.

| Time | Picture | Words / voice |
|---|---|---|
| 0.0 | Black | **There is nothing in this world** (then) **that does not have a *decisive moment.*** |
| 9.0 | Black | **Cardinal de Retz** |
| 11.0 | A huge field, one tiny figure walking out into it (Saad's own, Osmo Pocket 3) | **The light won't wait.** |
| 16.8 | An empty grey beach | |
| 19.6 | A freight train through a chain-link fence; the light falls (the grade drops about 1¼ stops) | "Light's changing." · **Neither will the moment.** |
| 25.6 | Faster, darker: the beach, a headlight, the train | |
| 28.1 | Black, and the music drops away | |
| 28.7 | Inside the camera: an agent at the sensor sees it, whips round and reaches | "Got it." |
| 32.6 | The train, one long take; the exposure comes back on the cut and holds as it passes | |
| 43.0 | The big hit: the field again, wide and right | **What if your camera had / a *cinematographer* inside it?** |
| 47.0 | The camera, assembled, a slow push | "You frame. I'll handle the light." |
| 50.2 | Pure black | **Exposure, *Handled*.** · the website link |

The footage sources (all read-only, cut from the 4K originals) are listed in `tools/build_films.py` (FOOTAGE).
