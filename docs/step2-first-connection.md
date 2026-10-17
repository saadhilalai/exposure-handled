# Step 2: First connection (read-only)

Date: 2026-10-17. Camera: ILME-FX2, firmware 1.01, USB (Remote Shoot/Trn.). Mac: macOS 27.0, Apple Silicon. SDK 2.02.00.

## What we built

- **`bridge/src/probe_readonly.cpp`**: our own C++ program, written from scratch. It finds the FX2, connects, reads every setting, saves one live-view frame, reads every setting again, compares the two reads, and disconnects.
- **It cannot change the camera:**
  - Sony's change functions (`SetDeviceProperty`, `SendCommand`, `ExecuteControlCode…`, settings-file upload, LUT import, clock, FTP…) are "poisoned", so the build fails if the code mentions them. Tested: a test file that calls `SetDeviceProperty` is refused by the compiler.
  - The finished program imports only these 11 Sony functions: `Init, EnumCameraObjects, Connect, GetDeviceProperties, ReleaseDeviceProperties, GetLiveViewImageInfo, GetLiveViewImage, GetSDKVersion, Disconnect, ReleaseDevice, Release` (checked with `nm`).
  - It refuses to run unless exactly one ILME-FX2 is connected.
- **`agent/sony_values.py`**: decodes Sony's raw numbers (f-number, shutter, angle, ISO, Kelvin, and 37 list-type settings). Value names are read from the developer's own SDK header.
- **`tools/show_settings.py`**: prints the snapshot as tables and saves `settings_table.md`.

Run: `cd build/bridge && ./probe_readonly <session folder>`, then `python3 tools/show_settings.py <session folder>`.

## Results

| Check | Result |
|---|---|
| Camera found over USB | ✅ ILME-FX2 (USB link at 480 Mb/s, i.e. USB 2.0 speed) |
| Connected | ✅ first try, protocol version 300 |
| Settings read | ✅ 452 settings |
| Changed anything? | ✅ No. Two full reads before and after the live-view grab were identical (0 differences). |
| Live view frame | ✅ saved, 1024×576 JPEG, 40 KB, first attempt |
| Live view content | ⚠️ **Black frame** (brightness 3-16 out of 255). Camera reports no lens name and f-number "--". Likely reason: lens/body cap on, or no electronic lens mounted. |
| S-Log3 live view check | ⏸ Not possible on a black frame. Waiting for a real picture. |
| macOS 27 (untested by Sony) | ✅ Works |
| Build without full Xcode | ✅ Works (CMake + Command Line Tools) |

### Camera state at connection (starting-settings record)

- Exposure Ctrl Type: P/A/S/M, mode Movie M
- Shutter 1/250 (speed mode)
- ISO 12800
- WB AWB
- Log: Flexible ISO, S-Gamut3.Cine
- Display LUT: Off
- Picture Profile: Off
- Focus: MF (display-only)
- Frame rate: 23.98p
- Recording: XAVC S-I 4K 240M 4:2:2 10-bit
- Not recording
- Battery 3/4 on power supply

The full snapshot is in the session folder (`sessions/…/settings_start.json`), which is not committed.

### Things we learned

1. **Live view info vs. real size.** The SDK's "image info" said 640×360, but the JPEG is really 1024×576 (Live View Quality = High). We trust the JPEG itself.
2. **Changeable right now depends on mode.** In P/A/S/M mode, iris/shutter/ISO auto-manual switches report "not now"; they only apply in Flexible Exp. Mode. F-number is display-only (no electronic lens reported).
3. **More settings are writable than expected:** the clock, deleting user Base Looks, FTP, media slot. **Decision for Step 3:** the C++ bridge uses an **allow-list**, so only director-approved settings can ever be set, and everything else is refused.
4. **Decoder bug found and fixed:** Extended Shutter Speed uses 32+32-bit packing, not 16+16.
5. **Sony's sample app needed a compiler flag** to build with Apple clang 21 (`-Wno-error=return-mismatch`). We didn't edit Sony's files and never ran the sample against the camera.
