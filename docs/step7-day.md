# Step 7 day sheet: Saturday 2026-10-24

> **Two Terminal windows, that's all:**
> ```
> ~/camera-agent/tools/step7.sh bridge            # window 1, once: leave it open all day
> ~/camera-agent/tools/step7.sh S1_R1_A_agent     # window 2, each take, in the run sheet's order
> ```
> Window 2 runs that take's exact run-sheet command, with the dashboard at http://127.0.0.1:8770/. **SPACE** in window 2 is the kill switch.

**This is the real test, not a rehearsal.** The printed run sheet is the plan, and this page is only how to run it. Sessions go to `sessions/`, named after the take.

## Bring

- [ ] FX2, with 3+ charged batteries (about 3.5–4 hours of shooting), and enough card space for about 2 hours of footage at your codec
- [ ] Lens, **variable ND**, tripod
- [ ] **USB-C data cable** (the one from Oct 19)
- [ ] MacBook and its **charger**, plus an outlet nearby: it's a long day
- [ ] **The printed run sheet** and a pen, including the consent page for each person
- [ ] For the events:
  - S1: a blind on the window.
  - S3: two tungsten lamps.
  - S4: a dim practical on a dimmer.
  - S2: a marked line between shade and sun.

## Before you start (at home)

- [ ] Write on the printout: the list in docs/step7-tools.md, section 0. It covers the fixed iris, naming faces A and B, S5's 2-minute blocks, no m in S6, and clip numbers.
- [ ] Check the FX2's clock against the Mac's.
- [ ] If the robot is training on this Mac, pause it.
- [ ] You emailed yourself the plan's fingerprint (`7b2a9e69…a2303b`).

## Camera, for every take (set by hand, the same for all three methods)

- 23.98p, S-Log3 (Flexible ISO), **1/48**, **the look's f-stop** (the iris stays there, Manual included), **WB in Kelvin** for the scene, and the same starting ISO and ND.
- **FX2 Auto ISO is on only for FX2-auto takes** (range 800–12800), and off again straight after.
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
- **S5:** 2-minute blocks; press m at each block's start.
- **Bonus takes:** follow the agent's advice.

## If something goes wrong

- **Stop the agent:** SPACE in window 2, the dashboard's Kill switch, or unplug the cable. The camera keeps its last settings.
- **Window 1 says the bridge stopped:** Ctrl-C there, then `tools/step7.sh bridge` again.
- **Reshoot a take:** run the same take name again. The newest session counts, and the old one stays. Write why on the sheet.
- **A take is unusable for a non-exposure reason** (focus miss, someone walks in): write why on the sheet before anyone rates. The blind test then uses that person's next round.

## End of the day

1. Ctrl-C in window 1: the bridge stops, and the Mac may sleep again.
2. Copy the card into a folder called **STEP7-2026-10-24**, never next to rehearsal footage.
3. Tell your coding assistant. It runs the scoring (`tools/score_take.py`) and the blind-test cut list (`tools/blind_clips.py`). You export the 21 clips with the same LUT, then the rating page goes out (docs/step7-tools.md, sections 4–5).
