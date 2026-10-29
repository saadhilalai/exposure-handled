#!/bin/bash
# Copy this Pi's running system onto a new microSD card in a USB card reader, without redoing setup.
# The new card can be any size that holds the system (it doesn't have to match). In the same pass it gets three
# parts: boot, system, and a separate data partition (mounted at /data), so the system can later be made
# read-only (raspi-config's Overlay File System) while sessions, logs and the kill-switch file stay writable.
#
#   sudo deploy/pi/clone_card.sh                      lists the USB disks it could copy to, changes nothing
#   sudo deploy/pi/clone_card.sh /dev/sdX [ROOT_GB]   copies to that disk (default system size: 16 GB)
#
# It erases the target, so it shows the disk's name, size and model and asks you to type its name to confirm.
# It refuses the card the Pi is running from, any disk that isn't on USB, and any mounted disk. It uses only
# Debian's own tools (parted, mkfs, rsync). The camera services are stopped while it copies.
set -euo pipefail

say() { printf '\n== %s\n' "$*"; }
die() { printf '\nSTOPPED: %s\n' "$*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "run it with sudo"

for tool in rsync parted mkfs.vfat; do
    command -v "$tool" >/dev/null || { apt-get install -y -qq rsync parted dosfstools >/dev/null; break; }
done
SOURCE_DISK=/dev/$(lsblk -no PKNAME "$(findmnt -no SOURCE /)")
usb_disks() { lsblk -dpno NAME,SIZE,TRAN,MODEL | awk '$3 == "usb"'; }

TARGET=${1:-}
ROOT_GB=${2:-16}
if [ -z "$TARGET" ]; then
    echo "The Pi runs from: $SOURCE_DISK ($(lsblk -dno SIZE "$SOURCE_DISK"))"
    echo "USB disks it could copy to:"
    usb_disks | sed 's/^/  /' | grep . || echo "  none: put the new card in a USB card reader and plug it into the Pi"
    echo "Then: sudo $0 /dev/sdX"
    exit 0
fi

[ -b "$TARGET" ] || die "$TARGET isn't a disk"
[ "$TARGET" != "$SOURCE_DISK" ] || die "$TARGET is the card the Pi is running from"
usb_disks | awk '{print $1}' | grep -qx "$TARGET" || die "$TARGET isn't a USB disk"
! lsblk -no MOUNTPOINT "$TARGET" | grep -q . || die "$TARGET has mounted parts: unmount them first"
case "$ROOT_GB" in ''|*[!0-9]*) die "the system size is a whole number of GB" ;; esac
SIZE_B=$(lsblk -bdno SIZE "$TARGET")
USED_B=$(df -B1 --output=used / | tail -1)
[ "$((ROOT_GB * 1024 ** 3))" -gt "$((USED_B * 3 / 2))" ] || die "a ${ROOT_GB} GB system part is too small for $((USED_B / 1024 ** 3)) GB in use"
[ "$SIZE_B" -gt "$(((ROOT_GB + 2) * 1024 ** 3))" ] || die "the card is too small for a ${ROOT_GB} GB system part plus data"

say "Copy this Pi onto $TARGET"
lsblk -dno NAME,SIZE,MODEL,TRAN "$TARGET" | sed 's/^/  /'
echo "  Everything on it will be erased. New layout: boot 512 MB, system ${ROOT_GB} GB, data = the rest."
read -r -p "Type the disk's name ($(basename "$TARGET")) to confirm: " answer
[ "$answer" = "$(basename "$TARGET")" ] || die "not confirmed: nothing changed"

say "Stopping the camera services while copying"
systemctl stop camera-agent.service camera-bridge.service camera-bridge-armed.service 2>/dev/null || true

say "Partitioning"
wipefs -aq "$TARGET"
parted -s "$TARGET" mklabel msdos \
    mkpart primary fat32 4MiB 516MiB \
    mkpart primary ext4 516MiB "$((516 + ROOT_GB * 1024))MiB" \
    mkpart primary ext4 "$((516 + ROOT_GB * 1024))MiB" 100%
partprobe "$TARGET"; udevadm settle
P=$TARGET; case "$TARGET" in *[0-9]) P=${TARGET}p ;; esac
mkfs.vfat -F 32 -n bootfs "${P}1" >/dev/null
mkfs.ext4 -q -F -L rootfs "${P}2"
mkfs.ext4 -q -F -L data "${P}3"

M=$(mktemp -d /mnt/clone.XXXX)
trap 'umount -q "$M"/boot "$M"/data "$M"/root 2>/dev/null || true' EXIT
mkdir -p "$M"/root "$M"/boot "$M"/data
mount "${P}2" "$M"/root; mount "${P}1" "$M"/boot; mount "${P}3" "$M"/data

say "Copying the system (a few minutes)"
rsync -aAXH --numeric-ids --info=progress2 \
    --exclude={/proc/*,/sys/*,/dev/*,/run/*,/tmp/*,/mnt/*,/media/*,/lost+found,/boot/firmware/*,/data/*} / "$M"/root/
say "Copying the boot files"
rsync -rt --info=progress2 /boot/firmware/ "$M"/boot/
say "Copying the data (sessions, logs, the kill-switch file)"
[ -d /data ] && rsync -aAXH --numeric-ids /data/ "$M"/data/

say "Pointing the new card at its own parts"
OLD=$(blkid -s PARTUUID -o value "$(findmnt -no SOURCE /)" | sed 's/-02$//')
NEW=$(blkid -s PARTUUID -o value "${P}2" | sed 's/-02$//')
[ -n "$OLD" ] && [ -n "$NEW" ] || die "couldn't read the card IDs"
sed -i "s/PARTUUID=$OLD-/PARTUUID=$NEW-/g" "$M"/boot/cmdline.txt "$M"/root/etc/fstab
grep -q ' /data ' "$M"/root/etc/fstab || echo "PARTUUID=$NEW-03  /data  ext4  defaults,noatime  0  2" >> "$M"/root/etc/fstab
mkdir -p "$M"/root/data
grep -q "PARTUUID=$NEW-02" "$M"/boot/cmdline.txt || die "the new card's start-up file doesn't point at its system part"

sync
say "Done. The new card is ready."
echo "Next: sudo poweroff, wait for the green light to stop, swap the cards, and power on."
echo "This card stays exactly as it was, as a backup."
