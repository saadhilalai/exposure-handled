# Exposure, Handled.: three launch films

**Status:** the director's redo of all three (2026-10-22). Nothing is on the website until the director approves.

**Where they are (not in git):** `v1-abstract/renders/v1-abstract-4k.mp4`, `v2-hype/renders/v2-hype-4k.mp4`,
`v3-story/renders/v3-story-4k.mp4`. All 3840×2160, 24 fps, stereo AAC, mixed to -14 LUFS with the voice on top.

| | Film | Length | Feel | Music |
|---|---|---|---|---|
| 1 | **Calm** (`v1-abstract/`) | 58.6 s | Art first, after the AI-lab launch films: warm paper, hand-made shapes that become ideas, an old transmission of Turing's question, the camera shown once, as art | "Peace Within", Peter Rudenko |
| 2 | **Hype** (`v2-hype/`) | 36.5 s | A product drop: the camera locked in the centre while the world changes on every beat, then the glass reveal of the helpers at work inside | "Beast", Sascha Ende (turned down) |
| 3 | **Story** (`v3-story/`) | 55 s | A filmmaker, the light changing, the moment you'd miss, the helper inside the camera catching it | "Cylinder Three", Chris Zabriskie |

How they're made:
- **3D:** the camera this project drives, modelled from measured photos with no maker's name or logo (`blender/build_fx.py`), with an X-ray switch that turns every outer surface to glass. Path-traced in Blender Cycles (`blender/shots_fx.py`) at 1920×1080 and scaled to 4K with a light glow pass.
- **Edit:** HyperFrames projects, made by `tools/build_films.py` (edit, voice, mix, render). The calm film's art is SVG in `tools/calm_template.html`; the other two use `tools/films_template.html`.

## The rules the films follow (from the director's brief)

- **Words:** one or two at a time, big, solid colour, never a gradient. No labels, tags or side notes.
- **No small print:** no small grey text. The only small text is the website link at the very end.
- **Pure black:** every text-only card sits on pure black (#000) with no grain.
- **Camera name:** the films never say "FX2". In words, "Sony cinema camera".
- **No schedules,** and no mention of any AI company or assistant, anywhere in the films, files or commits.
- **Every claim true:** no "first ever". See `docs/framing-research.md`.
- **Footage:** no client work; faces only from licensed stock.
- **Honesty notes** live here, in `CREDITS.md` and in the website's Nerd mode, never on screen.

## Honesty notes (for Nerd mode and the credits)

- **The narrator is an AI-generated voice** (MiniMax engine through Higgsfield, voice "Harrison"). The calm film's opening reads Alan Turing's real 1950 sentence through a vintage-radio filter, so it sounds like an old transmission read aloud, not like Turing.
- **The 3D camera** is a model of the real camera, without its maker's name or logo.
- **The glowing helpers inside it are an illustration.** The real agent runs on a laptop and talks to the camera over USB. What's real:
  - it reads the live image and decides exposure by the chosen look;
  - it changes ISO, iris, shutter and white balance within approved ranges, and explains each change in one line;
  - the kill switch stopped it in 33 ms on the real camera.
- **Hype film:** the real places behind the camera are licensed stock plates (Pexels), thrown out of focus; the camera is composited in with its own light, reflections and shadow, and its iris changes with each world in the render. It's an illustration of the agent adapting, not a recording of it.
- **Story film:** the footage is licensed stock (Pexels; every clip and link in `CREDITS.md`). The light dropping is in the footage and the grade, to illustrate what the agent does.

## Film 1: Calm (58.6 s)

| Time | Picture | Words / voice |
|---|---|---|
| 0.0 | Paper. A dark field rises to meet a pencil horizon; a sun rises behind it | The radio-filtered voice: "I propose to consider the question... 'Can machines think?'" |
| 8.6 | Paper | **Alan Turing** (held 3.6 s) |
| 12.2 | A sun, its halos and rays drawn in | "Every image you've ever loved... started with light." · **Light** |
| 19.0 | A breathing shape, a shadow drifting across it | "And light... never holds still." · **Never still** |
| 25.0 | Lens rings and an 11-blade aperture that becomes an eye, and blinks | "What if your camera could see it change... the way a cinematographer does?" |
| 32.5 | A frame stepping through stops, a needle finding the middle | "Reading every stop. Keeping your look." · **Every stop** · **Your look** |
| 38.5 | The camera as a black silhouette on paper; a sweep of light reveals it | "So you can stay... in the moment." · **The moment** |
| 43.5 | Quickening cuts: lens glint, the dial, the ring, with art flashes between (each 0.3 s longer than the overnight cut) | |
| 49.05 | Pure black, held 2.5 s | |
| 51.55 | "Exposure, Handled." on ten surfaces in one band of the screen, cuts shrinking 0.42 → 0.16 s | a soft tick on each cut |
| 54.26 | Pure black | **Exposure, *Handled*.** · "Exposure... handled." · the website link |

## Film 2: Hype (36.5 s, on the beat of "Beast", 115 BPM)

| Beats | Picture | Words / voice |
|---|---|---|
| 0–12 | The camera locked in the centre. On every beat a new world: black, ochre, deep red, cobalt, sage, paper, then a sunset, a city at twilight, a desert, a forest, a studio, a stage. Its light, reflections and iris change with each | "New light." · "New place." · "Got it." |
| 12–16 | A smash zoom down the lens into the glass | **A camera** · **that thinks** |
| 16–24 | **The drop:** the body turns to glass; inside, the sensor, board, iris and fan glow, and the helpers burst out with light trails | "Sensor." |
| 24–28 | Through the glass barrel, the iris snaps on the beat, helpers on its ring | "Iris." |
| 28–32 | The colour chip: the helpers repaint it warm to neutral, tile by tile | "Color." |
| 32–36 | Macro cuts: glint, dial, ring, iris | |
| 36–47 | The helpers racing round the glass camera; inside again; the iris | "Want it back?" · "One key." |
| 47–50 | The kill switch: every helper freezes red, the music drops out | "Stopped." |
| 50–58 | Glass back to solid on the beat: flash, shake; the camera turns, held | "It's yours." |
| 58–70 | Pure black | **Exposure, *Handled*.** · "Exposure. Handled." · the website link |

## Film 3: Story (55 s, 2.39:1, an old-film texture throughout)

| Time | Picture | Words / voice |
|---|---|---|
| 0.0 | Two flat earthy fields under a soft curved horizon, on paper | "Every filmmaker knows this feeling." · **The light** · **won't wait.** |
| 8.6 | Match cut to a real ridge line at sunrise, a lone photographer | "You're alone. The light is perfect..." |
| 12.6 | A photographer against a burning dusk sky | |
| 15.2 | The sun sinking into cloud; the light falls | "and then... it isn't." |
| 18.2 | A cloud over the sun · blinds closing on a face · a setting sun · gulls in the last light, fading to black | "A cloud. A door. A setting sun. And the moment is gone." |
| 24.5 | Inside the glass camera: a helper at the sensor sees the light drop, whips round and reaches | "Unless someone is watching the light... with you." |
| 28.5 | A lens ring turning · a city going from day to night · a monitor on set | "It reads every stop. It moves when the light moves. And it tells you why." |
| 34.5 | A photographer framing at the sea · a photographer and horses in golden dust | "You frame the shot. It handles the light." |
| 41.0 | The camera, a slow push (on the music's second lift) | |
| 46.0 | A wave catching the low sun | |
| 48.6 | Pure black | **Exposure, *Handled*.** · "Exposure... handled." · the website link |

## The overnight drafts (replaced)

The first three drafts (2026-10-22, overnight) used an original camera design, the voice "Imogen", "Petrichor" and
"Cassini" (Scott Buckley), the de Retz quote, and Saad's own Osmo footage in the story. The director asked for this redo.
