"""The dashboard's PIN on the Pi: pairing a phone, and the PIN asked again to arm.

The settings file holds a salted hash of the PIN, never the PIN (make one with tools/pi_pin.py). Wrong PINs are
slowed down: after 5 in a row, nothing is accepted for 60 s, then 2 min, 4 min... up to 15 min. A paired phone
keeps a random token in a cookie; the Pi stores only a hash of it, in the data folder, so phones stay paired
across restarts. Forget every phone by deleting that file.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

ITERATIONS = 200_000
MAX_TRIES = 5
FIRST_WAIT_S, LONGEST_WAIT_S = 60.0, 900.0


def hash_pin(pin, salt=None, iterations=ITERATIONS):
    if not re.fullmatch(r"\d{6}", pin or ""):
        raise ValueError("the PIN is 6 digits")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, iterations)
    return "pbkdf2_sha256$%d$%s$%s" % (iterations, salt.hex(), digest.hex())


def pin_matches(pin, stored):
    try:
        kind, iterations, salt, digest = stored.split("$")
        if kind != "pbkdf2_sha256":
            return False
        mine = hashlib.pbkdf2_hmac("sha256", str(pin or "").encode(), bytes.fromhex(salt), int(iterations))
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(mine.hex(), digest)


def _token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class PinGuard:
    """Checks PINs (with the slow-down) and remembers paired phones."""

    def __init__(self, stored_hash, paired_file=None, clock=time.monotonic):
        self.stored, self.paired_file, self.clock = stored_hash, Path(paired_file) if paired_file else None, clock
        self.mutex = threading.Lock()
        self.fails, self.wait_s, self.blocked_until = 0, FIRST_WAIT_S, 0.0
        self.tokens = set()
        if self.paired_file and self.paired_file.exists():
            try:
                self.tokens = set(json.loads(self.paired_file.read_text()).get("tokens", []))
            except (ValueError, OSError, AttributeError):
                self.tokens = set()                   # unreadable: every phone pairs again, nothing worse

    @property
    def enabled(self):
        return bool(self.stored)

    def check(self, pin):
        """(ok, error). Counts wrong PINs; refuses everything while slowed down."""
        with self.mutex:
            now = self.clock()
            if now < self.blocked_until:
                return False, "too many wrong PINs: try again in %d s" % (self.blocked_until - now + 0.999)
            if pin_matches(pin, self.stored):
                self.fails, self.wait_s = 0, FIRST_WAIT_S
                return True, None
            self.fails += 1
            if self.fails >= MAX_TRIES:
                self.blocked_until, self.fails = now + self.wait_s, 0
                self.wait_s = min(self.wait_s * 2, LONGEST_WAIT_S)
                return False, "too many wrong PINs: try again in %d s" % (self.blocked_until - now)
            return False, "wrong PIN"

    def pair(self, pin):
        """(token or None, error). The token goes in the phone's cookie."""
        ok, error = self.check(pin)
        if not ok:
            return None, error
        token = secrets.token_urlsafe(32)
        with self.mutex:
            self.tokens.add(_token_hash(token))
            self._save()
        return token, None

    def is_paired(self, token):
        if not self.enabled:
            return True
        return bool(token) and _token_hash(token) in self.tokens

    def _save(self):
        if not self.paired_file:
            return
        self.paired_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.paired_file.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump({"tokens": sorted(self.tokens)}, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.paired_file)
        os.chmod(self.paired_file, 0o600)
