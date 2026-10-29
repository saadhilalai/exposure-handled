#!/bin/bash
# Install the camera agent on a Raspberry Pi 5 (Raspberry Pi OS (Legacy, 64-bit) Lite, Debian 12 "Bookworm").
# The repo must be at /opt/camera-agent. Run each step with sudo, in this order:
#
#   sudo deploy/pi/install.sh boot      the two settings Sony's SDK needs (4K memory pages, a bigger USB buffer),
#                                       then restart the Pi
#   sudo deploy/pi/install.sh sdk ZIP   unpack Sony's Linux 64bit (ARMv8) SDK zip (downloaded by you from Sony)
#                                       into the SDK folder; Sony's sample project is a zip inside that zip
#   sudo deploy/pi/install.sh app       user, folders, settings file, Python, face models, the bridge build,
#                                       the tests, the services. Needs Sony's Linux SDK on the Pi first.
#   sudo deploy/pi/install.sh pin       the dashboard's 6-digit PIN (asked twice; only a hash is stored)
#   sudo deploy/pi/install.sh hotspot   the Pi's own Wi-Fi. Do it last: after the next restart the Pi stops
#                                       joining your home Wi-Fi, so the Mac logs in by joining the Pi's network.
#
# It never starts the bridge and never touches the camera: the services start at the next power-up.
# Safe to run again: each step only changes what's missing.
set -euo pipefail

APP=/opt/camera-agent
CONF=/etc/camera-agent/config.toml
AGENT_USER=camera-agent
BOOT=/boot/firmware

say() { printf '\n== %s\n' "$*"; }
die() { printf '\nSTOPPED: %s\n' "$*" >&2; exit 1; }

need_root() { [ "$(id -u)" = 0 ] || die "run it with sudo"; }
need_pi() {
    [ "$(uname -m)" = aarch64 ] || die "this is for the Pi's 64-bit system (uname -m says $(uname -m))"
    [ -d "$APP/agent" ] || die "the repo isn't at $APP"
    grep -q bookworm /etc/os-release || echo "Note: not Bookworm. Sony tested its SDK on Debian 12 (Bookworm)."
}

# One setting from the settings file (the same reader the agent uses).
setting() {
    python3 -c "import sys; sys.path.insert(0, '$APP'); from agent.config import load; print(getattr(load('$CONF'), '$1'))"
}

step_boot() {
    need_root; need_pi
    say "Memory pages: 4K kernel (Sony's prebuilt libraries may break on the Pi 5's default 16K pages)"
    if grep -q '^kernel=kernel8.img' "$BOOT/config.txt"; then
        echo "already set"
    else
        cp -n "$BOOT/config.txt" "$BOOT/config.txt.before-camera-agent"
        printf '\n[all]\n# camera agent: 4K memory pages for Sony'"'"'s SDK\nkernel=kernel8.img\n' >> "$BOOT/config.txt"
        echo "added kernel=kernel8.img (backup: config.txt.before-camera-agent)"
    fi
    say "USB buffer: usbcore.usbfs_memory_mb=150 (Sony's required setting)"
    if grep -q 'usbcore.usbfs_memory_mb=150' "$BOOT/cmdline.txt"; then
        echo "already set"
    else
        cp -n "$BOOT/cmdline.txt" "$BOOT/cmdline.txt.before-camera-agent"
        sed -i '1 s/$/ usbcore.usbfs_memory_mb=150/' "$BOOT/cmdline.txt"
        echo "added (backup: cmdline.txt.before-camera-agent)"
    fi
    say "Done. Restart the Pi:  sudo reboot"
    echo "Then check:  getconf PAGESIZE   (must say 4096)"
    echo "             cat /sys/module/usbcore/parameters/usbfs_memory_mb   (must say 150)"
}

step_app() {
    need_root; need_pi
    [ "$(getconf PAGESIZE)" = 4096 ] || die "memory pages aren't 4K yet: run the boot step and restart"
    [ "$(cat /sys/module/usbcore/parameters/usbfs_memory_mb)" = 150 ] || die "the USB buffer isn't set yet: run the boot step and restart"

    say "System packages (Sony's list, plus Python and git)"
    apt-get update
    apt-get install -y autoconf libtool libudev-dev gcc g++ make cmake unzip libxml2-dev python3-venv git curl

    say "The agent's own user (no login, no admin rights)"
    id "$AGENT_USER" >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin "$AGENT_USER"
    usermod -aG plugdev,video "$AGENT_USER"

    say "Settings file: $CONF"
    if [ -f "$CONF" ]; then
        echo "already there (kept as it is)"
    else
        install -d -m 755 /etc/camera-agent
        install -m 640 -o root -g "$AGENT_USER" "$APP/config/pi.example.toml" "$CONF"
        echo "copied from config/pi.example.toml"
    fi
    local data sdk binary
    data=$(setting data_dir); sdk=$(setting sdk_dir); binary=$(setting binary)

    say "Data folder: $data (sessions, logs, the kill-switch file)"
    install -d -m 750 -o "$AGENT_USER" -g "$AGENT_USER" "$data" "$data/sessions" "$data/state" "$data/logs"

    say "Sony's SDK: $sdk"
    if [ ! -f "$sdk/RemoteCli/app/CRSDK/CameraRemote_SDK.h" ]; then
        die "Sony's SDK isn't there yet. Download the Camera Remote SDK for Linux 64bit (ARMv8) from Sony's site
(you accept Sony's licence there), copy the zip to the Pi, then:  sudo deploy/pi/install.sh sdk <the zip>
Never put Sony's files in the repo. Then run this step again."
    fi

    say "Python (pinned versions from requirements.txt)"
    [ -x "$APP/.venv/bin/python" ] || python3 -m venv "$APP/.venv"
    "$APP/.venv/bin/pip" install --quiet -r "$APP/requirements.txt" pytest==9.1.1

    say "Face models (checked against their known checksums)"
    if [ -f "$APP/models/face_detection_yunet_2023mar.onnx" ] && [ -f "$APP/models/face_recognition_sface_2021dec.onnx" ]; then
        echo "already there"
    else
        sh "$APP/tools/fetch_models.sh"
    fi

    say "Building the bridge"
    cmake -S "$APP/bridge" -B "$APP/build/bridge" -DCMAKE_BUILD_TYPE=Release -DSONY_SDK_DIR="$sdk/RemoteCli"
    cmake --build "$APP/build/bridge" -j2
    [ -x "$binary" ] || die "the bridge built, but not where the settings file expects it: $binary"

    say "Tests (fake camera only; nothing talks to the real one)"
    (cd "$APP" && .venv/bin/python -m pytest -q) || die "some tests failed: the services were NOT installed"

    say "Services, and the two permission rules"
    install -m 644 "$APP"/deploy/pi/camera-*.service "$APP"/deploy/pi/camera-health.timer /etc/systemd/system/
    install -d -m 755 /etc/polkit-1/rules.d
    install -m 644 "$APP/deploy/pi/50-camera-agent.rules" /etc/polkit-1/rules.d/
    install -m 644 "$APP/deploy/pi/60-camera-agent.rules" /etc/udev/rules.d/
    udevadm control --reload-rules
    systemctl daemon-reload
    systemctl enable camera-bridge.service camera-agent.service camera-health.timer
    echo "enabled: they start at the next power-up (nothing was started now)"
    [ -n "$(setting pin_hash)" ] || echo "Next: sudo deploy/pi/install.sh pin   (the agent won't start without a PIN)"
}

step_sdk() {
    need_root; need_pi
    local zip=${1:-} sdk
    [ -f "$zip" ] || die "give the path to Sony's zip, e.g.  sudo deploy/pi/install.sh sdk /tmp/CrSDK_..._Linux64ARMv8.zip"
    case "$(basename "$zip")" in *Linux64ARMv8*.zip) ;; *) die "that isn't the Linux 64bit (ARMv8) SDK zip" ;; esac
    command -v unzip >/dev/null || apt-get install -y unzip
    sdk=$(setting sdk_dir)
    install -d -m 755 "$sdk"
    unzip -q -o "$zip" -d "$sdk"
    [ -f "$sdk/RemoteCli.zip" ] || die "no RemoteCli.zip inside Sony's zip: the layout changed, so check it by hand"
    install -d -m 755 "$sdk/RemoteCli"
    unzip -q -o "$sdk/RemoteCli.zip" -d "$sdk/RemoteCli"
    [ -f "$sdk/RemoteCli/app/CRSDK/CameraRemote_SDK.h" ] || die "Sony's header isn't where the build expects it"
    say "Sony's SDK unpacked into $sdk (never part of the repo)"
}

step_pin() {
    need_root; need_pi
    [ -f "$CONF" ] || die "no settings file yet: run the app step first"
    local line
    line=$("$APP/.venv/bin/python" "$APP/tools/pi_pin.py" | tail -1)
    case "$line" in pin_hash\ =\ \"pbkdf2_sha256\$*) ;; *) die "no PIN made" ;; esac
    if grep -q '^pin_hash = ' "$CONF"; then
        python3 - "$CONF" "$line" <<'PY'
import re, sys
path, line = sys.argv[1], sys.argv[2]
text = open(path).read()
open(path, "w").write(re.sub(r'(?m)^pin_hash = .*$', lambda m: line, text, count=1))
PY
    else
        die "no pin_hash line under [dashboard] in $CONF: add the line yourself:
$line"
    fi
    say "PIN saved (only its hash). Phones paired before must pair again if you changed it: sudo rm $(setting state_dir)/paired.json"
}

step_hotspot() {
    need_root; need_pi
    [ -f "$CONF" ] || die "no settings file yet: run the app step first"
    local ssid band host country pass pass2
    ssid=$(setting ssid); band=$(setting band); host=$(setting host)
    country=$(raspi-config nonint get_wifi_country 2>/dev/null || true)
    [ -n "$country" ] || die "no Wi-Fi country set (the Pi's Wi-Fi stays off without one): sudo raspi-config, Localisation Options, WLAN Country"
    if nmcli -t -f NAME connection show | grep -qx camera-hotspot; then
        echo "The hotspot is already set up (connection camera-hotspot). Nothing changed."
        return
    fi
    read -r -s -p "Wi-Fi password for '$ssid' (8+ characters): " pass; echo
    read -r -s -p "Same password again: " pass2; echo
    [ "$pass" = "$pass2" ] || die "the two passwords don't match"
    [ "${#pass}" -ge 8 ] || die "the password needs at least 8 characters"
    nmcli connection add type wifi ifname wlan0 con-name camera-hotspot autoconnect yes \
        connection.autoconnect-priority 100 ssid "$ssid" 802-11-wireless.mode ap 802-11-wireless.band "$band" \
        ipv4.method shared ipv4.addresses "$host/24" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$pass" >/dev/null
    say "Hotspot '$ssid' set up (WPA2, ${band/bg/2.4 GHz}, the Pi at $host). It comes up at the next restart."
    echo "After that, the Pi no longer joins your home Wi-Fi. To log in from the Mac: join '$ssid', then"
    echo "  ssh <your user>@$host"
    echo "On the phone: join '$ssid', open http://$host:$(setting port)/ and enter the PIN once."
}

case "${1:-}" in
    boot) step_boot ;;
    sdk) step_sdk "${2:-}" ;;
    app) step_app ;;
    pin) step_pin ;;
    hotspot) step_hotspot ;;
    *) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
