# Step 8: Raspberry Pi 5 plan (plan only, nothing bought)

Researched 2026-10-17. Prices move fast right now (memory shortages); re-check before buying. Anything marked **UNVERIFIED** couldn't be confirmed from a reliable source.

## Will Sony's SDK work on a Pi 5 with the FX2?

**Probably, with two precautions. Not proven.**

- Sony ships a separate **Linux 64-bit (ARMv8)** SDK download (not in the Mac zip). Sony tested it on a **Pi 4 with Debian 12**, Jetson Nano and Jetson Orin Nano. **The Pi 5 is not on Sony's list.**
- One public project runs Sony's SDK (v2.00) on a Pi 5 (Ubuntu 24.04, in Docker) with a Sony A1. It reads camera settings over USB, with app-level bugs still open ([DPM-V2](https://github.com/unmanned-systems-uk/DPM-V2), [issue #54](https://github.com/unmanned-systems-uk/DPM-V2/issues/54)). No FX2-on-Pi-5 report found.
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
- Simplest fallback: a D-tap → USB-C PD cable such as [Kondor Blue](https://kondorblue.com/products/16-d-tap-to-usb-c-9v-3a-regulated-blue-braided-straight). It's 5 V 3 A only, which works with the 600 mA USB limit.
- **FX2 tip:** set the FX2's **USB Power Supply** menu so the camera doesn't try to charge from the Pi. The camera runs on its own battery.

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

## Parts list (US prices, 2026-10-17, before shipping and tax)

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
| Optional: kill-switch button | Any momentary push button + wires on GPIO | a few dollars | Price not researched |
| Not needed | Jetson Orin Nano Super | $399 | Only if the Pi 5 route fails |

## Biggest risks, in order

1. The Sony SDK on a Pi 5 is unproven, and the 16K pages need the 4K kernel. Mitigation: use the Legacy Bookworm image with `kernel8.img`, and try the SDK's sample before building anything else.
2. Power: the 5 V 5 A converter from D-tap isn't independently tested. Mitigation: bench-test it on the desk with a bench supply first.
3. Prices are volatile; re-check before buying.
