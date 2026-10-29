#!/bin/bash
# Send this Mac's code to the Pi, and check that every file arrived whole. Run it on the Mac.
#
#   tools/pi_send_code.sh             check the Pi's files, bring the Pi up to this Mac's commit, check again
#   tools/pi_send_code.sh --check     only check (changes nothing)
#   tools/pi_send_code.sh --restore   put back any file that doesn't match, from the Pi's own git copy
#                                     (the damaged version is kept first, in /data/camera-agent/restored/)
#
# The Pi is $PI: director@camera-pi.local by default; on the Pi's own Wi-Fi, PI=director@10.42.0.1.
# Each file is checked by its git checksum against this Mac's copy of the commit, not against the Pi's own
# records, so a file emptied by a power cut shows up. Everything written is flushed to the card (sync) at once.
set -euo pipefail

PI=${PI:-director@camera-pi.local}
APP=${PI_APP:-/opt/camera-agent}             # PI=local, PI_APP, PI_SAVED, PI_SUDO= : the tests' stand-in Pi
SAVED=${PI_SAVED:-/data/camera-agent/restored}
SUDO=${PI_SUDO-sudo}
MODE=${1:-send}

say() { printf '\n== %s\n' "$*"; }
die() { printf '\nSTOPPED: %s\n' "$*" >&2; exit 1; }
on_pi() {
    if [ "$PI" = local ]; then bash -c "$1"; else ssh -o ConnectTimeout=10 -o BatchMode=yes "$PI" "$1"; fi
}
G="$SUDO git -c safe.directory=$APP -C $APP"

case "$MODE" in send|--check|--restore) ;; *) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;; esac
cd "$(dirname "$0")/.."
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# The Pi's files that don't match commit $1, one path per line (none = all match).
mismatches() {
    git ls-tree -r "$1" | awk -F'\t' '{split($1, a, " "); print a[3] "\t" $2}' | sort > "$TMP/want"
    cut -f2 "$TMP/want" | on_pi "cd $APP && $SUDO python3 -c '
import hashlib, os, sys
for p in sys.stdin.read().splitlines():
    try:
        data = os.readlink(p).encode() if os.path.islink(p) else open(p, \"rb\").read()
        h = hashlib.sha1(b\"blob %d\\0\" % len(data) + data).hexdigest()
    except OSError:
        h = \"missing\"
    print(h + \"\\t\" + p)
'" | sort > "$TMP/got" || true
    if [ "$(wc -l < "$TMP/got")" != "$(wc -l < "$TMP/want")" ]; then
        echo "__lost_the_pi__"                       # the connection dropped: say so, don't call files damaged
        return
    fi
    comm -23 "$TMP/want" "$TMP/got" | cut -f2
}

lost() { [ "$1" != "__lost_the_pi__" ] || die "lost the connection to the Pi during the check: nothing was changed"; }

report() {    # $1 = commit, $2 = what it's checked against
    local bad n
    bad=$(mismatches "$1")
    lost "$bad"
    n=$(wc -l < "$TMP/want" | tr -d ' ')
    if [ -z "$bad" ]; then
        echo "All $n files on the Pi match $2 (${1:0:7})."
        return 0
    fi
    echo "$(echo "$bad" | wc -l | tr -d ' ') of $n files on the Pi don't match $2 (${1:0:7}):"
    echo "$bad" | sed 's/^/  /'
    return 1
}

[ "$MODE" != send ] || [ -z "$(git status --porcelain --untracked-files=no)" ] || die "this Mac has changes that aren't committed: commit first"
HEAD=$(git rev-parse HEAD)
PI_HEAD=$(on_pi "$G rev-parse HEAD") || die "can't reach the Pi at $PI"
[ "$MODE" = --check ] || ! on_pi "grep -q overlayroot=tmpfs /proc/cmdline" ||
    die "the Pi's system part is read-only, so changes would vanish at the next start.
On the Pi: sudo deploy/pi/read_only.sh off, restart, send the code, then read_only.sh on and restart"
git cat-file -e "$PI_HEAD^{commit}" 2>/dev/null || die "the Pi is on a commit this Mac doesn't have (${PI_HEAD:0:7})"

say "Checking the Pi's files against its commit"
if report "$PI_HEAD" "the Pi's commit"; then
    [ "$MODE" = --restore ] && echo "Nothing to restore."
elif [ "$MODE" = --restore ]; then
    bad=$(mismatches "$PI_HEAD")
    lost "$bad"
    stamp=$(date +%Y%m%d-%H%M%S)
    say "Keeping the damaged versions in $SAVED/$stamp/, then restoring them from the Pi's git copy"
    echo "$bad" | on_pi "cd $APP && while IFS= read -r p; do [ -e \"\$p\" ] || continue; \
        d=\"$SAVED/$stamp/\$p\"; $SUDO mkdir -p \"\${d%/*}\" && $SUDO cp \"\$p\" \"\$d\"; done && sync"
    # shellcheck disable=SC2086
    on_pi "$G checkout $PI_HEAD -- $(echo "$bad" | tr '\n' ' ') && sync"
    report "$PI_HEAD" "the Pi's commit" || die "still not matching after the restore: stop and look"
    exit 0
else
    die "fix these first:  tools/pi_send_code.sh --restore   (it keeps the damaged versions)"
fi
[ "$MODE" = send ] || exit 0

if [ "$PI_HEAD" = "$HEAD" ]; then
    echo "The Pi already has this Mac's commit."
    exit 0
fi
git merge-base --is-ancestor "$PI_HEAD" HEAD || die "the Pi's commit isn't part of this Mac's history: sort that out by hand"
say "Sending $(git rev-list --count "$PI_HEAD..HEAD") commit(s): ${PI_HEAD:0:7} -> ${HEAD:0:7}"
git bundle create -q "$TMP/code.bundle" "$PI_HEAD..HEAD"
on_pi "$SUDO tee $APP/.git/pi-code.bundle >/dev/null && sync" < "$TMP/code.bundle"
on_pi "$G fetch -q $APP/.git/pi-code.bundle HEAD && $G merge -q --ff-only FETCH_HEAD && sync && $SUDO rm -f $APP/.git/pi-code.bundle"
say "Checking every file again"
report "$HEAD" "this Mac's commit" || die "the copy didn't arrive whole: run  tools/pi_send_code.sh --restore"
