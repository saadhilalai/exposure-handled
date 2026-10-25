# Step 2: First connection (read-only)

Date: 2026-10-17. Camera: Sony cinema camera, firmware 1.01, USB (Remote Shoot/Trn.). Mac: macOS 27.0, Apple Silicon. SDK 2.02.00.

## What we built

- **`bridge/src/probe_readonly.cpp`**: our own C++ program, written from scratch. It finds the camera, connects, reads every setting, saves one live-view frame, reads every setting again, compares the two reads, and disconnects.
- **It cannot change the camera:**
  - Sony's change functions (`SetDeviceProperty`, `SendCommand`, `ExecuteControlCode…`, settings-file upload, LUT import, clock, FTP…) are "poisoned", so the build fails if the code mentions them. Tested: a test file that calls `SetDeviceProperty` is refused by the compiler.
  - The finished program imports only these 11 Sony functions: `Init, EnumCameraObjects, Connect, GetDeviceProperties, ReleaseDeviceProperties, GetLiveViewImageInfo, GetLiveViewImage, GetSDKVersion, Disconnect, ReleaseDevice, Release` (checked with `nm`).
  - It refuses to run unless exactly one Sony cinema camera is connected.
- **`agent/sony_values.py`**: decodes Sony's raw numbers (f-number, shutter, angle, ISO, Kelvin, and 37 list-type settings). Value names are read from the developer's own SDK header.
- **`tools/show_settings.py`**: prints the snapshot as tables and saves `settings_table.md`.

Run: `cd build/bridge && ./probe_readonly <session folder>`, then `python3 tools/show_settings.py <session folder>`.

## Results

| Check | Result |
|---|---|
| Camera found over USB | ✅ Sony cinema camera (USB link at 480 Mb/s, i.e. USB 2.0 speed) |
| Connected | ✅ first try, protocol version 300 |
| Settings read | ✅ 452 settings |
| Changed anything? | ✅ No. Two full reads before and after the live-view grab were identical (0 differences). |
| Live view frame | ✅ saved, 1024×576 JPEG, 40 KB, first attempt |
| Live view content | ✅ First grab was black (cap on / no lens reported). With the Sigma mounted and uncapped: a real picture. |
| Lens recognized | ✅ "28-70mm F2.8 DG DN \| Contemporary 021". Iris changeable (f/2.8 to f/22, 19 stops in 1/3 steps); focus changeable (AF-C/MF, near/far, absolute position). |
| S-Log3 live view check | ✅ **Live view over USB shows the log image whether Display LUT is On or Off** (see below). |
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

### S-Log3 and the Display LUT (tested)

Setup:
- Log mode Flexible ISO, S-Gamut3.Cine, ISO 12800, 1/250, f/2.8
- Same framing for both grabs; the director switched only Display LUT on the camera
- The camera confirmed the switch (`MonitorLUTSetting` ON, then OFF)
- The only other change was a small AF-C focus shift

| 8-bit luma | LUT On | LUT Off |
|---|---|---|
| darkest 0.5% | 12 | 11 |
| median | 44 | 43 |
| 95% / 99.5% | 78 / 84 | 77 / 85 |

**Conclusion:** the USB live-view JPEG is not affected by Display LUT. The agent always sees the flat log image in log mode, so:

- **Good:** the agent's input doesn't depend on how you set your monitor.
- **Rule for Step 4:** in log mode, judge exposure in S-Log3 terms, never by "it looks dark". The log mode is read from `MovieShootingMode` / `PictureProfile_Gamma`.
- **Open (Step 4):** exactly how Sony maps S-Log3 into the 8-bit JPEG. The deepest shadows sat at about 11/255. That **likely** means legal-range S-Log3 (black = code 95 of 1023) stretched to 0-255, which would put 18% grey near 104/255 and 90% white near 155/255. To be confirmed with a grey card.

### Things we learned

1. **Live view info vs. real size.** The SDK's "image info" said 640×360, but the JPEG is really 1024×576 (Live View Quality = High). We trust the JPEG itself.
2. **Changeable right now depends on mode.** In P/A/S/M mode, iris/shutter/ISO auto-manual switches report "not now"; they only apply in Flexible Exp. Mode. F-number is display-only (no electronic lens reported).
3. **More settings are writable than expected:** the clock, deleting user Base Looks, FTP, media slot. **Decision for Step 3:** the C++ bridge uses an **allow-list**, so only director-approved settings can ever be set, and everything else is refused.
4. **Decoder bug found and fixed:** Extended Shutter Speed uses 32+32-bit packing, not 16+16.
5. **Sony's sample app needed a compiler flag** to build with Apple clang 21 (`-Wno-error=return-mismatch`). We didn't edit Sony's files and never ran the sample against the camera.
