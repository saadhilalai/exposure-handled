# Exposure, Handled.: the hype cut

**Status:** draft 1, 2026-10-21. Replaces the slow narrated film (`video/film/`, kept for reference) after the director's note: "too slow, too many words, looks like Nerd mode. Make it a hype video."

**Shape:**
- 36.5 s, 1920×1080 (the final renders at 4K).
- Cut on the beat of "Beast" by Sascha Ende (115 BPM).
- Eleven short voice lines, about 11 s of talking in total.
- Five big words, one real stat.
- No subtitles in the picture; a caption file (`video/hype/captions.vtt`) goes with the website's player.

**How it's built:**
- The edit is written in beats in `video/tools/build_hype.py`, so every cut, word, voice line and hit lands on the beat.
- The 3D shots are the website's own camera, rendered frame by frame on the same beat grid (`video/tools/capture_hype.py`). They have motion blur from four sub-frames per frame, and speed ramps on the orange crew.

**Honesty:**
- Every shot carries a small tag: 3D ILLUSTRATION, REAL (sped up), PLACEHOLDER or STAND-IN.
- Every number on screen is read from `site/data/site.json`, the Oct 19 FX2 logs.
- No "first ever" or "never seen" claims.

## The cut

Film times are seconds; a beat is 0.522 s.

| Time | Picture | Words / voice | Tag | Source of anything real |
|---|---|---|---|---|
| 0.0 | 3D: a whip orbit onto the camera in the dark | **A CAMERA** / **THAT THINKS** | 3D ILLUSTRATION | — |
| 1.0 | 3D: a macro across the lens, with its orange line | **like a *cinematographer.*** | 3D ILLUSTRATION | — |
| 2.1 | 3D: a push into the rear screen, which shows a real frame from the Oct 19 test | — | 3D ILLUSTRATION | `site/media/real/test1_05.jpg` |
| 4.2 | Real live view, white wall and lamp; ISO ticks 6400 → 5000 → 4000 → 3200 → 2500 → 2000; then EXPOSURE GOOD | "Too hot." "Coming down." | REAL · SPED UP | Test 1: scene +2.6 st, five ISO steps (8.4 s in real life) |
| 6.3 | 3D: a push into the lens. On the drop (8.3 s) the body blows apart in slow motion and the crew bursts out. Then a dive down the glass, through the iris as it opens, onto the sensor | "Got it." · **IT SEES.** | 3D ILLUSTRATION | — |
| 14.6 | 3D: the iris snapping on three beats, then the colour chip repainting warm to cool | **IT DECIDES.** | 3D ILLUSTRATION | — |
| 18.8 | Stand-in: the lamp goes off | "Light's changing." | STAND-IN | until Saturday's S3 take |
| 19.8 | Real live view; SHUTTER 1/50 → 1/48, IRIS f/8 → f/4, ISO 3200 → 2500 → 2000 → 1600, WB 3700K → 2800K flip on the beat; then EXPOSURE GOOD | "Interview look." | REAL · SPED UP | Test 3: all six changes (12.5 s in real life) |
| 21.4 | The dashboard: false colour, then Auto | "Done." | PLACEHOLDER | real dashboard, fake camera |
| 21.9 | 3D: a fast orbit, the crew everywhere | "Want it back?" | 3D ILLUSTRATION | — |
| 24.0 | 3D: the crew racing. At 25.0 s (the kill) it freezes red and the music drops out | "One key." "Stopped." · **33 ms** | 3D ILLUSTRATION + the stat's own "REAL TEST" label | Test 1 kill switch: the agent stopped in 33 ms |
| 26.1 | 3D: the parts drift in slow motion, then slam home on the beat (27.1 s), with a flash and a light sweep | "It's yours." | 3D ILLUSTRATION | — |
| 28.2 | The hero camera turning | "Exposure… handled." · **Exposure, *Handled.*** | 3D ILLUSTRATION | — |
| 33.4 | End card: CAMERA AGENT · Designed & built by Saad Hilal · S4D · github.com/saadhilalai/exposure-handled, plus the credits (AI voice, music, what each tag means) | — | — | — |

## Lines changed from the brief's examples, and why

- **"Locked."** In the dashboard, LOCKED means *you* are holding every setting. If the agent said it, it would claim the opposite. Here the agent says "Got it." instead.
- **"Sky's starting to clip."** Not used: no real test has had a sky in it yet.
- **"Face is under."** Not used: the live face test hasn't happened yet.
- The only numbers on screen are the kill switch's **33 ms** and the camera HUD's real settings from tests 1 and 3.

## What changes after Saturday

- **Stand-in shot:** becomes the real S3 take (the lamp going off), with its own log.
- **Dashboard flashes:** become a recording on the FX2, and the PLACEHOLDER tag comes off.
