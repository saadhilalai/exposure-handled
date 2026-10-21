# Camera Agent website (draft, v2)

The project's public page. **It's a draft and isn't deployed.** `index.html` carries `noindex` until launch.

**Preview it on this Mac:**
```
python tools/serve_site.py          # then open http://127.0.0.1:8780/
```
It needs a server rather than double-clicking the file: the page loads its data with `fetch` and the 3D files as modules. Port 8780 is used because 8765 is robot-walker's server and 8770 is the dashboard's.

## The idea

You're holding a cinema camera, and the AI is your assistant inside it. People learn by playing, not reading.

| # | Section | What you do |
|---|---|---|
| 1 | Viewfinder | Watch the AI take over: settings tick, the picture corrects, it says why. Scroll, and the view pulls back to the camera's own screen. |
| 2 | Inside the camera | The camera comes apart in 3D. Orange agents swarm the sensor (ISO), crank the iris (aperture), repaint a color chip (WB), and freeze when you press STOP. |
| 3 | Your turn | Four camera dials and four lighting setups. Break the picture, then let the AI fix it. Change the light and it reacts. |
| 4 | Beat the AI | 15 seconds to fix a bad shot. The AI starts from the same shot, and both get scored. |
| 5 | See what it sees | Drag the slider: AI fix, S-Log3, false color, zebras. |
| 6 | Tested on a real camera | The agent's own log from the Oct 19 FX2 test, as a chart and four gauges. |
| 7 | Never touch | Locked buttons you can try to press, and the approved ranges as arcs. |
| 8 | Every decision, live | The dashboard. |
| 9 | Finale | The camera snaps back together. |

**Rules for words:**
- Short headlines.
- No captions under things.
- Every number gets a visual.
- All explanations, measurements and honest footnotes sit behind the **Nerd mode** switch (top right, or press N).
- Sound is off until you turn it on (or press M).
- Easter eggs: press **Z** for zebras and **F** for false color.

## What's real, what's a placeholder, what's an illustration

| On the page | Status | Where it comes from |
|---|---|---|
| The Oct 19 chart, gauges, ISO sequence, 33 ms kill switch | **Real** (teal tag) | `data/site.json`, exported from the session logs by `tools/export_site_data.py` |
| Approved ranges and locked settings | **Real** | `config/safe_ranges.json` and the agent's safety rules |
| Dashboard screenshots | **Placeholder** (amber tag) | `media/screens/`, the real dashboard running on the fake camera; to be replaced by a recording on the FX2 |
| The camera picture in the viewfinder, simulator, game and slider | **Illustration** (tagged in Nerd mode) | Rendered live in the browser by `js/sim.js`; not footage |
| The 3D camera and its crew | Illustration | `js/camera3d.js`; an original design inspired by the FX2, with no maker's name |

The simulator's AI (`js/ai.js`) is a small copy of the agent's rules for the demo:
- a 180° shutter
- the iris only when ISO can't go lower
- ISO to land the subject
- highlights protected
- WB set to the light (kept a little warm under tungsten and at sunset)

It stays inside the real approved ranges. Nerd mode says so on the page.

## Before launch

- Add real FX2 footage from the shoot (for example as a mode of the before/after slider), and swap the dashboard screenshots for a recording on the FX2.
- Add the Step 7 results.
- Point "See the code" at the repo once it's public (it goes to the GitHub profile for now).
- Remove `noindex` and the Draft chip.

## How it's built

- **Files:** plain HTML, CSS and JavaScript modules, no build step.
  - `css/site.css`: the look.
  - `js/main.js`: the sections.
  - `js/ui.js`: dials, chat feed, sound, cursor.
  - `js/sim.js`: the camera picture.
  - `js/ai.js`: the demo AI and scoring.
  - `js/camera3d.js`: the 3D camera.
- **The camera picture (`sim.js`):** one WebGL2 renderer draws a made-up scene in linear light, in three passes:
  1. **The scene:** the reel's motion blur is integrated over the shutter time.
  2. **Depth of field:** a gather blur, with real bokeh from the lights, shaped by a nine-blade iris.
  3. **The camera:** exposure (ISO × shutter ÷ f-stop²), black-body white balance, ISO noise, sensor clipping, then a film-style display curve, S-Log3, false color or zebras.

  The same renderer serves every view on the page.
- **3D:** three.js 0.186.1 (`vendor/three/`, MIT), with depth of field that racks to whatever the story is about, and bloom for the crew. Every part, texture and the crew is made in code; nothing is downloaded.
- **Motion:** GSAP with ScrollTrigger (`vendor/gsap/`, GreenSock's standard license). The 3D camera follows the scroll, and the other sections are calm.
- **Speed:**
  - **Automatic quality** (`js/quality.js`). Three levels: high, medium, low.
    - **First guess:** from the graphics chip, CPU cores and memory.
    - **Then the real frame rate decides:**
      - When frames run long, the render resolution drops; if that isn't enough, the level steps down. Under ~15 fps it goes straight to low.
      - If the processor is what's busy, the level steps down at once (medium skips the depth-of-field pass, which halves the 3D's draw calls).
      - After a busy spell (another app, a download), the resolution climbs back and it tries one level up after 8 calm seconds. A step that runs slow again isn't retried.
    - **What changes per level:** the 3D pixel ratio, depth of field, glow, number of agents and edge smoothing (MSAA), plus the camera pictures' resolution and blur taps.
    - **Nerd mode** shows a live counter: fps, level and resolution.
  - **Only what's on screen renders:** the 3D stops when it's faded out, and each camera picture draws only while it's (nearly) visible. Hidden pictures give their GPU memory back after 15 s. Off-screen sections and hidden beats pause their CSS animations, which otherwise cost style and layer work every frame.
  - **The 3D camera's CPU cost:** pieces that never move on their own are merged per part and material (about a third fewer draw calls). The scene's matrices update once a frame, and the canvas size is read only when it changes.
  - **The 3D rear screen** gets one still frame, because copying a live picture between the two graphics contexts stalled frames.
  - **Without a graphics chip** (software rendering): no 3D (the camera chapter reads as a normal page), small camera pictures that redraw only when something changes, and no blur, glow or moving grain.
  - **The cursor** is drawn by the system, so it tracks the mouse exactly. Over anything clickable, orange brackets snap around the element itself (`lockFrame` in `js/ui.js`). They follow the element, not the mouse, so they can't lag.
  - **Measured in Chrome on the M2** (October 20): 60 fps everywhere on a retina screen, with the CPU slowed 4× and 6×, with a graphics chip emulated 2× and 9× weaker (the page renders that many more pixels), and with no GPU at all. Not tested on real Windows, Intel or iPhone hardware.
  - **Testing knobs:** `?quality=high|medium|low` forces a level, `?gpuload=N` acts like a weaker chip, `?debug` exposes internals.
- **Reduced motion:** with `prefers-reduced-motion`, nothing scrubs or flies. The camera chapter reads as a normal page over a still exploded view.
- **If 3D can't start:** the page retries once, then shows the camera chapter as a normal page.
- **Type:** Instrument Serif for headlines, D-DIN (the S4D type) for readouts. Both are SIL OFL, with license files in `fonts/`.
