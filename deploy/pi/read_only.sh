#!/bin/bash
# Make the Pi's system part read-only, so pulling the power can't damage it. Changes to the system then go to
# memory and vanish at the next start; the data part (/data: sessions, logs, the kill-switch file, paired
# phones) stays writable, and so does the boot part (for the home-wifi rescue file).
#
#   sudo deploy/pi/read_only.sh             shows the state, changes nothing
#   sudo deploy/pi/read_only.sh prepare     installs the tool it needs (overlayroot) while there's internet:
#                                           do this on home Wi-Fi, before the Pi has its own network
#   sudo deploy/pi/read_only.sh on          read-only from the next start (needs the separate data part)
#   sudo deploy/pi/read_only.sh off         writable again from the next start (to update code or settings)
#
# It uses Debian's overlayroot, as raspi-config does, but with recurse=0: raspi-config's own setting would make
# /data read-only too, and its "off" wouldn't recognise this one.
set -euo pipefail

CMDLINE=/boot/firmware/cmdline.txt
PARAM="overlayroot=tmpfs:recurse=0"

say() { printf '\n== %s\n' "$*"; }
die() { printf '\nSTOPPED: %s\n' "$*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "run it with sudo"

now() { grep -q "overlayroot=tmpfs" /proc/cmdline && echo "read-only" || echo "writable"; }
next() { grep -q "overlayroot=tmpfs" "$CMDLINE" && echo "read-only" || echo "writable"; }
data_part() { findmnt -no SOURCE /data 2>/dev/null || true; }

status() {
    echo "System part: $(now) now, $(next) from the next start."
    if [ -n "$(data_part)" ]; then
        echo "Data part:   $(data_part) on /data, $(findmnt -no OPTIONS /data | cut -d, -f1)"
    else
        echo "Data part:   none yet (/data is on the system part: copy the card first, clone_card.sh)"
    fi
    echo "Boot part:   $(findmnt -no OPTIONS /boot/firmware | cut -d, -f1)"
    dpkg -s overlayroot >/dev/null 2>&1 && echo "overlayroot: installed" || echo "overlayroot: not installed (prepare)"
}

case "${1:-}" in
    "")
        status ;;
    prepare)
        say "Installing overlayroot (only installs it: nothing is read-only until 'on' and a restart)"
        dpkg -s overlayroot >/dev/null 2>&1 || apt-get install -y overlayroot
        grep -q overlayroot "$CMDLINE" && die "the start-up line already mentions overlayroot: check it by hand"
        sync
        status ;;
    on)
        dpkg -s overlayroot >/dev/null 2>&1 || die "overlayroot isn't installed: run 'prepare' on home Wi-Fi first"
        [ -n "$(data_part)" ] || die "/data isn't its own part yet, so it would go read-only too: copy the card first"
        [ "$(findmnt -no OPTIONS /data | cut -d, -f1)" = rw ] || die "/data isn't writable now: look at it first"
        if grep -q "overlayroot=" "$CMDLINE"; then
            grep -q "$PARAM" "$CMDLINE" || die "the start-up line has a different overlayroot setting: check it by hand"
            echo "Already on from the next start."
        else
            cp -n "$CMDLINE" "$CMDLINE.before-read-only"
            sed -i "1 s/^/$PARAM /" "$CMDLINE"
            sync
            say "Read-only from the next start (backup: cmdline.txt.before-read-only). Restart: sudo reboot"
        fi
        echo "After the restart, check:  sudo deploy/pi/read_only.sh   (it should say read-only now)" ;;
    off)
        if grep -q "overlayroot=" "$CMDLINE"; then
            sed -i "1 s/overlayroot=[^ ]* \{0,1\}//" "$CMDLINE"
            sync
            say "Writable again from the next start. Restart: sudo reboot"
            echo "Afterwards, to go back to read-only:  sudo deploy/pi/read_only.sh on, then restart"
        else
            echo "It isn't set to read-only."
        fi ;;
    *)
        sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
