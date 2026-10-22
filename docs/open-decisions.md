# Open decisions for the director

## Answered (2026-10-21)

| # | Decision | Answer |
|---|---|---|
| 1 | Manual iris | **Fixed** at the look's f-stop. Written into the plan as Clarification 1. |
| 2 | Unrecognized faces | **Scored against the take's person.** Clarification 2 in the plan, built into `score_take.py`. Name people A and B in the face box. |
| 3 | Run-sheet notes | **Written by hand on the printout.** The list is in docs/step7-tools.md, section 0. |
| 4 | Plan fingerprint | **Emailed by the director:** `7b2a9e69b190f4d055f87d4acb2e536deaababe3bf262d4b0d93d8ffea2a303b` (with both clarifications; tag `step7-plan-clarified`). |
| 5 | Disclosure | **Said in the results** (as recommended). |
| 6 | Saturday's start | **`tools/step7.sh`** (as recommended). |
| 7 | Rehearsal | **Thursday 2026-10-22, at sunset.** |
| 8 | Pointer over buttons | **Keep the dot** (as recommended). |
| 9 | Depth of field on slower computers | **Keep** (as recommended). |
| 10 | End-card title | **Exposure, Handled.** It's on the end card, the website's title and the README. |
| 11 | Music | **"Penumbra" by Scott Buckley** (CC BY 4.0): a different track, same calm cinematic feel. |
| 12 | Commit the video source | **Yes**, the storyboard and composition. Footage, music and renders stay out (as recommended). |
| 13 | Saturday's sessions | **Session 1 only** (indoors: S1, S3, S4, S6, both people). Session 2 (S2 midday, S5 sunset) goes on the next clear day. |

None of 3, 5, 6, 8, 9 or 12 changes the frozen plan.

## New (2026-10-22, morning): the redo of all three films

Everything is in `video/FILMS.md` and `video/CREDITS.md`. None of it is on the website.

**29. The narrator.** The most human take came from ElevenLabs (voice "Dallin"), but its free account was blocked
mid-job ("Free Tier access has been disabled", which needs a paid plan). So all three films use one voice from the MiniMax
engine (through Higgsfield), "Harrison": low, calm, with natural pauses and breaths. The audition reel is
`video/films-voice/v2/voice-auditions.mp3` (Dallin, then Harrison, Gideon, Callum, Sterling).
- **A (recommended):** keep Harrison.
- **B:** a paid ElevenLabs plan, and I re-voice with Dallin.

**30. Which camera.** The brief said "FX3", and also "the camera we actually used". The camera this project drives is the
FX2, so the render is a faithful FX2 (EVF, grip, dials), without Sony's name or logo.
- **A (recommended):** keep the FX2.
- **B:** model an FX3 instead.

**31. The orange helpers in the calm film:** cut, so the film stays art first. They're the stars of the hype film.

**32. The hype film's real places.** Your Mac has no sunset, city-night, desert, forest or studio footage without client
work or faces, so those beats use licensed Pexels plates, out of focus behind the camera.
- **A (recommended):** keep them.
- **B:** send me your own clips of those places and I'll swap them in.

**33. The story film's footage.** It's all licensed Pexels stock now, because you named Pexels or Mixkit. Coverr clips
were also found (free for commercial use), but they're not used. Only one clip of yours qualified: a door opening onto
daylight in SHUTTER. It's not used, because SHUTTER is a YSV film and your notes keep YSV and S4D apart.
- Three of the clips show faces: the photographer with horses, the actor on a monitor, and the woman at the blinds. Your
  brief allows faces from licensed stock, and none of them is presented as endorsing the product.

**34. Music.**
- Calm: "Peace Within" (Peter Rudenko). Its piano may be sampled; the alternative is Chris Zabriskie's "The Temperature of the Air on the Bow of the Kaleetan".
- Story: "Cylinder Three" (Chris Zabriskie).
- Hype: "Beast", now 9 dB lower, ducking harder under the voice.
- All CC BY 4.0, and none is used in another of your films.

## New (2026-10-22, overnight): three films to pick from

Everything is in `video/FILMS.md`. The renders are in `video/v1-abstract/renders/`, `video/v2-hype/renders/` and `video/v3-story/renders/` (not in git). This replaces the hype draft below (17–20); its music and voice carry over.

**21. Which film?** Calm (50 s), Hype (36.5 s) or Story (55 s). Or tell me what to take from each.

**22. A "first" claim: not used anywhere yet.**
- The research (`docs/framing-research.md`) found nothing public that does all of this together: watches a pro cinema camera's live image, changes its exposure itself, steers by a chosen look, and explains each change. The closest, FrameCoach, needs a tap for every change.
- But "first" can't be proven, and FrameCoach is one feature away from making it false.
- If you want it, the safest wording is for a description, not the film: *"As far as we can find (October 2026), the first assistant that runs a cinema camera's exposure on its own, from a chosen look, and explains every change in plain English."*
- **Recommended:** leave it out. The films say "A camera that thinks like a cinematographer" instead.

**23. The story film's big line: "What if your camera had a cinematographer inside it?"** It's your line. The research flags that the agent runs on the laptop, not inside the camera.
- **A:** keep it. It's a question, a vision line, and the film shows the crew inside as an illustration.
- **B:** "...beside it?"
- **Recommended:** A.

**24. Voice.** All three films use the same AI voice as the hype draft, Imogen, kept loud and on top of the music, in short lines. Sloane and Orion are in the hype voice reels.
- **Recommended:** keep one voice across all your films.

**25. Music.** "Petrichor" (calm) and "Cassini" (story) by Scott Buckley, and "Beast" by Sascha Ende (hype). All CC BY 4.0, all checked on their own pages.
- Scott Buckley also scored the robot film, with a different track ("Meanwhile").
- "Beast" is still the 128 kbps preview: its full-quality file needs the "Download for free" button on ende.app (a click in a browser).
- **Recommended:** keep these. If Hype wins, download the full-quality Beast before the final.

**26. Quotes, and how their names are shown.**
- No real person's voice is used. The references' archival voice, a real scientist, isn't something to copy, and you said not to put words in real people's mouths.
- The calm film opens like the Nothing film instead, but with the agent's own voice.
- The quotes are on screen, real and checked:
  - Turing, 1950: "I propose to consider the question, 'Can machines think?'"
  - Cardinal de Retz, the epigraph of Cartier-Bresson's *The Decisive Moment*: "There is nothing in this world that does not have a decisive moment."
- Names get their own card, in white, never small grey text under the quote.

**28. The story film's footage.**
- The search was read-only: 1,412 videos on the Mac, 286 camera originals checked one by one.
- The story uses only clips that are clearly yours from personal days out (Osmo Pocket 3), with no faces. Plates and badges are cropped out.
- Some of the most cinematic footage on the Mac was left out because it might be client work, belongs to another company of yours, or shows faces. Those clips, and why each was left out, are in a private note that stays out of git: `video/v3-story/assets/footage/NOTES.md`.
- Say which of them are OK and I'll recut the story with them.

**27. Resolution.**
- **Now:** the moving 3D is path-traced at 1920×1080 and scaled up to 4K. Path-traced 4K is about 50 s a frame here, about 20 hours for all three films.
- **The stills:** true 4K.
- **Recommended:** once you pick a film, re-render just its 3D shots at 4K over a night.

## New (2026-10-21, night): the hype cut

You asked for a hype video instead of the slow narrated film, so decisions 14–16 below are replaced by these. Draft 1 is sent (`video/hype/renders/`, not in git). The cut sheet, with the source of every real thing on screen, is `video/HYPE.md`.

**17. Music.** The draft uses **"Beast" by Sascha Ende** (CC BY 4.0, 115 BPM, ende.app). Why I picked it:
- It has a riser, a beat of near-silence and a hard drop.
- Its own short break lands exactly on the kill switch, so the music cuts out there with no edit.
- Its last bar and final hit close the film.

The other candidates, all CC BY 4.0:
- "Sunstorm Trailer" (Sascha Ende): cinematic hybrid trailer.
- "Superbike XXL" (John Bartmann): 80s synthwave.
- "Exit the Premises" (Kevin MacLeod): steady 128 BPM, but no drop.

One catch: the draft uses ende.app's 128 kbps preview. For the final I need the full-quality file, which ende.app only gives through its "Download for free" button (it runs a browser check). Either I click it in your Chrome, or you download it and drop it in `video/hype/assets/music/`.

**18. Voice.** The draft uses **Imogen**: steady and cool, and the pitch hardly wanders. All three were made with the ElevenLabs engine through your Higgsfield plan, about 0.15 credits a line; 33 lines cost about 5 credits. Reels of all 11 lines are sent:
- Imogen (in the draft).
- Sloane: lower and warmer.
- Orion: male.

If you'd rather have Dior from the first auditions, that needs the ElevenLabs upgrade (decision 16, option A).

**19. Subtitles.** The cut has **none in the picture**, because the note said too many words on screen. The lines go in a caption file (`video/hype/captions.vtt`) for the website's player. Recommended: keep it that way.

**20. One example line swapped.** "Locked." became **"Got it."** In the dashboard, LOCKED means *you* are holding every setting, so the agent saying it would claim the opposite.

Everything else follows your note:
- 36.5 s.
- Five big words.
- One stat: **33 ms**, the kill switch, from the real Oct 19 test.
- Small tags on every shot.

---

## Replaced by the hype cut: the narrated film (decisions 14–16)

**14. Approve the script.** `video/SCRIPT.md`: 14 lines, about 38 s of talking in a 70 s film. Every number comes from the Oct 19 logs, and the source is beside each line. Change any line you like. Nothing gets voiced until you approve them.

**15. Which voice?** There are three auditions of lines 7, 8, 11 and 12 (sent, and in `video/composition/assets/voice/auditions/`, not in git):
- **Dior:** a crisp, neutral male voice, made for tech launch films.
- **Marie:** a cool American female voice (2 takes).
- **Recommended:** whichever sounds more like *your* assistant. If I had to pick blind: Dior, because "crisp with an edge" is the brief's "a little cool".

**16. Where the final voice comes from.** The ElevenLabs connection is a free account. It made these auditions, then refused the next request: *"Unusual activity has been detected on your account, so Free Tier access has been disabled… Please upgrade to a paid subscription."* I haven't retried. The options:
- **A (recommended if you like Dior or Marie): upgrade ElevenLabs** to its cheapest paid plan. It unlocks the account, keeps the exact voice you picked, and paid plans include a commercial license.
- **B: Higgsfield,** your paid plan (1,057 credits). It runs the same Eleven v4 engine, but with its own preset voices, not Dior or Marie. I'd audition 2–3 of those first, which costs a few credits.
- **C: a free voice that runs on this Mac** (open-source Kokoro, Apache license). It's less expressive than the two above, but not robotic.

Until you answer, I'm building the film's visuals timed to the script, with the music in. The voice drops in last.

---

## New (2026-10-21, afternoon)

**13. Is Saturday both sessions, or session 1 only?** *(Answered: session 1 only.)* The plan has two:
- Session 1: daytime, indoors, S1/S3/S4/S6, with both people.
- Session 2: a clear day, S2 around midday, then S5 at sunset.

docs/step7-day.md covers both. **Recommended:** session 1 on Saturday, and session 2 on the next clear day, because the plan says rain only moves session 2. Tell me if both are on Saturday, and I'll add a timeline (S2 at midday, S5 starting about 25 min before sunset).

---

*The original questions, as asked:*

Written 2026-10-21 while you were away.

## Before Saturday (Step 7)

**1. Manual takes: may you move the iris?**
- The frozen plan says both "Manual: ISO, ND, iris if you want" and "the same for all three: the look's f-stop, set by hand".
- Moving the iris changes depth of field, which raters could spot, so it would unblind them.
- **A (recommended):** Manual uses ISO and ND only, with the iris kept at the look's f-stop. Log it as a clarification under Deviations.
- **B:** The iris is allowed in Manual. Log it, and note it in the results.

**2. Whose face target scores a take when the camera doesn't recognize the face?**
- When recognition misses a frame (most likely backlit in S1 and dim in S4), the agent falls back to the look's +0.5 target. The plan scores against "that person's target".
- **A (recommended):** score every take against the person named in the take (S1_R1_A means person A), whatever the recognizer said. Decide before seeing results.
- **B:** score as logged.

**3. Run-sheet notes. The printed sheet is frozen, so these are by hand unless you OK a reprint.**
- S5 rows: each is a 2-minute block. The sheet's front note only says "take is 50 s (S6: 60 s)".
- S6 rows: don't press m, even though there's an "m at event" box.
- Write the camera's clip number in the notes column for each take, and check the FX2 clock against the Mac's before the first take. The 87 card files are otherwise matched by order and time.
- At each person's first take (S1_R1_A_agent, S1_R2_B_agent), press "this face looks right" first.
- **A (recommended):** write these on the printout.
- **B:** regenerate the sheet with them added. The take order and commands wouldn't change.

**4. Proof the plan wasn't changed after the shoot.**
- The git history was rewritten twice (to clean old wording), so the tag alone is weaker evidence than it was.
- The plan's fingerprint today (SHA-256 of docs/step7-test-plan.md): `f7e7f9d661c7fea2af8b8c666d17b431ec99d993597d4731251244a52b5b404d`
- **Recommended:** email that line to yourself before Saturday, so a timestamp outside this Mac holds it.

**5. Disclosure.** You run the Manual takes and you've read the plan, including the blind-test picks. That can't be fixed now. **Recommended:** say so in the results.

**6. Saturday's start script (new): `tools/step7.sh`.** One window runs the bridge for the day; a second runs each take by name, with the exact run-sheet command. See docs/step7-tools.md, section 0. **Recommended:** use it. The printed commands still work as they are, because the dashboard port now defaults to 8770.

## The rehearsal

**7. Which evening?** Wednesday or Thursday leaves a day to fix what it finds. Everything is ready: `tools/rehearsal.sh`, docs/rehearsal.md.

## Website

**8. Pointer over buttons.** The orange brackets now frame the button itself, so over anything clickable the pointer is a small orange dot rather than a second set of brackets. **Recommended:** keep it.

**9. Slower computers lose depth of field sooner.** When frames are slow because the computer's processor is busy (not its graphics chip), the page now drops to "medium" straight away. Medium has no depth of field on the 3D camera. Fast computers (like this Mac) keep it.

## Brag video (draft built with placeholders; not in git)

The storyboard is `video/STORYBOARD.md` and the composition is `video/composition/index.html`. It's 40 s, in the robot film's style, with every stand-in tagged in yellow.

**10. Title on the end card.** "Camera Agent" for now. The robot's film has a phrase title ("Walk Before You Climb"). **Recommended:** keep "Camera Agent" unless a line comes out of Saturday's footage.

**11. Music.** The draft has none. The robot's film used "Meanwhile" by Scott Buckley (CC BY 4.0). **Recommended:** a different CC BY track, chosen like the robot's: measure where its swell falls and line it up with the moment the window grows to full screen (12.2 s). Don't reuse another project's track; the robot's first draft was rejected partly for that.

**12. Commit the source?** The storyboard and composition are kept out of git (the `video/` folder is excluded locally). **Recommended:** commit the storyboard and composition source, but never renders or footage.
