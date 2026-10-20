# Camera Agent website (draft)

The project's public page. **It's a draft and isn't deployed.** `index.html` carries `noindex` until launch.

**Preview it on this Mac:**
```
python tools/serve_site.py          # then open http://127.0.0.1:8780/
```
This needs a server rather than double-clicking the file: the page loads its data with `fetch`, and the clips need byte ranges. Port 8780 is used because 8765 is robot-walker's server and 8770 is the dashboard's.

## What's real and what's a placeholder

The page labels every piece. **Amber "Placeholder"** marks stand-in media; **teal "Real"** marks data from the camera's own logs.

| On the page | Status | Where it comes from |
|---|---|---|
| Hero, Log → LUT wipe, "How it thinks" monitor, Proof background | **Placeholder** | `media/placeholder/`: made-up scenes from `tools/make_placeholder_clips.py`. They go through the real S-Log3 curve and the blind test's LUT (Sony's LC-709TypeA). They aren't in git; remake them with that tool. |
| Look card backgrounds | **Placeholder** | Stills from the same clips |
| Dashboard screenshots | **Placeholder** | `media/screens/`, copied from `docs/screenshots/` (fake camera) |
| Hero subtitles, the real-test replay, the exposure chart | **Real** | The Oct 19 unattended test on the FX2: `data/site.json` + `media/real/` (the frame the agent saw at each change) |
| Safety counts (44 sent, 44 confirmed, 0 refused, 33 ms kill switch) | **Real** | The same test's bridge log and report |
| Looks, approved ranges | **Real** | `agent/looks.py`, `config/safe_ranges.json` |
| Pi numbers (≈ 33 ms/frame, ≈ $244) | **Estimates** | [docs/step8-pi-plan.md](../docs/step8-pi-plan.md) |
| Proof section (63 takes, 6 scenes, 3 ways) | **The plan; results pending** | [docs/step7-test-plan.md](../docs/step7-test-plan.md) |

**Refresh the real data** after a new session: `python tools/export_site_data.py [sessions/<folder>]`. It exports only exposure settings, log lines and timings; nothing else from the camera, such as its serial number.

## Before launch

- Replace the placeholder clips with real FX2 footage from the shoot, and swap the dashboard screenshots for a recording of the live dashboard.
- Fill in the Proof section with the Step 7 results.
- Add the GitHub link (the button says "Link at launch").
- Remove `noindex` and the draft bar.

## How it's built

- **Files:** plain HTML, CSS and JavaScript (ES modules), no build step.
  - `css/site.css`: the identity.
  - `js/main.js`: the scenes.
  - `js/replay.js`: the real-test player and chart.
- **Motion:** GSAP 3.14.2 with ScrollTrigger and SplitText (`vendor/gsap/`, GreenSock's no-charge standard license). Each scroll scene is a tall section with a sticky stage.
- **Reduced motion:** with `prefers-reduced-motion`, every scene shows its end state instead.
- **Type:** Instrument Serif for the film-title headlines and D-DIN (the S4D type) for labels and readouts. Both are SIL OFL, with license files in `fonts/`.
- **Identity:** the page is a viewfinder.
  - Neutral UI like a pro monitor; colour comes only from the picture or from status.
  - Camera readouts and timecode, and a letterbox that closes to 2.39:1.
  - The agent's real log lines, shown as subtitles.
  - An AF-frame cursor that locks on (teal) over anything clickable.
