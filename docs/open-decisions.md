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

None of 3, 5, 6, 8, 9 or 12 changes the frozen plan.

## New (2026-10-21, afternoon)

**13. Is Saturday both sessions, or session 1 only?** The plan has two:
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
