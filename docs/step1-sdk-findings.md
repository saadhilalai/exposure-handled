# Step 1: What Sony's SDK can and can't do (Sony cinema camera, macOS)

Source: Sony Camera Remote SDK **v2.02.00 for macOS**, its API Reference, the sample-app manual, Sony's license agreement (online), and the camera Help Guide (online).

"Confirmed in docs" means Sony's paperwork says it. "Untested" means we won't know until the camera is connected (Step 2).

---

## a. What language the SDK uses, and how Python will talk to it

**The SDK is C++.** Sony ships ready-built libraries (`libCr_Core.dylib` plus USB/network helpers) and C++ header files. You receive camera events by writing a C++ class that Sony's library calls back. The Mac libraries are "universal", meaning they contain a native Apple Silicon (arm64) version, so no slow translation layer.

**Python can't load it directly.** Python's simple loader (`ctypes`) only works with plain C functions. Sony's SDK uses C++ classes and callbacks. So we need a bridge.

| Option | What it is | Pros | Cons |
|---|---|---|---|
| **A. Small C++ helper program + Python brain (recommended)** | A tiny C++ program owns the camera connection. Python talks to it over a local socket (a private network line inside the Mac). | If the SDK crashes, Python and the kill switch keep running. A second, hard-coded safety lock lives in C++ (it can't format a card even if Python asks). The same split moves to the Pi unchanged. Python can be tested on recorded frames with no camera. Easy to explain. | A few milliseconds of extra delay per message (to be measured in Step 3). Two programs to start. |
| B. Python extension module (pybind11) | The C++ code is compiled into something Python can `import`. | Lowest delay, one program. | An SDK crash takes down the whole app, kill switch included. Sony's callbacks arrive on background threads, which makes Python threading tricky. |
| C. Someone else's open-source wrapper | A community Python wrapper. | Less code to write. | Unknown Sony cinema camera support, usually lags Sony's SDK versions, unclear license status. |

**Recommendation: A.** Safety and crash isolation matter most on a work camera.

---

## b. What the camera lets us read and change over USB

Taken from Sony's per-camera support table (the `Sony cinema camera` column). Two important notes:

1. ✔ means Sony lists the camera as supporting it. Whether a setting can be changed **at this moment** is reported live by the camera: each setting comes with a flag (changeable / display-only / not supported) and the list of allowed values. Example: F-number is display-only while the iris is set to Auto. We get the real answers in Step 2.
2. Every "Change" below goes through our one safety function, inside limits you approve.

| You asked about | Sony cinema camera over USB | Read | Change | Notes |
|---|---|---|---|---|
| ISO | ✔ | ✔ | ✔ | Plus a read-only "current ISO" that shows the real value when ISO is on Auto. |
| Gain in dB | ✘ | – | – | dB gain is FX6 only. On the camera we work in ISO. |
| ISO auto/manual | ✔ | ✔ | ✔ | Only in Flexible Exp. Mode (see below). |
| Base ISO (High/Low) | ✔ | ✔ | ✔ | "Gain Base ISO Sensitivity" = High or Low. "Base ISO Switch EI" also readable. The camera can also report the actual base ISO numbers as text. We confirm the numbers in Step 2/5, no guessing. |
| Exposure Index (Cine EI) | ✔ | ✔ | ✔ | In Cine EI, recorded ISO is locked to base ISO; EI only changes the monitoring look. That affects the brain design (Step 5). |
| Log mode (Off / Flexible ISO / Cine EI / Cine EI Quick) | ✔ | ✔ | (✔) | **We treat it as read-only** (your rule). |
| Shutter speed | ✔ | ✔ | ✔ | Sent as a fraction, e.g. 1/50. |
| Shutter angle | ✔ | ✔ | ✔ | Sent as angle × 1000 (180° = 180000). Speed/angle display mode is also readable and changeable. |
| Shutter auto/manual | ✔ | ✔ | ✔ | Flexible Exp. Mode only. |
| Anti-flicker (high-res shutter, flicker scan) | ✔ | ✔ | ✔ | Useful later for LED/fluorescent flicker. |
| Iris (F-number) | ✔ | ✔ | ✔ | Sent as f-stop × 100 (f/4 = 400). Needs an electronic lens. The Sigma 28-70 DG DN should work; untested. |
| Iris auto/manual | ✔ | ✔ | ✔ | Flexible Exp. Mode only. |
| Exposure control type (P/A/S/M vs Flexible Exp.) | ✔ | ✔ | ✔ | We'll ask you which you want the camera in. |
| White balance preset | ✔ | ✔ | ✔ | AWB, Daylight, Tungsten, Shade, Cloudy, Fluorescent, C.Temp, Custom 1-3. |
| Color temperature (Kelvin) | ✔ | ✔ | ✔ | Camera reports the allowed range and step. |
| WB tint (green/magenta) | ✘ | – | – | FX6 only. |
| AWB lock, Custom WB capture | ✔ | ✔ | ✔ | |
| Focus mode (MF / AF-S / AF-C / DMF) | ✔ | ✔ | ✔ | |
| Focus point (AF area position) | ✔ | (✔) | ✔ | Lets the agent put AF on a face. Set-only property; the current AF frame comes back with live-view "focus frame" info. |
| Face / subject recognition AF | ✔ | ✔ | ✔ | |
| Focus status ("in focus?") | ✔ | ✔ | – | Read-only. |
| Focus nudge near/far | ✔ | – | ✔ | Steps of -7 to +7. |
| Absolute focus position | ✔ | ✔ | ✔ | Sony warns the lens may not land exactly on a remembered position. Lens-dependent; untested on the Sigma. |
| Focus magnifier | ✔ | ✔ | ✔ | |
| **Internal ND** | ✘ | – | – | The camera has no internal ND (the FX6 does). The agent can't touch your variable ND, so it will tell you what to do. |
| "Manual input for ND value" | ✔ | ✔ | ✔ | Lets the camera store a typed-in ND value. Likely metadata only; untested. A possible later nicety. |
| Picture profile, gamma (S-Log3, S-Cinetone…), color mode, knee, black, detail | ✔ | ✔ | (✔) | **Read-only for us** (your rule). We read them to know if we're looking at log. |
| Creative Look, Base Look | ✔ | ✔ | (✔) | Read-only for us. |
| Display LUT / Gamma Display Assist | ✔ | ✔ | (✔) | Read-only for us. Decides what the live view looks like (see c). |
| **Zebra** | ✘ | – | – | Zebra over the SDK only works on one other Sony model, not the camera. We draw our own zebras in software, which is better anyway (we choose the level). |
| Record start/stop | ✔ | ✔ (state) | (✔) | Command "Down" = start, "Up" = stop. **We never send it unless you ask.** |
| Recording format, codec, frame rate, media | ✔ | ✔ | (✔) | **Read-only for us.** We read the frame rate to calculate 180°. |
| Live view size | ✔ | ✔ | ✔ | Low = 640 px wide, High = 1024 px wide. |
| Battery level | ✔ | ✔ | – | |

### Dangerous things the camera accepts over USB, which we will hard-block in C++

- Card format (full and quick)
- "REC settings reset" (camera settings reset)
- Pixel mapping
- LUT file import
- Uploading a settings file (overwrites settings and reboots the camera)
- APS-C/Full-frame switching
- Clock/time-zone setting and FTP settings
- Movie record start/stop (allowed only on your explicit request)

Good news: firmware update and deleting files over the SDK are **not** supported on the camera at all.

**Warning about Sony's sample app:** its interactive menu includes card format, camera settings reset, settings upload and firmware update, each a few keystrokes away. Even Sony's "simple" live-view sample changes a camera setting when it runs.

---

## c. Live view

- **Format:** one JPEG per frame (8-bit, compressed).
- **Size:** 640 px wide (Low) or 1024 px wide (High). Height follows the aspect ratio. Exact Sony cinema camera sizes untested.
- **Speed:** Sony says up to **30 fps** "if the communication speed is good", lower on a weak link. We measure the real number in Step 3.
- **How it arrives:** the SDK keeps refreshing a buffer in the background and we copy the newest frame. Grabbing a frame doesn't slow the camera.
- **Also available:** the camera's on-screen display (OSD) as a separate image. There's also a network "Monitoring" stream, but on the camera that needs Wi-Fi, so we skip it.

**S-Log3 and live view.** On the FX6 family, Sony's docs put "LiveView" in the same LUT group as the viewfinder. The camera has one Display LUT switch for every output. So **likely**:

- Display LUT **On**: live view looks like normal contrast (Rec.709-style).
- Display LUT **Off**, Gamma Display Assist Off: live view is flat, gray S-Log3.

This is untested. In Step 2 we'll read those settings and grab a frame in each state to confirm. The agent will always read picture profile, gamma, log mode, Display LUT and Gamma Display Assist first, so it knows which image it's judging and never "fixes" flat log by raising ISO. A JPEG is 8-bit and compressed, so highlight-clip readings are approximate. The plan in Step 4 will say how we handle that.

---

## d. Sony's license: what you can publish and sell (plain English, not legal advice)

Two English versions exist: a global one (Sony Corporation) and a US one (Sony Electronics Inc.). The core terms are the same.

**You may:**

- Use the SDK to build an app that controls Sony cameras and lenses.
- Ship your app with Sony's **compiled library built inside it** ("in an inseparable way").
- **Sell your app.** Sony's FAQ: "developers are free to sell their APPs for legitimate purposes."
- Publish **your own code** that calls the SDK. Nothing in the license forbids open-sourcing your own app code.

**You may not:**

- Share Sony's SDK files on their own: no libraries, headers, sample code or docs in a public repo. ("You may not share, distribute … the SOFTWARE unless expressly authorized.") → `sdk/` and the zip are in `.gitignore`, and the README tells people to download from Sony.
- Reverse-engineer, decompile or modify Sony's files.
- Imply Sony made, owns or supports your app. → README and app will say clearly that this is not a Sony product.
- Use it for weapons/military purposes (standard clause).

**If you ever distribute or sell the app to other people, you must:**

1. Before they use it, **tell them and get their consent** that controlling a camera with the app takes the camera "out of such manufacturer-warranty as separately specified by SONY". (In the global version this doesn't apply in Australia, NZ, Philippines, South Africa and Iraq.)
2. Tell them and get consent about the prohibited (weapons/military) uses.
3. Provide all customer support yourself.
4. Update your app when Sony releases SDK updates, following Sony's instructions.

**⚠️ About your own Sony cinema camera:** that warranty clause is written about end users of apps you distribute, but it shows Sony's position that SDK control may fall outside the camera's warranty "as separately specified by Sony". I haven't found or read that separate warranty wording for the camera. If this matters to you, check the camera warranty terms or ask Sony **before** Step 2.

Also: the libusb library inside Sony's package is open source (LGPL) with its own conditions. Since we don't redistribute any of Sony's files, it doesn't affect the public repo.

**For the public repo:** our own Python and C++ code, written from scratch (not copied from Sony's samples), is fine to publish. Sony's sample code stays private.

---

## e. Anything that needs Windows/Linux, or that the Mac can't do

- **Nothing we need is Windows- or Linux-only.** The Mac package has the same features. Windows needs an extra USB driver; the Mac doesn't.
- **macOS version:** Sony tested macOS 14, 15 and 26. **This Mac runs macOS 27.0, which Sony hasn't tested.** It will likely work, but it's a real risk. If the camera isn't detected, this is the first suspect.
- **Quarantine flags:** the downloaded SDK files carry macOS "quarantine" flags. Sony says to remove them with `xattr -d com.apple.quarantine <file>` on the 7 library files before running. That happens in Step 2 and only touches `~/camera-agent/sdk/`.
- **Build tools:** Sony's guide uses Xcode + CMake. This Mac has Apple's Command Line Tools but **not full Xcode, and no CMake**. Plan: `brew install cmake`, then build with CMake's normal Makefiles instead of Xcode. Likely fine; untested.
- **Python:** the system Python is 3.9.6 (old). We'll want a newer Python in a private project environment for later steps (your call when we get there).
- **Limits specific to this camera (any OS):** no wired Ethernet control (USB or Wi-Fi only), no remote firmware update, no remote file delete, no SDK zebra, no WB tint, no gain dB, no internal ND.
- **Raspberry Pi (Step 8 preview):** the Linux ARMv8 package is a **separate download** (not in this Mac zip). Sony tested a Pi 4 (Debian 12), Jetson Nano and Jetson Orin Nano. A **Pi 5 is not on Sony's tested list**. It will likely work (same CPU family), but needs checking in Step 8.

---

## Camera setup for USB control (from Sony's docs and the camera's Help Guide)

Do this once the firmware update has finished. None of it touches your recording format, codec, frame rate or picture profile.

1. **Disconnect any phone app.** The Help Guide says a computer can't control the camera while it's connected to a smartphone (Creators' App).
2. **Set the USB mode.** MENU → Setup → USB → **USB Connection Mode**. Pick either:
   - **Remote Shoot/Trn.** (always connect as a remote camera), or
   - **Sel. When Connect** (the camera asks each time; then pick **Remote Shoot/Trn.**).
   Don't pick USB Streaming, MSC or MTP.
3. **Plug in USB-C** from the camera to the MacBook. Use a data cable, not a charge-only cable.
4. On the camera, if asked, choose **Remote Shoot/Trn.**
5. **Optional, for stills only:** MENU → Network → Cnct./Remote Sht. → **Remote Shoot Setting** → Still Img. Save Dest. = **Camera Only**, so test stills never get sent to the Mac. It doesn't affect video.
6. **Leave everything else as you normally shoot.** In Step 2 we only read.

Before Step 3 (when the agent starts changing exposure) we'll decide together how the camera should be set up so the agent can drive iris, shutter and ISO. Probably MENU → Shooting → Shooting Mode → **Exposure Ctrl Type = Flexible Exp. Mode**, with iris, shutter and ISO each on **Manual**. Your call then.

Help Guide pages used: [Remote Shoot Function](https://helpguide.sony.net/ilc/2530/v1/en/contents/0903_pc_remote_function.html), [USB Connection Mode](https://helpguide.sony.net/ilc/2530/v1/en/contents/0601_usb_connection.html), [Remote Shoot Setting](https://helpguide.sony.net/ilc/2530/v1/en/contents/201h_remote_shoot_setting.html), [Exposure Ctrl Type](https://helpguide.sony.net/ilc/2530/v1/en/contents/201h_exposure_control.html), [Display LUT](https://helpguide.sony.net/ilc/2530/v1/en/contents/211h_display_lut.html), [Log shooting](https://helpguide.sony.net/ilc/2530/v1/en/contents/211h_s_log_shooting.html).
