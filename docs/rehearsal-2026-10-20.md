# Shakedown rehearsal: sunset, 2026-10-20

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

> The frozen Step 7 plan is **ISO only** for Saturday, with FX2 Auto ISO for the camera takes. Tonight uses all four settings, as you asked. Saturday follows the frozen plan unless you decide to change it.

## Bring

- [ ] FX2, with 2+ charged batteries
- [ ] Sigma 28-70 and your **variable ND**. The agent can't turn the ND, but it will tell you when you need more or less.
- [ ] A memory card for tonight. A separate card is best; otherwise note the first clip number.
- [ ] Tripod
- [ ] **USB-C data cable**, the one from Oct 19
- [ ] MacBook, charged, plus its charger (or a power bank if there's no outlet)
- [ ] iPhone for the hotspot, charged, plus a cable
- [ ] Something to rest the Mac on, in shade (sun on the screen makes the dashboard hard to read)
- [ ] A card or phone screen that says **REHEARSAL**, to hold in front of the lens at the start of each clip

## Before you leave

- [ ] Say **"done testing"** so I take the website link down. It saves hotspot data.
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
3. **Plug the USB-C cable** from the FX2 into the Mac. If the camera asks, choose **Remote Shoot/Trn.**
4. **Terminal window 1: the bridge.** Copy-paste:
   ```
   mkdir -p ~/camera-agent/sessions/REHEARSAL/bridge-2026-10-20
   cd ~/camera-agent/build/bridge && ./camera_bridge ~/camera-agent/run/bridge.sock ~/camera-agent/sessions/REHEARSAL/bridge-2026-10-20 --allow-exposure-while-recording
   ```
   It should say **Connected to ILME-FX2** and **REHEARSAL SWITCH ON**. Leave this window open.
5. **Terminal window 2: the agent.** Copy-paste:
   ```
   cd ~/camera-agent && caffeinate -dims .venv/bin/python tools/run_agent.py --live --rehearsal --take REH_sunset_A_agent --allow-exposure-while-recording --dashboard --port 8770
   ```
   Type `LIVE` when asked. `caffeinate` keeps the Mac awake while the agent runs.
6. **Dashboard:** open http://127.0.0.1:8770/ on the Mac. Check that the chips say **Rehearsal** and **Rec switch on: ISO, iris, shutter, WB**. Auto starts **off**: press **Auto**.
7. **Say "camera ready"** to your coding assistant. From then on it watches the logs (read-only) and logs anything it sees.
8. **Face test:** when you're in frame and your face looks right on the dashboard, press **This face looks right** once.
9. **The sunset run (agent):** hold up the REHEARSAL card and **press REC yourself** (the agent never starts or stops recording). Let it run as the light falls.
   - Press **m** (or Mark on the dashboard) when the light visibly changes: sun behind a cloud, sun touching the horizon.
   - **Log problems the moment they happen:** press **x** in window 2, or type in the dashboard's **Problems** box and press Log.
10. **Mini three-way comparison (one shot, two if the light allows).** Same framing, about 50 s each, back to back, and slate each one. To end a take, press **q** in window 2 (it offers to put your starting settings back). Then start the next with one of these:
    - **A, agent:** `cd ~/camera-agent && .venv/bin/python tools/run_agent.py --live --rehearsal --take REH_cmp1_A_agent --allow-exposure-while-recording --dashboard --port 8770`, then press Auto, then REC.
    - **B, camera Auto ISO:** turn the FX2's Auto ISO **on**, then `.venv/bin/python tools/run_agent.py --rehearsal --take REH_cmp1_B_auto --dashboard --port 8770` (no `--live`: it only watches and logs). REC, 50 s, stop. Turn Auto ISO back **off**.
    - **C, by hand:** `.venv/bin/python tools/run_agent.py --rehearsal --take REH_cmp1_C_manual --dashboard --port 8770` (watches only). Expose by hand, REC, 50 s, stop.

    The bridge stays as it is for all three. B and C never send anything to the camera.
11. **When you're done:** press **q** in window 2, then **Ctrl-C** in window 1. Unplug the cable.
12. **Footage:** when you copy the card, put tonight's clips in a folder called **REHEARSAL-2026-10-20**, never next to Step 7 footage. The slates mark them too.

## If something goes wrong

- **Stop the agent:** press **SPACE** in window 2, or the dashboard's **Kill switch**, or unplug the USB cable. The camera keeps its last settings and is yours.
- **The internet drops:** nothing changes for the camera. The agent runs on the Mac by itself, and I catch up from the logs when you're back online.
- **Hotspot data:** the agent and dashboard use none. Only the coding assistant's messages use a little.
- **The agent says the bridge isn't there:** window 1 must say "Listening on …". If it says "No camera found over USB", check the cable and the USB mode, then run step 4 again.

## Problems found tonight

*(Filled in after the shoot, ranked by how much they matter for Saturday.)*
