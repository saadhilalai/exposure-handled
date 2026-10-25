# Step 7 day sheet: Saturday 2026-10-24, session 1 (indoors)

> **Two Terminal windows, that's all:**
> ```
> ~/camera-agent/tools/step7.sh bridge            # window 1, once: leave it open all day
> ~/camera-agent/tools/step7.sh S1_R1_A_agent     # window 2, each take, in the run sheet's order
> ```
> Window 2 runs that take's exact run-sheet command, with the dashboard at http://127.0.0.1:8770/. **SPACE** in window 2 is the kill switch.

**This is the real test, not a rehearsal.** The printed run sheet is the plan, and this page is only how to run it. Sessions go to `sessions/`, named after the take.

**Saturday is session 1 only** (director, 2026-10-21):
- **Scenes:** S1 window-backlit face, S3 tungsten, S4 low light and S6 static control, with **both people (A and B)**.
- **Takes:** 54 scored and 5 bonus, 59 in all. Allow about 2.5–3 hours.
- **On the printed sheet** these are the first pages, under "Session 1 · daytime, indoors". The session 2 pages (S2, S5) come after a page break: leave them for the next clear day.
- **Shoot S1 while there's daylight in the window,** since its event is opening the blind.

## Bring

- [ ] Sony cinema camera, with 3+ charged batteries, and enough card space for about 1.5 hours of footage at your codec
- [ ] Lens, **variable ND**, tripod
- [ ] **USB-C data cable** (the one from Oct 19)
- [ ] MacBook and its **charger**, plus an outlet nearby: it's a long day
- [ ] **The printed run sheet** and a pen, including the consent page for each person
- [ ] For the events:
  - S1: a blind on the window.
  - S3: two tungsten lamps.
  - S4: a dim practical on a dimmer.
- [ ] Both people, A and B, with their consent page signed

## Before you start (at home)

- [ ] Write on the printout: the list in docs/step7-tools.md, section 0. It covers the fixed iris, naming faces A and B, no m in S6, and clip numbers. (The S5 note is for session 2.)
- [ ] Check the camera's clock against the Mac's.
- [ ] If the robot is training on this Mac, pause it.
- [ ] You emailed yourself the plan's fingerprint (`7b2a9e69…a2303b`).

## Camera, for every take (set by hand, the same for all three methods)

- 23.98p, S-Log3 (Flexible ISO), **1/48**, **the look's f-stop** (the iris stays there, Manual included), **WB in Kelvin** for the scene, and the same starting ISO and ND.
- **The camera's Auto ISO is on only for FX2-auto takes** (range 800–12800), and off again straight after.
- USB Connection Mode **Remote Shoot/Trn.**, no phone app connected.

## Start

1. Plug in the USB cable. **Window 1:** `tools/step7.sh bridge` → "Bridge ready".
2. **Say "camera ready"** to your coding assistant. From then on it watches the logs, read-only.
3. **Window 2**, each take: `tools/step7.sh <take name from the sheet>`. A typo is refused, with the closest names shown.
4. **Each person's first take** (S1_R1_A_agent, S1_R2_B_agent): type **A** or **B** in the dashboard's face box, then press **This face looks right**.

## Each take (the sheet's tick boxes)

| Method | Before | During | After |
|---|---|---|---|
| **Agent** | Type LIVE, then press **Auto** twice | **Rec** → at 15 s make the event and press **m** → at 50 s stop Rec | **q**, write the clip number |
| **FX2 auto** | Camera **Auto ISO on** | Rec → event + m → stop | q, then **Auto ISO off** |
| **Manual** | The dashboard isn't visible to you | Expose by hand (ISO, ND; the iris stays put) → Rec → event + m → stop | q |

- **S6:** don't press m.
- **Bonus takes** (after a person's scored rounds in a scene): follow the agent's advice.

## If something goes wrong

- **Stop the agent:** SPACE in window 2, the dashboard's Kill switch, or unplug the cable. The camera keeps its last settings.
- **Window 1 says the bridge stopped:** Ctrl-C there, then `tools/step7.sh bridge` again.
- **Reshoot a take:** run the same take name again. The newest session counts, and the old one stays. Write why on the sheet.
- **A take is unusable for a non-exposure reason** (focus miss, someone walks in): write why on the sheet before anyone rates. The blind test then uses that person's next round.

## End of the day

1. Ctrl-C in window 1: the bridge stops, and the Mac may sleep again.
2. Copy the card into a folder called **STEP7-2026-10-24**, never next to rehearsal footage.
3. Tell your coding assistant. It scores session 1's takes (`tools/score_take.py`) and lists the cut points for the 15 blind-test clips shot today (`tools/blind_clips.py`).
4. **The rating page waits for session 2.** Two of the blind test's seven sets (S2 and S5) are shot then, and raters see all 21 clips together.

## Session 2: the next clear day

- **Scenes:** S2 around midday (person A, shade to sun), then S5 starting about 25 minutes before sunset (2-minute blocks; press m at each block's start). These are the sheet's session 2 pages.
- **Bring** a marked line on the ground between the shade and the sun.
- **Same two windows** as Saturday: `tools/step7.sh bridge`, then each take by name.
- This page gets its own session 2 section before that day.
