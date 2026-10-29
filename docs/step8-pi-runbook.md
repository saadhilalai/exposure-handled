# Step 8, part 3: the Pi sessions, step by step

Three sessions, in this order. Each step says who does it and what you should see. Stop at the first thing that
looks wrong.

- **Never arm except in session 2, part B.** Everything else is watch-only.
- **The camera's own settings are only ever changed by the agent while armed.**
- **The 2-core limit stays on throughout:** the agent and the bridge get one core each.

Tools used here, all in the repo:

| Tool | Runs on | What it does |
|---|---|---|
| `tools/pi_send_code.sh` | Mac | brings the Pi up to the Mac's code, then checks every file by its checksum; `--restore` repairs damaged files |
| `tools/pi_watch_test.sh` | Pi | watch-only test: voltage, low power, frames a second, time per look, heat, CPU |
| `tools/pi_power_bench.sh` | Pi | the hardest power test: all 4 cores busy, no camera use |
| `tools/pi_rehearsal.py` | Mac | the phone's controls against the fake camera; `--check` walks the first arm by itself |
| `deploy/pi/install.sh hotspot…` | Pi | the Pi's own Wi-Fi, on trial first, with a way back |
| `deploy/pi/read_only.sh` | Pi | the read-only system part, with the data part kept writable |

---

## Session 1: repair the code, test the lighter agent, the Pi's own Wi-Fi, pair the phone

**Before:** the Pi on the wall charger, the camera on and in a blue USB port, the Mac on home Wi-Fi.

### A. Repair the code and test the lighter agent

1. **You:** plug the Pi in. Wait about a minute.
2. **Repair the damaged files** (a power cut emptied 7 of them), Mac:
   ```
   tools/pi_send_code.sh --restore
   ```
   You should see "7 of … files don't match", then "All … files on the Pi match". The damaged versions are kept in
   `/data/camera-agent/restored/`.
3. **Bring the Pi up to the Mac's code**, Mac: `tools/pi_send_code.sh`. You should see: "All … files on the Pi
   match this Mac's commit".
4. **Point the test settings at the Pi's current home address**, which changes now and then. On the Pi:
   ```
   sudo sed -i "s/^host = .*/host = \"$(hostname -I | cut -d' ' -f1)\"/" /etc/camera-agent/home-test.toml
   ```
5. **The 5-minute watch-only test**, on the Pi:
   ```
   CAMERA_AGENT_CONFIG=/etc/camera-agent/home-test.toml /opt/camera-agent/tools/pi_watch_test.sh 5 light-wall
   ```
   Then compare it with the earlier runs:

   | | MacBook port, full agent | Wall charger, full agent | Wall charger, idle | **Wall charger, lighter agent** |
   |---|---|---|---|---|
   | Voltage (typical / lowest) | 4.78 / 4.63 V | 4.67 / 4.53 V | 4.87 / 4.80 V | |
   | Low power | 37% | 87% | 0% | |
   | Frames a second | about 20 | 14 | n/a | (10 expected) |
   | Time per look | 23 ms | 35 ms | n/a | |
   | Heat | 50.5 °C | 51 °C | 43.9 °C | |

   **If the Pi switches off:** stop. Note the time and the light (solid red = power), and don't retry on that
   supply.

### B. Get ready for the read-only system part (needs internet, so before the Pi's own Wi-Fi)

6. On the Pi: `sudo /opt/camera-agent/deploy/pi/read_only.sh prepare`. This only installs the tool. You should
   see "System part: writable now, writable from the next start" and "overlayroot: installed".

### C. The Pi's own Wi-Fi, on trial

7. **Set it up**, on the Pi: `sudo /opt/camera-agent/deploy/pi/install.sh hotspot`.
   - **You type the Wi-Fi password, twice.** At least 8 characters; write it down.
   - It sets up the network but doesn't switch to it. The Pi stays on home Wi-Fi.
8. **Switch on trial:** `sudo /opt/camera-agent/deploy/pi/install.sh hotspot-try`.
   - After 5 seconds the Pi leaves home Wi-Fi and the login drops. That's expected.
   - **If nothing confirms it within 10 minutes, the Pi goes back to home Wi-Fi by itself.** So does a restart.
9. **Join it from the Mac, within 10 minutes:**
   - Wi-Fi menu, pick **camera-pi**, and type the password. It has no internet; that's normal.
   - Then in Terminal:
     ```
     ssh director@10.42.0.1
     sudo /opt/camera-agent/deploy/pi/install.sh hotspot-keep
     ```
   - You should see: "Kept: the Pi now makes its own network 'camera-pi' at every start".
10. **Prove it comes back after a restart:**
    - `sudo reboot`, then wait about a minute.
    - Join camera-pi again and `ssh director@10.42.0.1`.

### D. Pair the phone (watch-only)

11. **Start the agent watch-only, with the real settings,** on the Pi:
    `/opt/camera-agent/tools/pi_watch_test.sh 10 pairing`. That gives 10 minutes to pair.
12. **On the phone:**
    - Wi-Fi, **camera-pi**, the password. If it warns "no internet", stay connected.
    - Open the browser at **http://10.42.0.1:8770/**, type the **PIN** once, and tap Pair.
    - You should see the live picture and "Watching: read-only, suggesting only", with the kill button at the bottom.
    - **Don't arm.**
13. The test's summary at the end doubles as a power reading on the Pi's own Wi-Fi. Then on the Pi: `sudo poweroff`,
    and wait for the green light to stop.

### Getting back in touch with the Pi if something goes wrong

Try these in order:

1. **During the trial (step 8–9):** do nothing for 10 minutes. The Pi goes back to home Wi-Fi by itself. Or
   unplug it and plug it back in: the trial doesn't survive a restart. Then, on home Wi-Fi:
   `ssh director@camera-pi.local`.
2. **After it's kept:**
   - Join **camera-pi** from the Mac, then `ssh director@10.42.0.1` (or `camera-pi.local`).
   - To go back to home Wi-Fi for good: `sudo /opt/camera-agent/deploy/pi/install.sh hotspot-off`.
3. **camera-pi doesn't show up:**
   - Wait 2 minutes after power-up and look at the light. Solid red means it's off: unplug it and plug it back in.
   - The network is 2.4 GHz, which every phone and Mac can see.
4. **A network cable:**
   - Plug the Pi's network port into the home router.
   - On the cable it gets a home address of its own, whatever its Wi-Fi is doing.
   - From the Mac on home Wi-Fi: `ssh director@camera-pi.local`, then `hotspot-off`.
5. **The rescue file** (you forgot the password, or nothing else works):
   - Power the Pi off, take the card out, and put it in the Mac. It shows up as **bootfs**.
   - In Terminal: `touch /Volumes/bootfs/home-wifi`, then eject the card.
   - Put the card back and power on. Within about 2 minutes the Pi is back on home Wi-Fi, and the file removes itself.
   - **Once the system part is read-only (session 3), this lasts only until the next restart.** So, once you're in:
     1. `read_only.sh off`
     2. `sudo touch /boot/firmware/home-wifi`
     3. Restart, then `hotspot-off`.
6. **Last resort:** a screen (micro-HDMI) and a USB keyboard on the Pi, then log in and `hotspot-off`.

---

## Session 2: the proper charger, then the first real arm (ISO only)

**Before:**
- Raspberry Pi's own **27W USB-C supply** (5.1 V, 5 A) into the wall and the Pi.
- The camera on its own charged battery, on a tripod, pointing at a still scene.
- **Your call, on the camera:** setting the **USB Power Supply** menu to off stops the camera drawing power from
  the Pi. Its draw lowered the Pi's voltage before.

### A. Power checks (watch-only)

1. **Power up and wait a minute**, then on the Pi:
   - `vcgencmd get_throttled` should say **0x0**: never short of power since start-up.
   - `vcgencmd pmic_read_adc EXT5V_V` should say **about 5.1 V**.
2. **The lighter agent, 5 minutes:** `/opt/camera-agent/tools/pi_watch_test.sh 5 light-27w`.
   - Pass: low power **0%**, lowest voltage at least 5.0 V.
3. **All 4 cores:** `/opt/camera-agent/tools/pi_power_bench.sh 120`. This is the test that switched the Pi off
   twice on the MacBook's supplies.
   - Pass: "Still on", and "After: throttled=0x0".
4. **If either fails:** stop. No arming on that supply.
5. **If both pass:** let the agent start by itself at power-up, read-only as always:
   `sudo systemctl enable camera-bridge camera-agent`. Session 3's power-cut test needs this.

### B. The first arm: the fake camera first, then the real one

6. **On the Mac (no Pi needed, it can run anywhere):** `python tools/pi_rehearsal.py --check`. It should say
   **"19 of 19 steps passed"**:
   - read-only at start;
   - an unpaired phone can't arm;
   - a wrong PIN, or no LIVE, is refused;
   - after arming, Auto is off until pressed;
   - Auto changes ISO only;
   - the kill switch works from any phone and survives a restart;
   - only arming clears a kill;
   - phone gone: Auto off and the settings held;
   - disarm locks it.
7. **The same by hand:** `python tools/pi_rehearsal.py`. Open the address it prints in a browser, with the PIN it
   prints. Go through the same buttons yourself, including the kill switch, until it feels automatic.
8. **The real arm, only if:**
   - part A passed;
   - the camera **isn't recording**;
   - `sudo grep allow_exposure /etc/camera-agent/config.toml` says **false** (ISO only);
   - you've written down or photographed the camera's ISO, shutter, f-stop and white balance.
9. **Start the agent:** `sudo systemctl start camera-agent`. The phone, on camera-pi, should show
   "Watching: read-only", and the ISO it shows should match the camera.
10. **Arm:** PIN and LIVE.
    - The phone says "Armed … Auto is off".
    - Nothing changes on the camera for 10 seconds.
11. **Press Auto.**
    - Make the scene a little darker or brighter (a lamp, a blind) and wait.
    - **ISO changes, on the camera's own screen and on the phone,** with a one-line reason.
    - Shutter, f-stop and white balance don't move.
12. **Kill switch** on the phone.
    - It says "locked", and the camera's ISO stays where it is.
    - Restart the agent with `sudo systemctl restart camera-agent`. It comes back **locked and read-only**. It
      never arms itself.
13. **Phone drop:**
    - Arm again (PIN and LIVE), then press Auto.
    - Turn the phone's Wi-Fi off for 10 seconds. Auto goes off and the settings are held.
    - Turn Wi-Fi back on. It says "The phone is back", and Auto stays off.
14. **Disarm.** It says "locked", back to read-only. Then:
    - Set the camera back to your noted settings by hand.
    - Copy the session to the Mac.
    - `sudo poweroff`.

**Stop rules for the real arm:**
- Anything other than ISO changes, or anything changes while not armed: press the kill switch, then stop and report.
- The kill switch doesn't lock: pull the camera's USB cable.

---

## Session 3: the new card, the read-only system part, the power-cut test

**Before:**
- A new microSD card (A2, 64 GB) in a USB card reader.
- The Pi on the 27W supply, with session 2 done (the services start at power-up).
- On the Mac: `tools/pi_send_code.sh --check`, which should say all files match.

### A. Copy the card (the old one stays untouched as the backup)

1. **The new card's reader into the Pi's free blue USB port.**
2. **See which disk it is:** `sudo /opt/camera-agent/deploy/pi/clone_card.sh`.
   - It lists the USB disks with their size and model. The new card is usually `/dev/sda`.
   - **You confirm the name and size before anything is erased.** The size should match the new card.
3. **Copy:** `sudo /opt/camera-agent/deploy/pi/clone_card.sh /dev/sda`, then type `sda` to confirm.
   - It refuses the card the Pi runs from, and anything not on USB or mounted.
   - It takes a few minutes. You should see "Done. The new card is ready."
4. **Swap:**
   - `sudo poweroff`, and wait for the green light to stop.
   - Old card out (label it **BACKUP**), new card in.
   - Power on.
5. **Check:**
   - Log in as before. Everything should be the same: the user, the key, the PIN, the Wi-Fi.
   - `findmnt /data` shows the new data part.
   - `ls /data/camera-agent/sessions | tail -3` shows the old sessions.
   - On the Mac, `tools/pi_send_code.sh --check` says all files match.

### B. The read-only system part

6. **Switch it on:** `sudo /opt/camera-agent/deploy/pi/read_only.sh on`, then `sudo reboot`.
7. **Check:** `sudo /opt/camera-agent/deploy/pi/read_only.sh` should say "System part: read-only now" and
   "Data part: … rw".
8. **Prove it:**
   - `sudo touch /etc/vanish-test /data/camera-agent/stay-test`, then `sudo reboot`.
   - Afterwards, `/etc/vanish-test` is **gone** and `/data/camera-agent/stay-test` is **still there**.
   - Delete stay-test.

### C. The power-cut test, 10 times

9. **Each round:**
   - Camera plugged in.
   - Power on and wait until the phone shows "Watching" (about a minute).
   - **Pull the power plug**, not a shutdown. Wait 10 seconds, then plug it back in.
10. **After each round, within 2 minutes:**
    - The Pi is back on its network, and the phone shows "Watching" again.
    - `sudo dmesg | grep -i -E "ext4.*error|I/O error"` prints nothing.
    - The newest session is in `/data/camera-agent/sessions`.
11. **Round 9 tests the kill switch through a power cut:**
    - Arm, then press the kill switch, then cut the power.
    - After the restart it must still say **locked**.
    - Arm again to clear it, then disarm.
12. **After round 10:**
    - On the Mac, `tools/pi_send_code.sh --check` says all files match.
    - A 5-minute `pi_watch_test.sh` run.
13. **If the Pi doesn't come back after a cut:** stop cutting. The old card is the backup.

### Changing code or settings after this

The system part is read-only, so changes would vanish at the next start. The send tool and the Wi-Fi steps refuse
while it's on.
1. `sudo /opt/camera-agent/deploy/pi/read_only.sh off`, then `sudo reboot`.
2. Make the change, for example `tools/pi_send_code.sh` from the Mac.
3. `sudo /opt/camera-agent/deploy/pi/read_only.sh on`, then `sudo reboot`.
