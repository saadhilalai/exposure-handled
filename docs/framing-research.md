# Does Camera Agent already exist? Framing research for the launch film

Research date: 2026-10-21. About 60 web, code and paper searches, plus direct checks of the pages that mattered most. Every claim below has a link.

---

## The short answer

**The pieces exist. The whole combination doesn't seem to, at least not in public.**

- Cameras have set their own exposure for decades: auto ISO, auto iris, Auto ND, face-weighted metering. Since July 2026 Sony also has an AI (deep-learning) auto white balance in the FX5. None of these works from a creative look, and none explains its choices.
- **The closest product is FrameCoach** (iPhone app, 2026). It reads a Sony or Canon camera's live feed, Canon's cinema cameras included. You describe the look in plain English, and it gives up to three ranked changes, each with its reason. One tap sends a change to the camera. But its own support page says it **"never adjusts settings automatically"**: a person approves every change.
- **The closest coming product is Darkgrade** (Y Combinator, Fall 2024). It's an open camera-control engine, already tested on a Sony FX2. Its roadmap lists "one tap to set lights, audio & exposure", "let AI assistants run the camera" and "AI that understands what your camera sees", all marked "on the way". It targets YouTubers and podcasters, not cinematographers.
- **The closest hobby project is So-DSC.** It lets a chat AI see a Sony RX100's live view and change ISO, shutter, aperture, exposure compensation and white balance itself, while chatting. It's a compact stills camera with no safety limits, and the project has 1 star.
- **Research** has many learned auto-exposure controllers. Their goal is machine vision (robots, object detection), not a creative look. One vision-language model suggests manual settings but doesn't change the camera.

I found nothing public that does all of these together:

1. watches a **pro cinema camera's** live image;
2. **changes its exposure itself**, with no tap per change;
3. steers by a **chosen creative look**;
4. explains **every change in one plain line**;
5. stays inside a **safety envelope**: an approved list, no changes while recording, a kill switch and a full change log.

That's real, but it isn't proof. See the verdict for why a "first" line is still risky.

---

## What Camera Agent actually does today (checked in the project files, so the film stays accurate)

From `README.md`, `PROGRESS.md` and `agent/runner.py`:

- **How it decides:** explainable rules ("no black box"), plus neural face detection and recognition from OpenCV. **It is not an LLM, and it isn't a trained exposure controller.** "AI assistant" is fair; "AI that learned from DPs" would not be.
- **What it changes:**
  - ISO, by itself, in a live closed loop on a real FX2 (passed 2026-10-19).
  - All four settings (shutter 1/48, f/4, ISO, white balance 2800K), in one automatic run of the Interview look (Test 3, passed).
  - Today's approved range is ISO 800–12800.
- **Kill switch:** the dashboard button stopped it in **33 ms** on the real camera, and the bridge locked.
- **Restore, a correction to the brief:** the kill switch **does not** restore settings. After a kill the session is locked and nothing is sent. At the normal end of a live session, it **offers** to put your approved settings back to where they started, or does it automatically with `--restore`. So say "stops in 33 ms" and "offers to put your settings back", not "stops and restores in 33 ms".
- **Not done yet:** the blind test against FX2 auto and manual (Step 7), and testing on a range of skin tones. **Don't claim "better than auto" or "works for every skin tone" yet.**
- **No LICENSE file** in the repo, so don't call it "open source" in the film.

---

## What already exists

Key: **Live** = reads the live image. **Sets** = changes the camera's settings itself. **Pro** = aimed at cinema or professional video. **Look/Why** = works from a creative look / explains its choices. Y = yes, N = no, ~ = partly.

### 1. Camera makers' built-in features

| Thing | What it is | Live | Sets | Pro | Look / Why | Status | Source |
|---|---|---|---|---|---|---|---|
| Sony FX2 auto exposure | Intelligent Auto, P/A/S modes, ISO Auto, ISO Range Limit, "Face Priority in Multi Metering" | Y | Y | Y | N / N | Shipping | [FX2 Help Guide](https://helpguide.sony.net/ilc/2530/v1/en/index.html); [what Face Priority metering does (α7 IV guide)](https://helpguide.sony.net/ilc/2110/v1/en/contents/TP1000655352.html) |
| Sony Auto ND (FX6, FX9, FS5, Z190/Z280…) | Electronic variable ND that "proactively and automatically" holds exposure | Y | Y | Y | N / N | Shipping (since ~2017) | [Sony Pro: Variable ND](https://pro.sony/en_IE/technology/variable-auto-nd-filter-technology) |
| Sony FX5 "Auto Tracing White Balance" | Deep-learning light-source estimation on the new AI unit (announced 2026-07-22) | Y | Y (WB only) | Y | N / N | Shipping | [What Digital Camera](https://www.whatdigitalcamera.com/photography-news/open-gate-recording-comes-to-sony-via-fx5-with-internal-x-ocn-raw-and-16-stops-of-dynamic-range); [Fstoppers](https://fstoppers.com/gear/sony-fx5-fx3-two-features-everyone-asked-903682) |
| Sony AI processing unit (FX2, FX3, FX5, PXW-Z300) | Subject recognition for autofocus, auto framing | Y | Focus/framing only | Y | N / N | Shipping | [Park Cameras FX2](https://www.parkcameras.com/shop/sony-fx2-full-frame-cinema-line-camera_7634619m); [CineD Z300](https://www.cined.com/sony-pxw-z300-announced-1-2-inch-4k-3-cmos-camcorder-with-17x-zoom-ai-features-and-world-first-content-authentication/embed/) |
| Sony Monitor & Control / Creators' App | Phone and tablet remote with waveform, false color, zebras | Y | Manual only | Y | N / N | Shipping | [Videomaker](https://www.videomaker.com/news/sony-releases-updated-monitor-control-app/) |
| Canon Cinema EOS | Auto Iris, Push Auto Iris, Auto ISO/Gain, AE shift. C400 adds Auto Exposure Ramping Compensation (Aug 2026). | Y | Y | Y | N / N | Shipping | [Canon C200 specs](https://www.canon-europe.com/video-cameras/eos-c200/specifications/); [Canon, Aug 2026 firmware](https://www.canon.co.uk/press-centre/press-releases/2026/08/canon-enhances-cinema-eos-with-new-eos-c80-and-eos-c400-firmware-update/) |
| Panasonic AG-CX20/CX18 | "Faces are detected… and the exposure is matched" | Y | Y | Pro camcorder | N / N | Shipping | [Panasonic manual](https://eww.pavc.panasonic.co.jp/hdw/oi/AG-CX20/html/AG-CX20_CX18_DVQP3341_eng/0091.html) |
| Blackmagic PYXIS (BlackmagicOS) | Configurable auto exposure modes | Y | Y | Y | N / N | Shipping | [Blackmagic](https://www.blackmagicdesign.com/uk/products/blackmagicpyxis/blackmagicos) |
| DJI Ronin 4D / Focus Pro | LiDAR plus AI recognition, for focus. No AI exposure found. | Y | Focus only | Y | N / N | Shipping | [Engadget](https://www.engadget.com/dj-is-8-k-ronin-4-d-camera-has-a-built-in-gimbal-and-li-dar-autofocus-system-165716323.html) |
| Atomos Ninja TX camera control (Nov 2025) | Change ISO, shutter and WB from the monitor | Y | Manual only | Y | N / N | Shipping | [PetaPixel](https://petapixel.com/2025/11/19/atomos-ninja-tx-series-now-offers-much-more-camera-control/) |
| ARRI, RED, Zeiss, Insta360 | Nothing found on AI exposure control | n/a | n/a | n/a | n/a | n/a | (searches came up empty) |

### 2. Broadcast and robotic cameras

| Thing | What it is | Live | Sets | Pro | Look / Why | Status | Source |
|---|---|---|---|---|---|---|---|
| Cyanview, SKAARHOJ panels | Remote shading of many camera brands. Manual, with classic auto-iris modes. | Y | Manual / classic auto | Y | N / N | Shipping | [Cyanview](https://www.cyanview.com/); [SKAARHOJ Sony](https://www.skaarhoj.com/integrations/sony) |
| Vinten VEGA CCU | Shading saved with preset shots | n/a | Recalls presets | Y | N / N | Shipping | [Vinten](https://www.vinten.com/en/product/vega-ccu/) |
| Sony BRC-AM7 PTZ | AI tracking and auto framing. A NAB 2026 firmware lets it "color match other cameras" (method not described). | Y | Framing; colour match | Y | N / N | Shipping | [SVG, NAB 2026](https://www.sportsvideo.org/2026/04/16/nab-2026-inside-sonys-wide-range-of-new-offerings-enhancements-to-cameras-to-switchers-and-more/) |
| Panasonic AW-UE160 PTZ | AI auto framing, plus a classic "auto iris window" | Y | Framing; classic iris | Y | N / N | Shipping | [Panasonic](https://eu.connect.panasonic.com/ae/en/products/broadcast-proav/aw-ue160) |
| Studio Automated (German Supercup, Aug 2026) | AI moves a PTZ head; "production companies… shade it in real time" | Y | Pan/tilt/zoom only | Y | N / N | In use | [SVG Europe](https://www.svgeurope.org/blog/headlines/ai-powered-automated-cameras-introduced-into-live-host-feed-in-first-for-supercup/) |
| "AI shading" or "AI paint" products | **None found** from Sony, Grass Valley, Ikegami, Cyanview, or at NAB 2026 | n/a | n/a | n/a | n/a | n/a | (several searches came up empty) |

### 3. Apps and startups

| Thing | What it is | Live | Sets | Pro | Look / Why | Status | Source |
|---|---|---|---|---|---|---|---|
| **FrameCoach** (FrameCoach Ltd., iPhone) | **Closest match.** Live feed over Wi-Fi from Sony (Camera Remote API bodies), Canon CCAPI bodies (including C70, C80, C300 III, C400, C500 II) or the iPhone. You describe the look ("cinematic sunset interview"); it gives 3 ranked changes, each with a reason. One-tap Apply. Analysis runs in the cloud. | Y | **Only when you tap Apply.** "FrameCoach never adjusts settings automatically." | Y (filmmakers) | **Y / Y** | Shipping, free. Versions 1.0–1.6 dated Mar 27–Jun 24 (listing © 2026). | [Site](https://www.framecoach.io/); [Support / camera list](https://www.framecoach.io/support); [App Store](https://apps.apple.com/app/id6757565363) |
| **Darkgrade** (Y Combinator F24) | Open camera-control engine "Link" (alpha), tested on Sony FX2, A7 IV, Canon R6 III and more. "Studio" app in development. Roadmap, all "on the way": one-tap exposure, AI assistants running the camera, AI that understands what the camera sees. | Y | By code; AI exposure not yet | Creators, YouTubers | Not yet | Alpha / roadmap | [darkgrade.com](https://darkgrade.com); [Roadmap](https://darkgrade.com/roadmap); [GitHub](https://github.com/darkgrade/darkgrade); [YC](https://www.ycombinator.com/companies/darkgrade) |
| Camera Intelligence "Caira" | Micro Four Thirds camera that clips onto an iPhone. Conventional AI auto exposure, voice control, and generative "exposure tuning" in the gallery *after* capture. The capture pipeline is non-generative. | Y | Its own AE | Creators | ~ / N | Kickstarter 2025, shipping 2026 | [CineD](https://www.cined.com/camera-intelligence-caira-ceo-vishal-kumar-on-the-new-ai-iphone-camera-attachment-and-lessons-from-the-alice-camera/); [PetaPixel](https://petapixel.com/2025/09/03/camera-intelligence-formerly-alice-camera-pivots-to-ai/) |
| Kino (Lux) | iPhone video app. "AutoMotion" exposure is biased to a 180° shutter. Not AI. | Y | Y (phone) | ~ | ~ / N | Shipping | [App Store](https://apps.apple.com/app/id6472380172) |
| Blackmagic Camera (iOS) | Tap to expose; auto exposure you can lock. Not AI. | Y | Y (phone) | ~ | N / N | Shipping | [Blackmagic forum](https://forum.blackmagicdesign.com/viewtopic.php?p=989025) |
| SensePose (Android) | AI sets ISO, EV and shutter live. Shows the values, doesn't explain them. Photos only. | Y | Y (phone) | N | N / N | Shipping | [SensePose](https://www.sensepose.com/blog/best-ai-camera-app-android) |
| Middle Control 4.0 (Sep 2026) | Free control of 200+ cameras, Sony FX included. Manual exposure, plus an automation page for moves. | Y | Manual | Y | N / N | Shipping | [Newsshooter](https://www.newsshooter.com/2026/09/15/middle-control-4-0-control-200-camera-models-from-one-free-app/) |

### 4. Open source and hobby

| Thing | What it is | Live | Sets | Pro | Look / Why | Status | Source |
|---|---|---|---|---|---|---|---|
| **So-DSC** | Server that lets a chat AI see a Sony RX100 VA's live view and set ISO, shutter, aperture, EV and WB. README describes the AI correcting itself ("too bright, EV −1"). No safety limits. | Y | **Y, while chatting** | N (compact) | N / chat only | Hobby, 1 star | [GitHub](https://github.com/nananek/so-dsc) |
| Canon MCP server | A chat AI turns commands ("set iso 320") into Canon CCAPI calls. Has a live-view tool; no exposure judgement. | ~ | On command | N | N / N | Hobby, 9 stars | [GitHub](https://github.com/ediardo/canon-mcp-server) |
| sonycam | Command-line tool for Sony's Camera Remote SDK, built to be called by coding agents. No decision-making. | ~ | On command | N | N / N | Hobby | [GitHub](https://github.com/davidanthoff/sonycam) |
| sonshell | Shell for Sony's SDK (FX3, FX30, FX6). Manual control. | Y | Manual | Y | N / N | Hobby | [GitHub](https://github.com/goudvuur/sonyshell) |
| CamBridge | One studio's multi-camera panel (FX3 and FX30). Manual exposure, presets, matching. | Y | Manual | Y | N / N | Private use | [GitHub](https://github.com/Rareuncommon/cam_control) |

### 5. Research

| Thing | What it is | Live | Sets | Pro | Look / Why | Status | Source |
|---|---|---|---|---|---|---|---|
| Lee et al., CVPR 2024 | Reinforcement-learning auto exposure (exposure time and gain). Reaches its target exposure in 5 steps. Goal: computer vision. | Y | Y | N | N / N | Research | [CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/html/Lee_Learning_to_Control_Camera_Exposure_via_Reinforcement_Learning_CVPR_2024_paper.html) |
| Yang et al., 2018 | Reinforcement-learning exposure for phone live preview, linking scene content to exposure | Y | Y | N | N / N | Research | [arXiv 1803.02269](https://arxiv.org/abs/1803.02269) |
| Tomasi et al., 2021 | Learned gain and exposure control for robot navigation | Y | Y | N | N / N | Research | [arXiv 2102.04341](https://arxiv.org/abs/2102.04341) |
| Microsoft patent | Deep network for real-time "semantic-aware" exposure control | Y | Y | N | N / N | Patent | [US10530991](https://patents.google.com/patent/US10530991) |
| Lens (ICLR 2025) | Adapts real sensor settings in real time so a vision model sees better | Y | Y | N | N / N | Research | [arXiv 2503.02170](https://arxiv.org/abs/2503.02170) |
| ACamera-Net (2025) | Predicts ISO and white balance from RAW, for "professional-style imaging" | Y | Y | ~ | N / N | Research | [arXiv 2510.20550](https://arxiv.org/abs/2510.20550) |
| Vision-Language-Camera (VLC) | A vision-language model *suggests* manual-mode settings, with instructions | Y | **N (advice only)** | N | ~ / Y | Research | [GitHub](https://github.com/zqianaa/VLC) |
| SCOPE (HRI 2026), OPUS (2025) | Language-model agents that drive PTZ cameras. Pan, tilt and zoom only, no exposure. | Y | Movement only | N | N / N | Research | [arXiv 2606.02951](https://arxiv.org/abs/2606.02951); [arXiv 2505.06402](https://arxiv.org/abs/2505.06402) |
| CineMPC (2024), RoboPhoto-VLA (Oct 2026), PhotoAgent (2026) | Drone and robot "cinematographers" that control camera position, focus and zoom. Not exposure. | Y | Pose/focus/zoom | ~ | ~ / N | Research | [arXiv 2401.05272](https://arxiv.org/abs/2401.05272); [arXiv 2610.26287](https://arxiv.org/abs/2610.26287); [arXiv 2603.22796](https://arxiv.org/abs/2603.22796) |

---

## Who already has each piece

| Piece of Camera Agent | Already done by |
|---|---|
| Watches a cinema camera's live image | Many: the camera's own metering, FrameCoach, Darkgrade, Monitor & Control |
| Changes exposure on the camera by itself | Built-in AE (auto ISO, auto iris, Auto ND, FX5 AI white balance); So-DSC (hobby, compact camera); research controllers |
| Decides from a named creative look | FrameCoach (but advice only, applied by tap) |
| Explains each change in plain English | FrameCoach (advice only); VLC (research, advice only) |
| Safety envelope: approved list, recording lock, kill switch, change log | Cameras have limits like ISO Range Limit, but I found no external AI tool with a kill switch and logged reasons |
| **All of it together, on a cinema camera, without a tap per change** | **Nothing found** |

---

## Verdict

### Can we say "first"?

**A narrow "first" might be true, but I can't verify it, and I don't recommend putting it in the film.**

Why "first" claims are hard:

- **You can't prove a negative.** These searches only cover what's public, indexed and in English. A private studio tool, a demo posted only on social media, or a non-English project wouldn't show up.
- **The nearest competitor is one feature away.** FrameCoach already does the look, the explanation and applying changes to Canon cinema cameras. If it adds an "auto-apply" switch, a "first" line becomes false overnight. Darkgrade has AI exposure on its public roadmap and already runs on the FX2.
- **"First" draws "well, actually…" replies.** Built-in auto exposure has changed cinema-camera settings by itself for decades. Sony's FX5 now uses deep learning for white balance. So-DSC lets an AI see live view and change exposure. Each of these could be used to argue against a loosely worded "first".
- **The word "AI" can be challenged.** Camera Agent decides with explainable rules plus neural face detection. That is a strength, but a "first AI" claim invites a fight over what counts as AI.

**If you still want one**, this is the narrowest wording the sources support. It belongs in the description, with the date and a "we looked" caveat, not spoken in the film:

> "As far as we can find (October 2026), the first assistant that runs a cinema camera's exposure on its own, from a chosen look, and explains every change in plain English."

- **Confidence:** moderate that nothing public did all of this before 2026-10-21. Low that it stays true for long.
- **Key sources:** FrameCoach's "never adjusts settings automatically" ([support](https://www.framecoach.io/support)); Darkgrade's roadmap, where AI exposure is still "on the way" ([roadmap](https://darkgrade.com/roadmap)); So-DSC is a compact camera with no look system ([GitHub](https://github.com/nananek/so-dsc)); camera-maker AE has no looks or explanations ([FX2 Help Guide](https://helpguide.sony.net/ilc/2530/v1/en/index.html), [Sony Auto ND](https://pro.sony/en_IE/technology/variable-auto-nd-filter-technology), [FX5 AI white balance](https://www.whatdigitalcamera.com/photography-news/open-gate-recording-comes-to-sony-via-fx5-with-internal-x-ocn-raw-and-16-stops-of-dynamic-range)).

### Recommended: vision framing

Lead with the idea, not a race. Either of these works as the hook:

- **"What if your camera had a cinematographer beside it?"** "Inside it" is more poetic, but the agent runs on the laptop next to the camera. "Beside it" is literally true. Use "inside it" only if you're fine with the metaphor.
- **"A camera that thinks like a cinematographer."** This is plainly a metaphor, so it's safe.

### Big, confident lines that are true without "first"

Each is checked against the project's own logs (Oct 19 real-camera tests).

1. **"Pick the look. It handles the exposure."** Five looks. It sets ISO itself; iris, shutter and white balance too when you approve them (Test 3, interview look).
2. **"It reads the picture in stops, like a DP. Highlights first, then faces."** This is the README's rule order.
3. **"No tap to approve. It sets the camera itself, and tells you why."** This is the real difference from FrameCoach, said without naming anyone.
4. **"Every change, explained in one line."** For example: "Face −1.9 st (target +0.5): ISO 2000 → 4000 (base ISO)".
5. **"It only touches what you approve. Never while you're rolling."** Approved list (today ISO 800–12800) and the lock while recording.
6. **"One key. Stopped in 33 milliseconds."** Real dashboard kill-switch test, Oct 19. Keep restoring separate: "At the end, it offers to put your settings back."

Two more that are true and on-brand:
- **"No black box. Every rule is a DP's rule."**
- **"Built by a working cinematographer. Tested on a real Sony FX2."**

**Avoid for now:**
- "first" or "only" in the film;
- "better than auto" (the blind test hasn't been shot);
- "works for every skin tone" (not yet tested across skin tones);
- "stops and restores in 33 ms" (the kill switch locks; restoring is a separate end-of-session offer);
- "open source" (the repo has no license file);
- anything implying it learned from DPs or uses a large language model.

---

## Limits of this research

- Searches were in English. YouTube, X and Reddit coverage through search engines is thin, and private or closed-beta tools wouldn't appear.
- FrameCoach's own pages disagree. The website says FX3 and FX30 support is "in development", but the App Store notes for 1.6.0 list them as connecting directly. Either way, every change still needs a tap.
- Some items rely on retailer or press pages rather than manuals: the Sony FX2 AI unit, the Canon C400 auto modes and the BRC-AM7 colour match.
