# Brag video credits

## The three launch films (2026-10-22, `v1-abstract/`, `v2-hype/`, `v3-story/`)

The films carry no credits or small print on screen (the director's rule); these lines go wherever a film is posted
(video description, the website's Nerd mode).

**Narration:** an AI voice (text-to-speech, the ElevenLabs engine through Higgsfield; voice "Imogen"), speaking as the
agent, in short lines. Nothing it says claims more than the logs show (see `FILMS.md`).

**Music:**
- Calm film: "Petrichor" by Scott Buckley, https://www.scottbuckley.com.au/library/petrichor/, CC BY 4.0. Used from 2:03.0, 50 s.
- Hype film: "Beast" by Sascha Ende, https://ende.app/en/song/10415-beast, CC BY 4.0. Same edit as the hype draft (0:12.55–0:45.94, then the last bar from 2:38.64).
- Story film: "Cassini" by Scott Buckley, https://www.scottbuckley.com.au/library/cassini/, CC BY 4.0. Used from 3:00.4, 55 s.
- On YouTube, Scott Buckley's own credit line goes in the description: 'Petrichor' (or 'Cassini') by Scott Buckley - released under CC-BY 4.0. www.scottbuckley.com.au
- None of the three tracks is used in another of Saad's projects. (The robot's film used a different Scott Buckley track, "Meanwhile".)

**Quotes (real, verified):**
- "I propose to consider the question, 'Can machines think?'" Alan Turing, "Computing Machinery and Intelligence", *Mind*, 1950 (its opening sentence).
- "There is nothing in this world that does not have a decisive moment." Cardinal de Retz, the epigraph Henri Cartier-Bresson chose for *The Decisive Moment* (1952).

**Sound effects** (CC0): Kenney "Impact Sounds" and "Sci-fi Sounds" (kenney.nl), "Swishes Sound Pack" by artisticdude (opengameart.org).

**Pictures:**
- 3D: an original camera (no maker's name or logo, not a copy of any product), modelled from code and path-traced in Blender Cycles (`blender/build_camera.py`, `blender/shots.py`). The orange agents inside it are an illustration: the real agent runs on a laptop and talks to the camera over USB.
- Story footage: Saad's own (no client work, no faces). The light dropping in the story is done in the grade, to illustrate.

**Type:** Instrument Serif and D-DIN, SIL Open Font License 1.1.

**Tools:** Blender (GPL), HyperFrames, GSAP, FFmpeg.

## The hype cut (`hype/`, current)

**Narration:** an AI voice (text-to-speech, the ElevenLabs engine through Higgsfield; draft voice "Imogen"), speaking as the agent. Its lines retell what the logs show (`HYPE.md`). The end card says it's an AI voice.

**Music:** "Beast" by Sascha Ende, https://ende.app/en/song/10415-beast, released under CC BY 4.0 (https://ende.app/en/standard-license).
- Used from 0:12.55 to 0:45.94, then its last bar from 2:38.64 to the end. Ducked under the voice, and out for three beats at the kill switch.
- The credit is on the end card, and must go wherever the film is posted.
- Not in git: save the track as `hype/assets/music/beast.mp3` and rebuild with `tools/build_hype.py`.

**Sound effects** (CC0, no credit required, credited anyway):
- Kenney "Impact Sounds" and "Sci-fi Sounds" (kenney.nl). License files are in `hype/assets/sfx/`.
- "Swishes Sound Pack" by artisticdude (opengameart.org).

**Pictures:**
- 3D illustration: the website's own camera, rendered frame by frame (`tools/capture_hype.py`).
- Real: the Oct 19 test on a Sony FX2, its live-view frames and its logged settings, sped up.
- Placeholder: the real dashboard on the fake camera.
- Stand-in: the lamp-off clip, until Saturday's footage.

**Type:** Instrument Serif and D-DIN, SIL Open Font License 1.1 (`hype/assets/fonts/`), the website's fonts.

**3D and motion:** three.js (MIT) and GSAP (GreenSock's standard license), the same copies the website uses.

## The narrated film (`film/`, replaced by the hype cut)

**Narration:** an AI voice (text-to-speech), speaking as the agent. The lines retell what its logs show (sources beside each line in [SCRIPT.md](SCRIPT.md)). The film's end credits and the website say so. The service and voice are named here once they're picked.

**Music:** "Penumbra" by Scott Buckley, released under CC-BY 4.0. www.scottbuckley.com.au
- The credit must appear wherever the film is posted (for YouTube, in the video description). It's in the film's end credits.
- Excerpt used: from 0:13.5, 70 s, raised 7 dB, ducked under the voice, with a fade in, a dip at the kill switch and a fade out. The audio isn't in git. Download the full mix from https://www.scottbuckley.com.au/library/penumbra/ and rebuild with the command in `tools/build_film.py`.

**Pictures:**
- Real: the Oct 19 test on a Sony FX2, its live-view frames and its log.
- Illustration: the website's own 3D camera and camera simulator, rendered frame by frame (`tools/capture_film.py`).
- Placeholder: the real dashboard on the fake camera.
- Stand-in: the "next" clip, until the Step 7 footage.

**Type:** Instrument Serif and D-DIN, SIL Open Font License 1.1 (`film/assets/fonts/`), the website's fonts.

**3D and motion:** three.js (MIT) and GSAP (GreenSock's standard license), the same copies the website uses.

## The silent draft (`composition/`, superseded)

**Music:** "Penumbra" by Scott Buckley, CC-BY 4.0. Excerpt 0:12.4–0:52.4, raised 7 dB, with a fade in and out (command in STORYBOARD.md).

**Type:** Geist and Geist Mono, SIL Open Font License 1.1 (`composition/assets/fonts/Geist-OFL-LICENSE.txt`).

**Animation:** GSAP (GreenSock's standard license).
