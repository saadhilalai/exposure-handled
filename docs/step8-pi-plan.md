# Step 8: Raspberry Pi 5 plan (plan only, nothing bought)

Researched after the dashboard was built (Step 6). Prices move fast (memory shortages); re-check before buying. Anything marked **UNVERIFIED** couldn't be confirmed from a reliable source. **Nothing has been bought.**

## Will Sony's SDK work on a Pi 5 with the camera?

**Probably, with two precautions. Not proven.**

- Sony ships a separate **Linux 64-bit (ARMv8)** SDK download (not in the Mac zip). Sony tested it on a **Pi 4 with Debian 12**, Jetson Nano and Jetson Orin Nano. **The Pi 5 is not on Sony's list.**
- One public project runs Sony's SDK (v2.00) on a Pi 5 (Ubuntu 24.04, in Docker) with a Sony A1. It reads camera settings over USB, with app-level bugs still open ([DPM-V2](https://github.com/unmanned-systems-uk/DPM-V2), [issue #54](https://github.com/unmanned-systems-uk/DPM-V2/issues/54)). No Sony cinema camera-on-Pi-5 report found.
- **Precaution 1, memory page size:** the Pi 5's default kernel uses 16K memory pages, which breaks some prebuilt ARM64 programs. [Raspberry Pi itself](https://www.raspberrypi.com/news/benchmarking-raspberry-pi-5/) notes the stock Geekbench 6 build fails. Sony's libraries are prebuilt, so it's a real risk (**UNVERIFIED** either way). Fix from day one: add `kernel=kernel8.img` to `/boot/firmware/config.txt`; `getconf PAGESIZE` should then say 4096. Speed cost is negligible (774 vs 764 Geekbench single-core).
- **Precaution 2, OS version:** current Raspberry Pi OS is Debian 13 "Trixie", but **Raspberry Pi OS (Legacy, 64-bit), i.e. Debian 12 "Bookworm", is still offered for the Pi 5** ([downloads](https://www.raspberrypi.com/software/operating-systems/)). Use Legacy Bookworm Lite 64-bit: closest to what Sony tested.

**What changes in our code / setup for the Pi** (small: the bridge design was chosen for this):

1. Download Sony's Linux ARMv8 SDK into `sdk/` (same license rules: never in the repo).
2. Add a Linux branch to `bridge/CMakeLists.txt`:
   - Sony's adapter libraries sit next to the program (`$ORIGIN`), not in `Contents/Frameworks`.
   - Add `-fsigned-char`, which Sony's own build uses on Raspberry Pi.
3. Sony's required USB setting: append `usbcore.usbfs_memory_mb=150` to `/boot/firmware/cmdline.txt`.
4. Likely needed: a udev rule so the bridge can open the camera without root (Sony vendor ID 054c). **UNVERIFIED** until tried.
5. Python environment: the same `requirements.txt` (numpy, OpenCV); ARM64 versions exist.
6. Start the bridge and agent automatically at boot (systemd).
7. Dashboard on your phone over the Pi's own Wi-Fi hotspot, so no screen is needed. Step 6 should be phone-friendly.
8. Nice extra for a rig: a **physical kill-switch button** on the Pi's GPIO pins that sends `lock` to the bridge.
9. **The camera plugs into a blue USB 3.0 Type-A port.** The Pi 5's USB-C port is power only.

## Power from the V-mount (D-tap, 14.4–16.8 V)

- The Pi 5 wants **5 V at 5 A** over USB-C PD. That 5 A mode is non-standard, and most D-tap/PD gear stops at 5 V 3 A.
- On 3 A the Pi still runs, but limits its USB ports to 600 mA and shows a warning ([Raspberry Pi whitepaper](https://pip-assets.raspberrypi.com/categories/685-app-notes-guides-whitepapers/documents/RP-009856-WP-1-USB%20Power%20delivery%20on%20Raspberry%20Pi%205.pdf)).
- The Pi itself draws roughly **3–10 W** (measured: 2.8 W idle, 9.7 W max).
- **Recommended:** D-tap → [Tilta P-Tap to 5.5/2.1 mm DC cable](https://tilta.com/shop/p-tap-to-5-5-2-1mm-dc-male-cable/) → [Geekworm Pi5 5V5A PD module](https://geekworm.com/products/rpi5-5v5a-pd) (9–24 V in, 5 V 5 A PD out; [wiki](https://wiki.geekworm.com/Pi5-5V5APD) shows a 5 A load test) → Pi 5. Not independently tested from a V-mount: **UNVERIFIED**, so bench-test it first.
- Alternative: [52Pi EP-0225](https://52pi.com/products/52pi-pd-power-extension-adapter-board-for-raspberry-pi-5) (a forum user runs a Pi 5 from a 12 V battery with it; its DC jack size is listed inconsistently, so check before buying an adapter).
- Simplest fallback: a D-tap → USB-C PD cable such as [Kondor Blue's 16" D-Tap to USB-C PD cable](https://kondorblue.com/products/16-d-tap-to-usb-c-9v-3a-regulated-blue-braided-straight) ($37.99). At 5 V it gives 3 A at most, so the Pi runs with the 600 mA USB limit (enough: the camera runs on its own battery).
- **Sony cinema camera tip:** set the camera's **USB Power Supply** menu so the camera doesn't try to charge from the Pi. The camera runs on its own battery.

## Is the Pi 5 fast enough? (Jetson needed?)

Measured on this Mac with `tools/bench_eyes.py` (one CPU core, real frames), then scaled by Geekbench single-core (M2 2,342 vs Pi 5 812, about 2.9× slower):

| Per live-view frame | Mac M2 (measured) | Pi 5 (estimate) |
|---|---|---|
| JPEG decode | 1.0 ms | ~3 ms |
| Eyes without faces | 6.1 ms | ~18 ms |
| One face detection (YuNet, 640×360) | 13.4 ms | ~39 ms (independent estimate from published Pi 5 numbers: ~38 ms) |
| **Average, faces every 3rd frame** | **11.6 ms** | **~33 ms**, against a 41.7 ms budget at 24 fps |

**Verdict: the Pi 5 is very likely fast enough; a Jetson is not needed.**
- One core keeps up with 24 fps.
- The Pi has 4 cores, so face detection can run on its own core.
- The brain only needs to decide a few times a second, so analyzing every other frame would also be fine.
- First job on the Pi: run `tools/bench_eyes.py` to replace this estimate with a measurement.
- The Jetson Orin Nano Super is now $399 (it was $249). It's only worth it if the Pi 5 + SDK route fails (it is on Sony's tested list).

## Parts list (US prices when researched, before shipping and tax)

| Item | Recommended | Price | Notes |
|---|---|---|---|
| Computer | [Raspberry Pi 5 4GB](https://www.pishop.us/product/raspberry-pi-5-4gb/) | $110 | Plenty for this job. 8GB is $175. Prices rose from $60 since late 2025. |
| Cooling | [Raspberry Pi Active Cooler](https://www.pishop.us/product/raspberry-pi-active-cooler/) | $10.95 | |
| Case + cage mount | [KKSB Pi 5 case (room for cooler)](https://kksb-cases.com/products/kksb-raspberry-pi-5-case-with-space-for-hats-addon-boards-and-cooler) + [1/4"-20 bracket](https://kksb-cases.com/products/kksb-14-20-unc-thread-bracket) | €21.13 + €3.90 (~$29) | Ships from Sweden. No purpose-built Pi 5 cage mount exists. |
| Rig plate | [SmallRig 4887 cheese mount plate](https://www.bhphotovideo.com/c/product/1852171-REG/smallrig_4887_multifunctional_cheese_mount_plate.html) | $12.99 | 1/4" and 3/8" threads onto your cage. NATO clamp optional. |
| Storage | Official Raspberry Pi A2 64GB microSD ([PiShop](https://www.pishop.us/product-category/raspberry-pi/sd-cards/)) | $39.95 | SSD route is $145+ and out of stock; not needed |
| Power converter | [Geekworm Pi5 5V5A PD module](https://geekworm.com/products/rpi5-5v5a-pd) | $15.50 | Gives the Pi its full 5 A |
| D-tap lead | [Tilta P-Tap to 5.5/2.1 mm DC](https://tilta.com/shop/p-tap-to-5-5-2-1mm-dc-male-cable/) | $15.00 | Matches the Geekworm jack |
| Camera cable | [Kondor Blue USB-A to right-angle USB-C, USB 3.0, 2 ft](https://kondorblue.com/products/usb-a-right-angle-to-usb-c-right-angle-high-speed-data-and-power-cable-braided-blue) | $10.99 | Bandwidth needed is only ~1.6 MB/s |
| **Core total** | | **≈ $244** | (≈ $309 with the 8GB Pi) |
| Optional: screen | Your phone (free), or [Touch Display 2 5"](https://www.raspberrypi.com/products/touch-display-2/) | $0 / $40 list ($54.95 PiShop) | Phone over Wi-Fi is the plan |
| Optional: desk power | [Raspberry Pi 27W USB-C supply](https://www.pishop.us/) | $12.95 | For bench testing before the rig |
| Optional: kill-switch button | [Adafruit 30 mm arcade button, red](https://www.adafruit.com/product/3489) (big enough to hit by feel), or the small [16 mm red pushbutton](https://www.adafruit.com/product/1445) | $2.50 / $0.95 | Plus jumper wires (a few dollars, not price-checked). The arcade button's LED needs 5 V, so wire only the switch at first |
| Not needed | Jetson Orin Nano Super | $399 | Only if the Pi 5 route fails |

## Biggest risks, in order

1. The Sony SDK on a Pi 5 is unproven, and the 16K pages need the 4K kernel. Mitigation: use the Legacy Bookworm image with `kernel8.img`, and try the SDK's sample before building anything else.
2. Power: the 5 V 5 A converter from D-tap isn't independently tested. Mitigation: bench-test it on the desk with a bench supply first.
3. Prices are volatile; re-check before buying.

## Update after the dashboard (Step 6): load, memory, RAM

Measured on the Mac with the fake camera, the agent at 24 fps **plus** a browser pulling false-color frames at about 10 fps (`tools/run_agent.py --fake --dashboard`):

| | Mac M2 (measured) | Pi 5 (estimate, ×2.9) |
|---|---|---|
| Whole runner (eyes + brain + dashboard) | 47% of one core | ~1.4 of the Pi's 4 cores |
| Memory (runner) | 110 MB (+~40 MB once a face signature model is loaded) | about the same |
| False color for the browser | 4.9 ms per frame (was 23.4 ms; now a lookup table, same picture) | ~14 ms |
| Zebras for the browser | 4.8 ms (was 7.6 ms) | ~14 ms |
| Face signature ("this face looks right"), once per second per face | 5.9 ms | ~17 ms |
| Clean view | 0 ms (passes the camera's own JPEG through) | 0 ms |

**RAM: 4GB (director's decision).** The agent uses ~150 MB.

## Phone access (the dashboard on the rig)

- Plan: the Pi makes its own Wi-Fi hotspot, and your phone opens the dashboard. No laptop, no screen.
- **Before that's safe, two things are needed:** a WPA2 password on the hotspot, and a **password on the dashboard** (not built yet). Today the dashboard only listens on the computer it runs on, and its buttons are protected against other websites but not against other people on the same network.
- The page already has a phone layout, with the kill switch pinned to the bottom of the screen (Step 6 screenshots).

## What it costs, three ways (US, before shipping and tax)

| Build | What's in it | Total |
|---|---|---|
| **Bench test only** | Pi 5 4GB $110 · Active Cooler $10.95 · 64GB card $39.95 · official 27W supply $12.95 · camera cable $10.99 | **≈ $185** |
| **On the rig (recommended)** | Core list above: Pi 5 4GB, cooler, KKSB case + 1/4" bracket, SmallRig 4887 plate, card, Geekworm 5V5A module, Tilta P-Tap lead, camera cable | **≈ $244** |
| **Rig + extras** | Recommended + 27W desk supply for testing ($12.95) + arcade kill button ($2.50 + wires) + Touch Display 2 ($54.95 at PiShop) | **≈ $315** |
| (8GB instead of 4GB) | add to any row | +$65 |
| (Simplest power instead of Geekworm + Tilta) | Kondor Blue D-tap → USB-C PD cable ($37.99) instead of $30.50 of parts: 5 V 3 A only | +$7.49 |

## First day with the Pi (when you decide to buy)

In this order, stopping at the first thing that fails:

1. Flash **Raspberry Pi OS (Legacy, 64-bit) Lite, Bookworm**. Add `kernel=kernel8.img` to `/boot/firmware/config.txt` and `usbcore.usbfs_memory_mb=150` to `/boot/firmware/cmdline.txt`. Reboot; `getconf PAGESIZE` must say **4096**.
2. Desk power first (27W supply). Download Sony's **Linux ARMv8** SDK onto the Pi (never into the repo).
3. Build and run **our read-only probe** (`probe_readonly`) with the camera on a **blue USB 3 port**. Pass = it reads the settings and saves one live-view frame. This is the go/no-go for the whole Pi plan.
4. `tools/bench_eyes.py` on the Pi: replaces the ~33 ms/frame estimate with a measurement.
5. The bridge read-only, then the runner in dry run, then the dashboard on the Pi's own screen or a laptop on the same desk.
6. Only then: power from D-tap through the Geekworm module, on the bench, watching for the Pi's under-voltage warning (`vcgencmd get_throttled` should say `0x0`).
7. Last: the hotspot + dashboard password, then the rig.
