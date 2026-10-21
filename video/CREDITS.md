# Brag video credits

## The narrated film (`film/`)

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
