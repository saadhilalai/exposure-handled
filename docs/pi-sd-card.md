# Putting Raspberry Pi OS on the microSD card (on your Mac)

It takes about 15 minutes. You do every step yourself: the passwords stay with you, and you never type them into chat.
Written for Raspberry Pi Imager 2.0 (2.0.12 is current). If a button's name is a little different, pick the one that
means the same thing.

**Don't plug the camera into the Pi for any of this.**

## You need
- Your microSD card (A1 or A2), plus a way to put it in the Mac: the Mac's SD slot with an adapter, or a USB-C card
  reader.
- **Everything on the card will be erased.** Copy off anything you want to keep first.
- Your home Wi-Fi name and password. They're only for setting up at the desk; the Pi makes its own network later.

## 1. Make a login key (once, about 1 minute)

A key lets the Mac log in to the Pi securely without typing a password each time.

1. Open **Terminal** (Applications → Utilities).
2. Paste this and press Return:
   ```
   ssh-keygen -t ed25519 -C "camera-pi"
   ```
3. Press **Return** to accept where it saves the key.
4. It asks for a passphrase. Type one you'll remember, or press Return twice for none.
5. You now have a public key at `~/.ssh/id_ed25519.pub`. That's the half that's safe to give the Pi. Never share the
   other file, `id_ed25519`.

## 2. Install Raspberry Pi Imager

1. Go to **raspberrypi.com/software** and download **Raspberry Pi Imager for macOS**.
2. Open the downloaded file and drag **Raspberry Pi Imager** into **Applications**.
3. Open it from Applications.
   - If macOS asks whether to open an app from the internet, click **Open**.
   - If it asks for access to removable volumes, click **Allow**.
4. Put the microSD card into the Mac.

## 3. Choose the Pi, the system and the card

1. **Device:** choose **Raspberry Pi 5**.
2. **Operating system:**
   - Choose **Raspberry Pi OS (other)**, then **Raspberry Pi OS (Legacy, 64-bit) Lite**.
   - Check that its description says **Bookworm** (Debian 12). That's the closest match to what Sony tested its SDK on.
   - **Don't** pick the top "Raspberry Pi OS (64-bit)". It has a desktop and is the newer Trixie.
3. **Storage:** choose your microSD card.
   - Check that the size matches your card (a 64 GB card shows as about 63 or 64 GB).
   - If you see your Mac's own disk or a backup drive, stop: that's the wrong one.

## 4. Customisation (the important part)

Imager offers to customise the system. Say **yes**, and fill in each tab:

| Tab | What to enter |
|---|---|
| **Hostname** | `camera-pi`. This is the Pi's name on the network: the Mac will find it as `camera-pi.local`. |
| **Localisation** | Pick your country's capital city. That sets the time zone, the keyboard and the **Wi-Fi country**. The Wi-Fi country matters: the Pi's Wi-Fi stays off without one. |
| **User** | A username, for example `director`, and a **strong password**. Write the password down somewhere safe. It's needed for admin commands on the Pi. Never put it in the repo or in chat. |
| **Wi-Fi** | Your home Wi-Fi's name and password. Imager may offer to fill them in from your Mac; that's fine. |
| **Remote access** | Turn on **Enable SSH**, then choose **public key** (not password). Imager should find `~/.ssh/id_ed25519.pub` from step 1. If it doesn't, browse to it: in the file picker, press **Cmd + Shift + .** to show the hidden `.ssh` folder. |
| **Raspberry Pi Connect** | Leave it **off**. It's Raspberry Pi's cloud remote-access service, and this project has no cloud. |

Then save.

## 5. Write the card

1. Click **Write** and confirm that the card will be erased. The Mac may ask for its own password, so Imager can write
   to the card.
2. Wait for **Writing** and then **Verifying** to finish, about 5–10 minutes. Don't pull the card out during either.
3. When Imager says it's done, it ejects the card. Take it out.

## 6. First start (at the desk)

1. **Put the card in the Pi.** The slot is on the underside, at the opposite end from the USB ports. The card's label
   faces away from the board. Push gently until it sits.
2. **Power:** plug the MacBook's USB-C charger into the Pi's USB-C power port.
   - The Pi may report limited power on this charger. That's expected, and fine for setup.
   - No screen, keyboard or camera is needed.
3. **Wait about 2 minutes.** On its first start the Pi grows its system to fill the card and restarts once by itself.
4. **Log in from the Mac.** In Terminal, using the username you chose:
   ```
   ssh director@camera-pi.local
   ```
   - The first time, it asks whether to trust the Pi. Type `yes` and press Return.
   - If you gave the key a passphrase, it asks for it now.
   - You're in when the prompt reads `director@camera-pi:~ $`.
5. **Stop there and tell your coding assistant.** The next steps are the settings in
   [step8-pi-build.md](step8-pi-build.md), part 2: the memory page size and Sony's USB setting.

## If something goes wrong

- **`camera-pi.local` isn't found:**
  - Wait another minute and try again.
  - Check the Mac is on the same Wi-Fi.
  - If it still fails, the Wi-Fi details or the Wi-Fi country may be wrong. Rewrite the card with Imager and check the
    Wi-Fi tab.
- **"Permission denied (publickey)":** SSH was set to a key, but not the one from step 1. Rewrite the card and pick
  `id_ed25519.pub` in Remote access.
- **Imager can't write, or the card doesn't show up:**
  - Try another card reader.
  - Check the card's lock switch (on the SD adapter's side) isn't on "lock".

## Moving to a new card later (no setup again)

The Pi copies itself onto the new card, so nothing is set up twice. The new card can be any size that holds the
system: it doesn't have to match the old one. The copy also splits the new card into three parts:
- **boot**;
- **system**, 16 GB unless you choose otherwise;
- **data**: sessions, logs and the kill-switch file.

That split is what lets the system part be made read-only later, so pulling the power can't corrupt it.

1. **New card into a USB card reader, and the reader into the Pi.** The Pi stays running from its current card.
2. **See which disk it is.** Log in to the Pi and run:
   ```
   sudo /opt/camera-agent/deploy/pi/clone_card.sh
   ```
   It lists the USB disks with their size and model, and changes nothing. The new card is usually `/dev/sda`.
   Check that the size matches the new card.
3. **Copy:**
   ```
   sudo /opt/camera-agent/deploy/pi/clone_card.sh /dev/sda
   ```
   - It shows the disk again and asks you to type its name (`sda`) before erasing anything.
   - It refuses the card the Pi is running from, anything that isn't on USB, and anything mounted.
   - The copy takes a few minutes.
4. **Swap the cards:**
   - Run `sudo poweroff` and wait for the green light to stop.
   - Take out the old card and put the new one in the Pi's slot.
   - Power on.
5. **Check:** log in as before. Everything is the same: the user, the key, the PIN and the services. The old card
   is untouched and works as a backup.
