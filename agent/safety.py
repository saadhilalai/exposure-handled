"""The one function every camera change goes through.

change_setting() checks the director's approved ranges, refuses while the
camera is recording or after the kill switch, asks the bridge to make the
change (the bridge checks again with its own compiled-in allow-list), and
logs time, old value, new value, reason and timings to changes.jsonl.

Two exceptions, each off by default: with iso_while_recording on (Step 7 agent takes), ISO and nothing else
may change while recording; with exposure_while_recording on (rehearsal shoots only, director's decision),
every approved exposure setting may.

The exposure switch (exposure=True, off by default; approved by the director): aperture,
shutter and white balance may change too, inside their ranges. Without it, only ISO.
"""
import json
import time
from datetime import datetime
from pathlib import Path

from agent.sony_values import describe_value, load_enums

RANGES_FILE = Path(__file__).resolve().parent.parent / "config" / "safe_ranges.json"
NOT_RECORDING = 0  # CrMovie_Recording_State_Not_Recording


def load_ranges(path=RANGES_FILE):
    return json.loads(Path(path).read_text())["settings"]


def within_range(name, raw, rule):
    """Python-side range check, in human units."""
    if name == "IsoSensitivity":
        if raw >> 24:  # mode/extension flags (e.g. ISO AUTO) are never allowed
            return False
        iso = raw & 0xFFFFFF
        return rule["min_iso"] <= iso <= rule["max_iso"]
    if name == "FNumber":
        return round(rule["min_f"] * 100) <= raw <= round(rule["max_f"] * 100)
    if name == "ShutterSpeed":
        num, den = (raw >> 16) & 0xFFFF, raw & 0xFFFF       # packed numerator / denominator
        fastest, slowest = round(1 / rule["min_seconds"]), round(1 / rule["max_seconds"])   # 100, 48
        return not raw >> 32 and num >= 1 and num * slowest <= den <= num * fastest
    if name == "Colortemp":
        return rule["min_k"] <= raw <= rule["max_k"]
    if name == "WhiteBalance":
        return raw in rule["modes_raw"]
    return False  # nothing else has an approved range


class SafetyGate:
    def __init__(self, client, log_path, ranges=None, iso_while_recording=False, exposure=False,
                 exposure_while_recording=False):
        self.client = client
        self.iso_while_recording = iso_while_recording   # Step 7 agent takes only; off by default
        self.exposure_while_recording = exposure_while_recording and exposure   # rehearsals only; off by default
        self.exposure = exposure                         # aperture / shutter / WB too; off by default
        self.log_path = Path(log_path)
        self.ranges = ranges if ranges is not None else load_ranges()
        self.enums = load_enums()
        self.killed = False

    def _log(self, entry):
        entry = {"time": datetime.now().isoformat(timespec="milliseconds"), **entry}
        with self.log_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    def _refuse(self, name, raw, reason, why):
        self._log({"event": "refused", "setting": name, "new_raw": raw,
                   "new": describe_value(name, raw, self.enums), "reason": reason, "refused_because": why})
        return {"ok": False, "refused": True, "error": why}

    def kill(self, client=None, why="kill switch"):
        """Kill switch: stop all changes now and hand control back to the operator.
        `client`: a second bridge connection, so the lock gets through even while a change is in flight."""
        self.killed = True
        try:
            reply = (client or self.client).lock()
        except Exception as e:  # bridge gone: nothing can change the camera anyway
            reply = {"ok": False, "error": str(e)}
        self._log({"event": "kill_switch", "why": why, "bridge_locked": reply.get("locked", False)})
        return reply

    def change_setting(self, name, raw, reason):
        """The only way the agent changes the camera. `reason` is the one-line explanation."""
        if self.killed:
            return self._refuse(name, raw, reason, "kill switch is on")
        rule = self.ranges.get(name)
        if not rule or not rule.get("change_allowed"):
            return self._refuse(name, raw, reason, "not approved for changes")
        if rule.get("switch") == "allow_exposure" and not self.exposure:
            return self._refuse(name, raw, reason, "only ISO may change (exposure switch is off)")
        if not within_range(name, raw, rule):
            return self._refuse(name, raw, reason, "outside the approved range")

        before = self.client.get(name, "RecordingState")
        recording = before["RecordingState"]["current"] != NOT_RECORDING
        iso_ok = self.iso_while_recording and name == "IsoSensitivity"
        if recording and not iso_ok and not self.exposure_while_recording:
            return self._refuse(name, raw, reason, "camera is recording")
        old_raw = before[name]["current"]

        t0 = time.monotonic()
        reply = self.client._set_raw(name, raw)
        round_trip_ms = (time.monotonic() - t0) * 1000

        entry = {"event": "change", "setting": name, "reason": reason,
                 "old_raw": old_raw, "old": describe_value(name, old_raw, self.enums),
                 "new_raw": raw, "new": describe_value(name, raw, self.enums),
                 "ok": reply.get("ok", False), "round_trip_ms": round(round_trip_ms, 1), "while_recording": recording}
        for key in ("confirmed", "camera_reports", "ms_sdk_return", "ms_first_callback", "ms_confirmed", "error", "refused"):
            if key in reply:
                entry[key] = reply[key]
        self._log(entry)
        reply["round_trip_ms"] = round_trip_ms
        reply["t_sent_monotonic"] = t0
        return reply
