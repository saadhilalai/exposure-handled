# Step 3: The bridge (C++ ↔ Python)

## How it's built

```
FX2 ──USB──> camera_bridge (C++) ──private socket file──> Python agent
              owns the Sony SDK          run/bridge.sock     agent/bridge_client.py
              live-view loop                                 agent/safety.py  (change_setting)
              allow-list + guarded_set()
```

- **`bridge/src/camera_bridge.cpp`** stays connected to the FX2.
  - A background loop copies each new live-view JPEG from Sony's buffer.
  - It answers one-line text commands with one-line JSON: `status`, `settings`, `get`, `frame`, `lvstats`, `display_strings`, `set`, `lock`, `quit`.
- **One way to change the camera (C++ side):** `guarded_set()` is the only place `SetDeviceProperty` appears, and the compiler is told to refuse that name for the rest of the file. It refuses unless:
  - the setting is on the compiled-in allow-list (Step 3: **ISO 800–12800 only**),
  - the value is in range and is one the camera currently offers,
  - the camera says the setting is changeable right now,
  - the camera is not recording,
  - the kill switch (`lock`) is off.

  It then waits for the camera to report the new value and times each stage.
- **One way to change the camera (Python side):** `SafetyGate.change_setting(name, value, reason)` checks `config/safe_ranges.json` (your ranges) a second time and refuses while recording or after the kill switch. It logs time, old value, new value, reason and timings to `changes.jsonl`.
- **Kill switch:** `SafetyGate.kill()` / bridge `lock`. Every change is refused until the bridge restarts. (The big dashboard button comes in Step 6.)
- **Live-view stream:** Python asks for "the next frame newer than the last one I have", so it never gets stale or duplicate frames, and the bridge never floods it.

## Results (2026-10-17)

| Check | Result |
|---|---|
| Settings changed since Step 2 | 17, all by the director during the shoot (ISO 12800 → 102400, shutter 1/250 → 1/160, zoom/focus, battery, new clips on card 1) |
| **FX2 base ISOs in S-Log3** | **800 and 4000**, read from the camera's own menu list ("Camera Gain BaseISO": High = ISO 4000, Low = ISO 800) |
| Live view speed | **23.9 fps** in Python (23.8 measured inside the bridge), 0 frames missed in 10 s |
| Frame interval | median 41.6 ms, 95% under 73.5 ms, worst 92.5 ms |
| Frame size | 1024×576 JPEG, about 66 KB each (about 1.6 MB/s over USB 2.0) |
| Delay bridge → Python | about 0 ms median: Python gets each frame as soon as the bridge has it |
| Read-only part changed anything? | No: 0 of 452 settings differed before vs. after (including the base-ISO request) |
| ISO test | **Not run.** Starting ISO was 102400, outside the approved 800–12800, so there's no in-range step up. The test refused itself; nothing was changed. |

Notes:
- Live view ran at **24 fps, matching the 23.98p project frame rate**, not the "up to 30 fps" in Sony's docs. Likely the camera sends live view at the recording frame rate; untested at 59.94p.
- The occasional 70-90 ms gap is a late frame from the camera, not one we dropped (frame numbers had no gaps).
- With the earlier frame at ISO 102400, brightness piled up at a hard ceiling of **221/255**. Likely the S-Log3 clip point in this preview; to confirm in Step 4.
