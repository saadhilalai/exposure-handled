# Shakedown rehearsal: Thursday 2026-10-22, at sunset

> **Set (2026-10-21): Thursday 2026-10-22 at sunset.** It was moved from the 20th, and everything below stayed ready. "Tonight" means Thursday evening.

> **The one command, at the location** (camera plugged in, Terminal open):
> ```
> ~/camera-agent/tools/rehearsal.sh
> ```
> It makes the folder, starts the bridge, and starts the agent with the dashboard, which opens by itself. You type **LIVE**, then press **Auto** on the dashboard. **SPACE** is the kill switch, in that same window. Quit with **q**, and the bridge stops with it.

**Not the Step 7 test.** Tonight's goal is to find everything that breaks in real light before the official shoot on Saturday.
- Everything from tonight is labeled **rehearsal**.
- The agent's data goes to `sessions/REHEARSAL/`, and take names start with `REH_`.
- The scoring tool refuses to mix it with Step 7 takes.

What runs tonight:
- **The agent** controls ISO, aperture, shutter and WB, including while recording. That uses a rehearsal-only switch, off unless given, which a Step 7 take can't use.
- **The dashboard** is running.
- **Face test:** press "This face looks right" once.
- **Mini three-way comparison:** one or two shots, filmed by the agent, by the camera's Auto ISO, and by hand.
- **Problems** get logged the moment they happen.

> **Decided (2026-10-20):** Saturday stays **ISO only**, like the frozen Step 7 plan, with Sony cinema camera Auto ISO for the camera takes. Tonight's all-four-settings run is rehearsal only.

## Bring

- [ ] Sony cinema camera, with 2+ charged batteries
- [ ] Sigma 28-70 and your **variable ND**. The agent can't turn the ND, but it will tell you when you need more or less.
- [ ] A memory card for tonight. A separate card is best; otherwise note the first clip number.
- [ ] Tripod
- [ ] **USB-C data cable**, the one from Oct 19
- [ ] MacBook, charged, plus its charger (or a power bank if there's no outlet)
- [ ] iPhone for the hotspot, charged, plus a cable
- [ ] Something to rest the Mac on, in shade (sun on the screen makes the dashboard hard to read)
- [ ] A card or phone screen that says **REHEARSAL**, to hold in front of the lens at the start of each clip

## Before you leave

- [x] The website's private link is down ("done testing", 2026-10-20), so it uses no hotspot data.
- [ ] If the robot is training on this Mac, pause it for the shoot, so the agent gets the CPU.
- [ ] Keep the Mac's lid **open** at the location. If it closes, the Mac sleeps and the agent stops. The camera keeps its last settings, so that's safe, just not useful.

## At the location, step by step

1. **Camera.** Tripod, lens, card in. Frame the shot where you'll stand for the face parts, with the sunset light on you. Focus by hand.
2. **Camera settings**, as you shoot normally (S-Log3, 23.98p, your codec), plus:
   - Movie mode **M**, ISO, iris and shutter all on **manual**, as on Oct 19.
   - **WB on Color Temp** (for example 5600K), not AWB, so the agent can adjust it and it can't drift on its own.
   - **USB Connection Mode = Remote Shoot/Trn.** (already set from before).
   - **No phone app connected** to the camera.
   - ND set to something sensible for now. The agent will say if it needs changing.
3. **Plug the USB-C cable** from the camera into the Mac. If the camera asks, choose **Remote Shoot/Trn.**
4. **Run the one command** in Terminal:
   ```
   ~/camera-agent/tools/rehearsal.sh
   ```
   It shows the bridge's answer (**Connected to ILME-FX2** and **REHEARSAL SWITCH ON**), then asks you to type **LIVE**. The dashboard opens at http://127.0.0.1:8770/.
5. **Dashboard:** check that the chips say **Rehearsal** and **Rec switch on: ISO, iris, shutter, WB**. Auto starts **off**: press **Auto**.
6. If it says the bridge didn't connect: check the cable, USB Connection Mode, and that no phone app is connected, then run the command again.
7. **Say "camera ready"** to your coding assistant. From then on it watches the logs (read-only) and logs anything it sees.
8. **Face test:** when you're in frame and your face looks right on the dashboard, type **A** in the face box and press **This face looks right** once. That's exactly what you'll do on Saturday (the scoring finds each person's target by the name A or B). Tonight's faces are kept apart from Saturday's, so you'll do it again then.
9. **The sunset run (agent):** hold up the REHEARSAL card and **press REC yourself** (the agent never starts or stops recording). Let it run as the light falls.
   - Press **m** (or Mark on the dashboard) when the light visibly changes: sun behind a cloud, sun touching the horizon.
   - **Log problems the moment they happen:** press **x** in the Terminal window, or type in the dashboard's **Problems** box and press Log.
10. **Mini three-way comparison (one shot, two if the light allows).** Same framing, about 50 s each, back to back, and slate each one. End each take with **q**, then run the next:
    - **A, agent:** `~/camera-agent/tools/rehearsal.sh REH_cmp1_A_agent`, type LIVE, press Auto, then REC.
    - **B, camera Auto ISO:** turn the camera's Auto ISO **on**, then `~/camera-agent/tools/rehearsal.sh REH_cmp1_B_auto`. The agent only watches, and the bridge is read-only. REC, 50 s, stop, then turn Auto ISO back **off**.
    - **C, by hand:** `~/camera-agent/tools/rehearsal.sh REH_cmp1_C_manual`. Watch only; expose by hand, REC, 50 s, stop.

    For a second shot, use `cmp2` in the names.
11. **When you're done:** press **q**. The script stops the bridge too. Unplug the cable.
12. **Footage:** when you copy the card, put tonight's clips in a folder called **REHEARSAL-** plus the date: **REHEARSAL-2026-10-22**, never next to Step 7 footage. The slates mark them too.

## If something goes wrong

- **Stop the agent:** press **SPACE** in the Terminal window, or the dashboard's **Kill switch**, or unplug the USB cable. The camera keeps its last settings and is yours.
- **The internet drops:** nothing changes for the camera. The agent runs on the Mac by itself, and I catch up from the logs when you're back online.
- **Hotspot data:** the agent and dashboard use none. Only the coding assistant's messages use a little.
- **"The bridge didn't connect":** the script prints the bridge's own message. If it's "No camera found over USB", check the cable and the USB mode, then run the command again.

## Problems found tonight

*(Filled in after the shoot, ranked by how much they matter for Saturday.)*

Found before the shoot, on the fake camera:
- ~~While Auto is off, the status line flips back and forth with the suggestion.~~ **Fixed 2026-10-21:** with Auto off it now shows the suggestion steadily.
