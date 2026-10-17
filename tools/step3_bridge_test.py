"""Step 3 bridge test.

Read-only part (always):
  1. Read all settings through the bridge.
  2. Ask the camera for its base ISO list (its own menu text).
  3. Measure live-view speed for N seconds.
  4. Read all settings again and compare (proves the read-only part changed nothing).

ISO test (only with --iso-test, only if every precondition passes):
  - ISO goes one step up through the safety gate, is confirmed on the camera,
    held 2 s, then restored to exactly the starting value and confirmed.
  - Live view is recorded the whole time to measure when the picture changes.
  - If anything fails after the first change, it retries the restore, then
    locks the bridge (kill switch) and tells the operator.

Usage: python3 tools/step3_bridge_test.py <session_dir> [--iso-test] [--fps-seconds 10]
"""
import argparse
import json
import statistics
import struct
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.bridge_client import BridgeClient  # noqa: E402
from agent.safety import SafetyGate, load_ranges  # noqa: E402
from agent.sony_values import describe_value, load_enums  # noqa: E402

BASE_ISO_LIST = 8  # CrDisplayStringType_Camera_Gain_BaseISO_Display
EI_GAIN_LIST = 9   # CrDisplayStringType_Video_EIGain_Display

# Settings that move on their own (battery, AF-C focus, meter, card bookkeeping).
DRIFTS_ON_ITS_OWN = {
    "BatteryRemain", "TotalBatteryRemain", "BatteryLevel", "TotalBatteryLevel", "MeteredManualLevel",
    "FocusPositionCurrentValue", "FollowFocusPositionCurrentValue", "FollowFocusPositionSetting",
    "FocalDistanceInMeter", "Focus_Magnifier_Setting", "FocusIndication",
}


def diff_settings(before, after, enums):
    rows = []
    for name in sorted(set(before) | set(after)):
        a, b = before.get(name), after.get(name)
        if a is None or b is None or a["current"] != b["current"] or a.get("current_str") != b.get("current_str"):
            rows.append({
                "setting": name,
                "before": describe_value(name, a["current"], enums) if a else None,
                "after": describe_value(name, b["current"], enums) if b else None,
                "drifts_on_its_own": name in DRIFTS_ON_ITS_OWN or name.endswith("UpdateTime"),
            })
    return rows


def pct(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(p / 100 * len(values)))]


def measure_live_view(client, seconds):
    client.lvstats(reset=True)
    records, last = [], -1
    t_end = time.monotonic() + seconds
    while time.monotonic() < t_end:
        t0 = time.monotonic()
        header, jpeg = client.frame(after=last, timeout_ms=1000)
        t1 = time.monotonic()
        if jpeg is None:
            continue
        records.append({"t": t1, "rtt_ms": (t1 - t0) * 1000, "frame_no": header["frame_no"],
                        "bytes": header["bytes"], "age_ms": header["age_ms"]})
        last = header["frame_no"]
    bridge = client.lvstats()
    times = [r["t"] for r in records]
    gaps = [(b - a) * 1000 for a, b in zip(times, times[1:])]
    skipped = sum(max(0, b["frame_no"] - a["frame_no"] - 1) for a, b in zip(records, records[1:]))
    return {
        "seconds": seconds,
        "frames_received": len(records),
        "fps_python": round((len(records) - 1) / (times[-1] - times[0]), 2) if len(records) > 1 else 0,
        "fps_bridge": round(bridge["fps"], 2),
        "interval_ms": {"median": round(statistics.median(gaps), 1), "p95": round(pct(gaps, 95), 1),
                        "max": round(max(gaps), 1)} if gaps else None,
        "frame_numbers_skipped": skipped,
        "jpeg_kb_avg": round(statistics.mean(r["bytes"] for r in records) / 1024, 1) if records else 0,
        "frame_age_ms_median": round(statistics.median(r["age_ms"] for r in records), 1) if records else None,
    }


class FrameRecorder(threading.Thread):
    """Saves every live-view frame with its arrival time (separate bridge connection)."""

    def __init__(self, out_dir, t_zero):
        super().__init__(daemon=True)
        self.out_dir, self.t_zero = Path(out_dir), t_zero
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.index, self.stop_flag = [], threading.Event()

    def run(self):
        client, last = BridgeClient(), -1
        while not self.stop_flag.is_set():
            header, jpeg = client.frame(after=last, timeout_ms=500)
            if jpeg is None:
                continue
            t_ms = (time.monotonic() - self.t_zero) * 1000
            name = "%06d.jpg" % header["frame_no"]
            (self.out_dir / name).write_bytes(jpeg)
            self.index.append({"t_ms": round(t_ms, 1), "frame_no": header["frame_no"], "file": name})
            last = header["frame_no"]
        client.close()


def mean_luma(jpg_path):
    """Average brightness (0-255) using macOS 'sips' to decode; no extra Python packages."""
    with tempfile.NamedTemporaryFile(suffix=".bmp") as tmp:
        subprocess.run(["sips", "-s", "format", "bmp", str(jpg_path), "--out", tmp.name],
                       capture_output=True, check=True)
        d = Path(tmp.name).read_bytes()
    off = struct.unpack_from("<I", d, 10)[0]
    w, h = struct.unpack_from("<ii", d, 18)
    step = struct.unpack_from("<H", d, 28)[0] // 8
    row = ((w * step) + 3) // 4 * 4
    total, n = 0.0, 0
    for y in range(0, abs(h), 4):
        base = off + y * row
        for x in range(0, w, 4):
            b, g, r = d[base + x * step], d[base + x * step + 1], d[base + x * step + 2]
            total += 0.2126 * r + 0.7152 * g + 0.0722 * b
            n += 1
    return total / n


def iso_preconditions(client, enums, ranges):
    """Return (ok, message, old_raw, up_raw). Never changes anything."""
    props = client.get("IsoSensitivity", "RecordingState")
    iso = props["IsoSensitivity"]
    old_raw = iso["current"]
    rule = ranges["IsoSensitivity"]
    if props["RecordingState"]["current"] != 0:
        return False, "camera is recording", old_raw, None
    if not iso["can_set_now"]:
        return False, "camera says ISO can't be changed right now", old_raw, None
    if old_raw >> 24 or not (rule["min_iso"] <= (old_raw & 0xFFFFFF) <= rule["max_iso"]):
        return False, "starting ISO %s is outside the approved %d-%d" % (
            describe_value("IsoSensitivity", old_raw, enums), rule["min_iso"], rule["max_iso"]), old_raw, None
    offered = sorted(v for v in (iso["set_values"] or iso["values"]) if not v >> 24)
    higher = [v for v in offered if v > old_raw]
    if not higher or higher[0] > rule["max_iso"]:
        return False, "no step up from %s stays inside the approved range" % describe_value(
            "IsoSensitivity", old_raw, enums), old_raw, None
    return True, "ok", old_raw, higher[0]


def run_iso_test(session, client, enums, ranges):
    ok, msg, old_raw, up_raw = iso_preconditions(client, enums, ranges)
    result = {"ran": False, "precondition": msg}
    if not ok:
        print("ISO test NOT run: %s. Nothing was changed." % msg)
        return result

    gate = SafetyGate(client, session / "changes.jsonl")
    t_zero = time.monotonic()
    recorder = FrameRecorder(session / "iso_frames", t_zero)
    recorder.start()
    restored = False
    up, back = {}, {}

    def stamp(reply):
        if "t_sent_monotonic" in reply:
            reply["t_ms"] = round((reply["t_sent_monotonic"] - t_zero) * 1000, 1)

    try:
        time.sleep(1.5)  # baseline frames
        up = gate.change_setting("IsoSensitivity", up_raw, "Step 3 test: ISO one step up (director-approved)")
        stamp(up)
        during = client.get("IsoSensitivity")["IsoSensitivity"]["current"]
        print("UP:   %s -> %s  ok=%s  camera now reports %s%s" % (
            describe_value("IsoSensitivity", old_raw, enums), describe_value("IsoSensitivity", up_raw, enums),
            up.get("ok"), describe_value("IsoSensitivity", during, enums),
            ("  (" + up["error"] + ")") if up.get("error") else ""))
        if during != old_raw:
            time.sleep(2.0)  # hold, so the change is visible on the camera and in live view
            for _ in range(3):
                back = gate.change_setting("IsoSensitivity", old_raw, "Step 3 test: restore ISO to starting value")
                if back.get("ok") and client.get("IsoSensitivity")["IsoSensitivity"]["current"] == old_raw:
                    restored = True
                    break
                time.sleep(0.5)
            stamp(back)
            after = client.get("IsoSensitivity")["IsoSensitivity"]["current"]
            print("BACK: %s -> %s  ok=%s  camera now reports %s" % (
                describe_value("IsoSensitivity", up_raw, enums), describe_value("IsoSensitivity", old_raw, enums),
                back.get("ok"), describe_value("IsoSensitivity", after, enums)))
            time.sleep(1.5)
        else:
            result["error"] = "ISO did not change: %s" % up.get("error", "camera still reports the old value")
    finally:
        recorder.stop_flag.set()
        recorder.join(timeout=3)
        current = client.get("IsoSensitivity")["IsoSensitivity"]["current"]
        if current != old_raw:
            gate.kill()
            print("!!! ISO is NOT back at the starting value (%s, should be %s). Bridge LOCKED. "
                  "Please set ISO on the camera by hand." % (describe_value("IsoSensitivity", current, enums),
                                                            describe_value("IsoSensitivity", old_raw, enums)))
            restored = False

    (session / "iso_frames" / "index.json").write_text(json.dumps(recorder.index, indent=1))
    result.update({
        "ran": bool(back), "restored_exactly": restored or current == old_raw,
        "before": describe_value("IsoSensitivity", old_raw, enums), "before_raw": old_raw,
        "during": describe_value("IsoSensitivity", up_raw, enums), "during_raw": up_raw,
        "after": describe_value("IsoSensitivity", current, enums), "after_raw": current,
        "up": {k: up.get(k) for k in ("ok", "t_ms", "round_trip_ms", "ms_sdk_return", "ms_first_callback", "ms_confirmed")},
        "back": {k: back.get(k) for k in ("ok", "t_ms", "round_trip_ms", "ms_sdk_return", "ms_first_callback", "ms_confirmed")},
        "frames_recorded": len(recorder.index),
    })
    return result


def image_change_timing(session, iso_result):
    """After the camera work: when did the live-view brightness actually change?"""
    index = json.loads((session / "iso_frames" / "index.json").read_text())
    for f in index:
        f["luma"] = round(mean_luma(session / "iso_frames" / f["file"]), 2)
    (session / "iso_frames" / "index.json").write_text(json.dumps(index, indent=1))
    out = {}
    for key in ("up", "back"):
        t_set = iso_result[key]["t_ms"]
        base = [f["luma"] for f in index if t_set - 1000 <= f["t_ms"] < t_set]
        later = [f for f in index if f["t_ms"] >= t_set]
        if len(base) < 3 or not later:
            out[key] = None
            continue
        mu, sd = statistics.mean(base), statistics.pstdev(base)
        threshold = max(1.0, 4 * sd)
        moved = next((f for f in later if abs(f["luma"] - mu) > threshold), None)
        settled = statistics.mean(f["luma"] for f in later[-10:]) if key == "back" else None
        out[key] = {"baseline_luma": round(mu, 2), "threshold": round(threshold, 2),
                    "first_changed_frame_ms_after_set": round(moved["t_ms"] - t_set, 1) if moved else None,
                    "luma_at_change": moved["luma"] if moved else None}
        if settled is not None:
            out[key]["luma_end"] = round(settled, 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--iso-test", action="store_true")
    ap.add_argument("--fps-seconds", type=float, default=10)
    args = ap.parse_args()
    session = Path(args.session)
    session.mkdir(parents=True, exist_ok=True)
    enums, ranges = load_enums(), load_ranges()

    client = BridgeClient()
    results = {"status": client.status()}
    print("Bridge:", json.dumps(results["status"]))

    before = client.settings()
    (session / "settings_before.json").write_text(json.dumps(before, indent=1))
    print("Read %d settings." % len(before))

    results["base_iso_list"] = client.display_strings(BASE_ISO_LIST)
    results["ei_gain_list"] = client.display_strings(EI_GAIN_LIST)
    print("Camera's base ISO list:", json.dumps(results["base_iso_list"]))
    print("Camera's EI gain list: ", json.dumps(results["ei_gain_list"]))

    results["live_view"] = measure_live_view(client, args.fps_seconds)
    print("Live view:", json.dumps(results["live_view"]))

    mid = client.settings()
    results["changes_during_read_only_part"] = diff_settings(before, mid, enums)
    print("Settings that changed during the read-only part:",
          [r["setting"] for r in results["changes_during_read_only_part"]])

    if args.iso_test:
        results["iso_test"] = run_iso_test(session, client, enums, ranges)
        after = client.settings()
        (session / "settings_after.json").write_text(json.dumps(after, indent=1))
        results["changes_after_iso_test"] = diff_settings(mid, after, enums)
        print("Settings different after the ISO test vs. before it:",
              json.dumps(results["changes_after_iso_test"]))
    client.close()

    if results.get("iso_test", {}).get("ran"):
        results["image_change"] = image_change_timing(session, results["iso_test"])
        print("Live view picture change:", json.dumps(results["image_change"]))

    (session / "step3_results.json").write_text(json.dumps(results, indent=1))
    print("Saved", session / "step3_results.json")


if __name__ == "__main__":
    main()
