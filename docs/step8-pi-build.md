# Step 8, part 2: moving the agent onto the Pi (plan, not built)

The goal: the agent runs on a Raspberry Pi 5 on the camera rig, starts by itself on power-up, and you run it from your phone.
No laptop on set. Later goal: a product someone else can install, so it's built clean from the start.

This builds on [step8-pi-plan.md](step8-pi-plan.md) (the research and parts). **Nothing here is built yet, and nothing
connects to the camera until you say "camera ready".** Anything marked **UNVERIFIED** has to be proven on the Pi itself.

## 1. Does Sony's SDK run on the Pi 5?

**Very likely, but the Pi 5 itself isn't on Sony's tested list. One test on the first day decides it.**

- **There is a Linux ARM64 build.** Sony's current SDK is still v2.02.00, the version the Mac bridge uses. It comes in
  Linux 64-bit ARM (the Pi 5's kind), Linux 32-bit ARM and Linux x86 versions. The ARM64 download is about 180 MB.
  ([Sony's SDK page](https://support.d-imaging.sony.co.jp/app/sdk/en/index.html))
- **What Sony tested it on:** a Raspberry Pi 4 (4GB) on Debian 12 "Bookworm", and two Nvidia Jetson boards. **No Pi 5.**
  (Sony's own compatibility page, in the SDK download.)
- **Our camera is on Sony's supported list** for USB, in all three USB modes.
- **On Linux ARM, Sony's SDK only works over USB, not wireless.** That's fine: the bridge already uses USB only.
- **The licence:** an app may contain Sony's library "in an inseparable way" and be shared. Sony's files may not be
  shared on their own.
  - Whether a separate library file next to our program counts as "inseparable" is a legal question (**UNVERIFIED**).
  - So for now, nothing changes: each person downloads the SDK from Sony and accepts Sony's licence themselves.
  - The repo, and any SD card image we ever share, never contains Sony's files.
  - Before selling anything, get a lawyer's read on that one clause.

**What that means for the bridge:** the same C++ code, built for the Pi. Nothing in the bridge's logic changes:
- the same allow-list, compiled in;
- the same check that the camera reports the model we expect;
- the same ranges and the same kill switch;
- the same refusal of format, record, firmware, codec, frame rate, resolution, picture profile and media.

Only the build file gets a Linux section, the same way Sony builds its own sample for Linux:
- **Sony's library files sit next to the program** (Linux's `$ORIGIN`), instead of in the Mac's `Contents/Frameworks`.
- **Two compiler flags Sony's own build uses on Linux:** `-fsigned-char` (Sony's note: it needs this on Raspberry Pi
  OS) and `-fstack-protector-all`.
- **Sony's package list:** `autoconf libtool libudev-dev gcc g++ make cmake unzip libxml2-dev`.

## 2. The Pi's setup, before any of our code

| Setting | Why |
|---|---|
| **Raspberry Pi OS (Legacy, 64-bit) Lite**, i.e. Debian 12 "Bookworm" | It's the closest match to what Sony tested (the newer "Trixie" is Debian 13). Lite has no desktop: less to break, and nothing on the Pi grabs the camera as a photo device (likely; checked on the first day). |
| `kernel=kernel8.img` in `/boot/firmware/config.txt` | The Pi 5's default kernel uses 16K memory pages, which can break prebuilt ARM programs like Sony's. This one uses 4K pages. Check: `getconf PAGESIZE` must say `4096`. |
| `usbcore.usbfs_memory_mb=150` added to the single line in `/boot/firmware/cmdline.txt` | Sony's required USB buffer size. Check: `cat /sys/module/usbcore/parameters/usbfs_memory_mb` must say `150`. |
| A USB permission rule for Sony's vendor ID `054c` | So the bridge can open the camera without running as the all-powerful root user. **UNVERIFIED**: Sony's docs don't mention this, so it's tried on the first day. |
| Camera: **USB Connection Mode = Remote Shoot (PC Remote)**, **USB Power Supply = Off** | The first is how the SDK sees the camera. The second keeps the camera from drawing power from the Pi: it runs on its own battery. |

## 3. Moving the bridge and the brain: what changes, what stays

### Stays exactly the same
- **The bridge's code and its compiled-in allow-list.** ISO 800–12800 by default. Aperture, shutter and WB only with
  `--allow-exposure`. WB mode Auto or Color Temp only. No focus.
- **The brain, the eyes, the looks and the Python safety gate** (`agent/`). It's plain Python, OpenCV and numpy, and
  64-bit ARM versions of all of them exist.
- **Two layers have to agree.** The Python gate and the bridge each check every change. One safety function sends
  them, and every one is logged.
- **The bridge only talks on a private file-socket on the Pi itself, never on the network.** The phone never reaches the
  bridge. It only reaches the dashboard, and the dashboard asks the agent, which asks the gate, which asks the bridge.
- **The kill switch** locks the bridge: nothing changes until you hand control back. **Snapshot and restore:** the
  settings are saved at the start and offered back at the end.
- **The tests** run on the Pi as well as the Mac (`pytest`).

### Changes
1. **The build file gets a Linux section** (above).
2. **One config file** instead of fixed paths: `/etc/camera-agent/config.toml`. It holds:
   - where Sony's SDK is;
   - the data folder;
   - the dashboard address;
   - the start-up mode;
   - the hotspot name.

   On the Mac, the same defaults as today.
3. **The kill switch survives a restart. This is a new safety fix, and it matters on the Pi.**
   - Today the lock lasts until the bridge restarts.
   - On the Pi the bridge restarts by itself after a crash, so a crash could quietly undo a kill.
   - The fix: the lock is also written to the data folder. A restarted bridge reads it and stays locked until you unlock
     from the phone.
4. **After any restart, the agent comes back only suggesting, never changing.** Nothing ever arms itself.
5. **The dashboard learns to live on a network** (part 5): a pairing PIN, and the Pi's hotspot address added to its
   list of allowed addresses.
6. **Arming from the phone.** Today you type `LIVE` in Terminal. With no Terminal on set, the phone does it:
   - you enter your PIN;
   - you press **Arm**, then confirm by typing `LIVE` on the phone;
   - you press **Auto** twice, as today.
7. **Optional: a real kill button** on the Pi's pins, wired straight to the bridge's lock. It works even if the phone
   or the Wi-Fi is gone.

### How the start-up mode stays safe (needs your decision, below)
- **The bridge starts read-only at power-up.** It can read the camera and the live view and refuses every change.
- **Arming** (PIN + `LIVE` on the phone) switches it to the normal ISO-only mode. The Pi does that by restarting the
  bridge service in that one mode, through a rule that allows exactly that service and nothing else.
- **`--allow-exposure` (aperture, shutter, WB) can never be switched on from the phone.** It's a line in the config
  file, changed only from the Mac over SSH (a secure remote login), on purpose.
- **Disarm or kill:** the lock goes to the bridge at once, as today, and then the bridge drops back to read-only.

## 4. Auto-start on power-up

Services managed by systemd, the Pi's built-in service manager (files in `deploy/pi/`):

| Service | What it does | Restart rule |
|---|---|---|
| `camera-bridge` | The bridge **read-only**, started at power-up. It waits for the camera on USB and leaves it alone until it's plugged in and in Remote Shoot mode. | Tries again every 3 s while there's no camera. Comes back locked if it was locked. |
| `camera-bridge-armed` | The bridge in its normal mode. **Never started at power-up**: only the agent starts it, after the phone arms it. The two bridge services conflict, so only one ever runs. | **Never restarted armed.** If it stops, the read-only bridge takes over. |
| `camera-agent` | The agent and the dashboard, suggesting only until the phone arms it. It *wants* the bridge rather than *requiring* it, because arming stops the read-only bridge on purpose. | Restarts after a crash, always read-only. |
| `camera-health` (every minute) | One power-and-heat reading for the dashboard and the log. | |

The agent's own user may start those two bridge services and nothing else (a polkit rule), and may open Sony USB
devices (a udev rule), so nothing runs as the all-powerful root user.

Also:
- **A small power-and-heat logger** writes `vcgencmd get_throttled` and the temperature to the data folder every
  minute. The dashboard's Pi panel shows "Power OK" or a warning that the voltage dipped, with the temperature.
- **Start-up time:** expect roughly 20–40 s from power to dashboard (**UNVERIFIED**, measured on the first day).
- **Pulling the D-tap mustn't corrupt the card.**
  - The system part of the card goes **read-only** (Raspberry Pi's own "Overlay File System" switch, in `raspi-config`).
  - Logs and session snapshots go to a separate data partition on the same card.
  - Only that partition is written during a shoot, and the session logs are flushed after every change.
- **The rule for the camera is unchanged on the Pi:** the Pi never connects to the camera, and never changes a
  setting, without your go.

## 5. Your phone, over the Pi's own Wi-Fi

**Recommended: the Pi makes its own Wi-Fi network (a hotspot).** The Pi's network manager can do it, and it comes up at
every start. Your phone joins it and opens `http://10.42.0.1:8770` (the hotspot's usual address; it's bookmarked once).

- **The Wi-Fi password:** a strong WPA2 password, set on the first day.
- **The pairing PIN:** a 6-digit PIN, set in the config file on the first day. Enter it once and the phone stays paired.
  Arming asks for it again.
- **The dashboard only answers on the hotspot.** Not on any other network, and not on the internet. No cloud, no
  accounts.
- **Wi-Fi country:** the Pi's Wi-Fi stays off until a country is set. The SD card step sets it.
- **Use 2.4 GHz for the hotspot.** It's the safest choice on the Pi 5. Whether 5 GHz works as a hotspot there is
  **UNVERIFIED**.
- **Your phone loses its internet** while it's on the Pi's network. iPhones say "No Internet Connection" and stay joined.
- **At the desk:** the Mac joins the Pi's network to log in over SSH, or uses an Ethernet cable.

**The other way (not recommended): the Pi joins your phone's hotspot.**
- Your phone keeps its internet.
- But the Pi's address changes, the phone's hotspot has to be on before the Pi starts, and some phones turn their
  hotspot off when nobody uses it.

## 6. Power: the low-power warning

You're powering the Pi from the Kondor Blue D-tap to USB-C PD cable. At 5 V it gives up to **3 A**. The Pi 5 asks for
5 A, so:

- **What the Pi does on 3 A:**
  - It runs normally.
  - It limits its USB ports to **600 mA** in total.
  - It won't boot from USB, which doesn't matter because it boots from the card.
  - On a desktop it shows a "power is limited" warning. **Lite has no desktop, so there's no pop-up to see**. A message
    may still show on a connected screen at start-up; the exact wording on Lite is **UNVERIFIED**.
  - ([Raspberry Pi's power docs](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#power-supply),
    [their USB-PD whitepaper](https://pip-assets.raspberrypi.com/categories/685-app-notes-guides-whitepapers/documents/RP-009856-WP-1-USB%20Power%20delivery%20on%20Raspberry%20Pi%205.pdf))
- **The two settings:**
  - `usb_max_current_enable=1` (in `/boot/firmware/config.txt`) lets the USB ports draw up to 1.6 A instead of 600 mA.
  - `PSU_MAX_CURRENT=3000` (in the Pi's start-up chip, via `sudo rpi-eeprom-config --edit`) tells the Pi to assume a
    3 A supply instead of asking the cable.
- **My recommendation: set neither at first.**
  - 600 mA is plenty, because the camera runs on its own battery and the cable only carries data.
  - Raising the USB limit above what a 3 A supply can give is something Raspberry Pi's docs never recommend: if
    something pulls that much, the voltage drops.
  - Turn on `usb_max_current_enable=1` only if the camera won't connect at 600 mA.
- **What actually matters is voltage dips, not the warning.** On the bench, under full load, `vcgencmd get_throttled`
  must say `0x0`. `0x50000` means the voltage dipped at some point. The Power tile shows the same thing.
- **Bench-test the cable on the desk first.** Whether this exact cable gives the Pi a steady 5 V 3 A is **UNVERIFIED**.

## 7. Order of work (each step ends with a check-in)

1. **Flash the card** ([pi-sd-card.md](pi-sd-card.md)). Desk power (the MacBook charger), SSH from the Mac.
2. **Pi settings** (part 2). Check the page size and the USB buffer.
3. **You download Sony's Linux ARM64 SDK** and accept Sony's licence on Sony's site, then copy it to the Pi. It
   never goes into the repo.
4. **Build** the bridge and the read-only probe on the Pi. Run the tests on the Pi.
5. **After you say "camera ready": the read-only probe.** It reads the settings and saves one live-view frame, with no
   changes. **This is the go/no-go for the whole Pi plan.** Then `tools/bench_eyes.py`, to measure the Pi's speed.
6. **Build the Pi parts:** the config file, the kill switch that survives a restart, the PIN, arming from the phone,
   the hotspot. Each one is tested on the Mac first, with the fake camera.
7. **Auto-start services.** Pull the power on purpose ten times: it must come back read-only, locked if it was locked.
8. **The D-tap cable on the bench**, watching for voltage dips.
9. **Mount it:** cage cold shoe → SmallRig cold shoe mount → SmallRig cheese plate → 3M Dual Lock → Pi case.
10. **A field test.**

## Decided (director)

1. **Start-up:** the bridge starts read-only at power-up. It's armed from the phone with the PIN and `LIVE`.
2. **The phone drops off while armed:** the agent holds the current settings and pauses until the phone is back.
3. **Network:** the Pi makes its own Wi-Fi network.
4. **USB current:** stays at 600 mA. It's raised (`usb_max_current_enable=1`) only if the camera won't connect.
5. **Physical kill button:** later. For now the kill switch is the phone's button, or pulling the USB cable.
   - The product's case will have a button built in, so the code is ready for one.
   - Every kill goes through one path, the bridge's `lock` command over its private socket. That's what
     `tools/kill_switch.py` already does.
   - A button is then one small service: on a press, send `lock`. It needs no change to the bridge, the agent or the
     dashboard.

## Progress

- [x] **The kill switch outlives a restart.**
  - `--lock-file=PATH` on the bridge and on the fake camera: if PATH exists at start-up, they start locked.
  - `lock` writes PATH to disk before it answers. The bridge never removes it.
  - The agent refuses to start against a kill from before, and says that a restart won't clear it.
  - Tested without any camera: the flag reading and the file handling (built without Sony's SDK), the fake camera,
    and the agent.
  - Without the flag, nothing changes, so the Mac and the Step 7 tools work as before. The new bridge is built
    beside the current one (`build/bridge-next`); the Step 7 scripts still use `build/bridge`.
- [x] **One settings file** (`agent/config.py`, example `config/pi.example.toml`).
  - It holds the paths, the dashboard address, the PIN's hash and the hotspot.
  - It's strict: a misspelled name stops the agent with a clear message.
  - With no file, everything is the Mac's default.
  - The start-up mode is not a setting, and exposure can be allowed only in this file.
- [x] **Pairing with a PIN** (`agent/pin.py`, `dashboard/pair.html`, `tools/pi_pin.py`).
  - The settings file holds only a salted hash of the PIN.
  - Five wrong PINs lock pairing for 60 s, doubling up to 15 min.
  - Paired phones are remembered across restarts.
  - The kill switch works even without pairing.
  - With no PIN set, the dashboard is unchanged.
- [x] **Arming from the phone** (`agent/pi_controller.py`, `tools/pi_agent.py`).
  - **At start:** read-only, always.
  - **Arming:** PIN + `LIVE` switches the bridge to its normal mode and clears an old kill. Auto starts off.
  - **Disarm or kill:** locks the bridge, then goes back to read-only. The phone keeps seeing the picture.
  - **Failures:** a failed arm, or a kill mid-switch, ends locked and read-only. Losing the camera while armed goes
    back to read-only.
  - **Stays separate:** the Step 7 and rehearsal tools are untouched. The Pi has its own program.
- [x] **The phone drops off while armed:** after `phone_timeout_s` (5 s) with nothing from the phone, Auto goes off and
  the settings are held. When the phone is back, Auto stays off until it's pressed again.
- [x] **The Pi section of the build file**, laid out like Sony's own Linux sample. It can only be built on the Pi.
- [x] **Start-up services, the install script and the power-and-heat log** (`deploy/pi/`, `tools/pi_bridge.py`,
  `tools/pi_health.py`).
  - The install script runs in steps: `boot`, `app`, `pin`, `hotspot`.
  - It never starts the bridge: the services start at the next power-up.
  - It runs the tests on the Pi, and installs nothing if they fail.
  - On the Pi, face memory lives in the data folder.

## Left for when the Pi arrives

1. **Flash the card and log in** ([pi-sd-card.md](pi-sd-card.md)).
2. **Copy the repo to `/opt/camera-agent`**, then run `sudo deploy/pi/install.sh boot` and restart the Pi.
3. **Download Sony's Linux ARM64 SDK** from Sony's site (you accept Sony's licence there), copy the zip to the Pi,
   and run `sudo deploy/pi/install.sh sdk <the zip>`. Sony's sample project is a zip inside the zip; this step
   unpacks both.
4. **Run `sudo deploy/pi/install.sh app`, then `sudo deploy/pi/install.sh pin`.**
   - The first real build of the bridge on Linux.
   - The tests on the Pi.
   - Checks that the pinned numpy and OpenCV install there (**UNVERIFIED**).
5. **After "camera ready": the read-only probe.** This is the go/no-go for the Pi.
   - Also checks the USB permission rule (**UNVERIFIED**).
   - Then `tools/bench_eyes.py` for the real speed.
6. **A separate data partition, so the system part can go read-only.** Imager grows the system to fill the card on
   first start, so this is done on the Pi.
   - Recommended: split the card into system and data before turning on the Overlay File System.
   - The fallback is a small USB stick for data.
   - **UNVERIFIED**, worked out on the Pi.
7. **`sudo deploy/pi/install.sh hotspot`**, then a restart: the phone joins the Pi's network and pairs.
8. **Power-cut test:** pull the power on purpose ten times. It must come back read-only every time, and locked if it
   was locked.
9. **The D-tap cable on the bench**, watching the Power line on the dashboard. Then mount it on the rig and do a
   field test.

## Measured on the Pi

- **Speed per live-view frame** (`tools/bench_eyes.py` on one core, the public live-test frames, 1024×576):

  | | Mac M2 | Pi 5 |
  |---|---|---|
  | JPEG decode | 0.7 ms | 5.4 ms |
  | Eyes without faces | 7.1 ms | 18.8 ms |
  | One face detection | 13.3 ms | 41.8 ms |
  | **Average, faces every 3rd frame** | **12.2 ms** | **38.2 ms** |

  - **What it means:** it fits the 41.7 ms budget at 24 fps, but only just (the estimate was ~33 ms).
  - **Room to spare:** the Pi has 4 cores, so face detection can move to its own core. The brain only decides a few
    times a second, so every other frame would also be enough.
  - **Still to measure:** the 4-core run, on a proper supply (see power).
- **Power:**
  - On a MacBook charger through a USB-C dock, the Pi flagged a voltage dip at every start.
  - Plugged straight into the same charger, it still idled at about 4.9 V (the Pi 5 wants 5.1 V).
  - **Confirmed:** under the 4-core test the Pi switched itself off within a second (red light), twice. The last
    reading was 4.79 V and 40 °C, so it's power, not heat. The one-core test runs fine on it.
  - **Fix:** Raspberry Pi's 27W USB-C supply (5.1 V, 5 A) for the bench, and the same check on the D-tap cable.
    Until then: light loads only, and nothing armed.
- **Sony's Linux download:** Sony's sample project is a zip inside the SDK zip. The `install.sh sdk` step handles it.
- **The read-only probe on the Pi passed: the go/no-go is a go.**
  - Sony's Linux SDK finds the camera over USB and connects; 452 settings were read twice with 0 differences; one
    live-view frame was saved (1024×576, as on the Mac).
  - It ran as the agent's own user, so the USB permission rule works.
  - With the camera plugged in, the Pi's idle voltage on the bench charger fell from about 4.95 V to 4.8 V, with a
    brief low-voltage flag. Another reason for the 27W supply.
- **5 minutes live, read-only, on one core each for the agent and the bridge** (the bench charger, camera on USB):
  - 19.6 frames a second (median; lowest 15), the eyes 23 ms a frame. It kept up the whole time.
  - It stayed on, but the voltage fell to 4.63 V and the Pi flagged low power, slowing itself, 112 of 306 seconds.
    Up to 50.5 °C.
  - Light was added mid-run: the scene went from 8.4 stops under to about 4.2 under within one 10-second check.
    The suggestion stayed one small ISO step up (nothing changes in read-only, so it keeps offering the first step).
  - That run was powered from the MacBook's own USB-C port. The same run on the MacBook charger in the wall did
    worse: median 4.67 V (vs 4.78), lowest 4.53 V (vs 4.63), low power 87% of the time (vs 37%). The Pi slowed
    itself so much that it fell to 14 frames a second (eyes 35 ms). Neither is a supply for the field.
- **The Wi-Fi chip can run its own network** (access-point mode), NetworkManager 1.42, Wi-Fi country set.
