# Interview prep: Camera Agent

> **Draft (2026-10-17).** The answers use only numbers we've actually measured. Where Step 7 (the real-world, blind test) will add results, it says so; update these after the test.

Ten questions you're likely to get, each with a short answer to say out loud (30–45 seconds).

---

### 1. What is it, in 30 seconds?

"It's an AI camera assistant for my Sony cinema camera. It watches the live image over USB, judges exposure the way a cinematographer does (in stops, protecting highlights and faces), and changes the ISO itself, explaining every change in one line, like 'Face −1.9 stops, target +0.5: ISO 2000 to 4000, base ISO.' I pick the look, like Cinematic 24p or Interview, and it handles exposure inside that look. One key, or one button, takes control back instantly."

### 2. Why not just use the camera's own auto exposure?

"Camera auto exposes for 'bright enough'. A DP exposes for a look. Auto will happily change the shutter and wreck motion blur, close the iris and lose the shallow depth, or let a window blow out to brighten a face. My agent keeps the 180° shutter and the look's f-stop fixed, prefers the camera's base ISOs for a cleaner image, protects highlights first, and tells me when it needs ND instead of cheating with the wrong setting. And it explains itself, which auto never does. Whether it actually beats auto is what my blind test is for."

### 3. How does it know what correct exposure is, when the picture is flat S-Log3?

"It never goes by 'looks dark'. It converts every pixel to stops above or below 18% grey, using Sony's published S-Log3 curve. Then I calibrated that on my own camera, shooting a white wall at different ISOs. One stop turned out to be 20.63 levels in the live view, and highlights clip at level 221. To check it, a one-third-stop ISO change measures as 0.331 stops, against the true 0.333."

### 4. This is your work camera. How do you make sure it can't ruin a shoot?

"Layers. It starts in a dry run where it only suggests. Live mode needs me to type LIVE, and turning Auto on takes two presses. It can only change settings I've approved, which today is just ISO, 800 to 12800. That's checked in Python, and again in a C++ bridge that has its own compiled-in allow-list. It never changes anything while the camera is recording. There's a kill switch on the space bar, the dashboard, another terminal, or just the USB cable, and a runaway guard that kills it after 20 changes in a minute. And it never touches formats, codecs, frame rate or the card, ever."

### 5. How do you stop it from pumping the exposure up and down?

"The same habits a good operator has. It ignores errors under a third of a stop, waits a moment before reacting so someone walking past a window doesn't trigger it, and moves in small steps. In a simulator with 14 situations, from sunsets to walk-bys, it never went back and forth. Then a fake camera, using my real footage, caught a case the simulator missed: at ISO 6400 a lit wall next to a lamp clipped, so it went back to 5000, then up again. So now it remembers what clipped and only goes back up if the light really drops. That case is a permanent test now."

### 6. How does it handle different skin tones?

"It never guesses anyone's skin tone. It measures how bright a face is in stops. The usual 'skin at plus one stop' rule comes from lighter skin and makes darker skin look washed out, so I set the default lower, at plus half a stop. More importantly, there's a 'this face looks right' button. I frame the person, press it once, and from then on it holds that person at the exposure I chose. The cinematographer's eye decides, not a formula. Those face signatures stay on the computer. I haven't tested it across a range of skin tones yet; that's part of my test plan, with at least two subjects."

### 7. What was the hardest problem?

"Making the measurement trustworthy. Live view is a squeezed, undocumented 8-bit version of S-Log3, so we had to calibrate it on the real camera before any decision meant anything. A close second: telling a small practical lamp, which is allowed to clip, from a big window, which isn't, so the agent doesn't fight the lamps in a shot. That rule is still crude, and I say so."

### 8. How did you test it without risking the camera?

"In stages. First the program was read-only. The code literally can't compile a 'set' call. Then one supervised ISO change to measure the camera: it confirms in 119 to 172 milliseconds and shows in the picture about 0.3 seconds later. The brain was built in a simulator with those real delays, then a fake camera that speaks the same protocol as the real bridge and uses my real frames. There are 89 automated tests, including the kill switch and 'nothing changes while recording'. Then the first live run, on a wall and a lamp: I set ISO two stops too bright and it came back in five one-third-stop steps in about eight seconds. Then it left everything alone for a full minute, and the kill switch stopped it in 33 milliseconds. Afterwards every setting was back exactly as I'd left it."

### 9. What did you do, and what did the AI do?

"I directed it and designed the cinematography. I set the goal, the looks, the safety rules and the ranges for my own camera, and I made every decision along the way, like only allowing ISO for the first live test. I set up and approved every camera test, ran the early ones and the calibration myself, and gave the go for the first live run, which ran unattended. The AI wrote the code: the C++ bridge to Sony's SDK, the Python agent, the tests and the dashboard. We worked one step at a time, and I reviewed each step before the next one started."

### 10. How will you prove it works, and what's next?

"I wrote the test plan before shooting, so I can't move the goalposts. The scenes are a backlit window, shade to sun, tungsten, low light, sunset and a static control. Each one is shot three ways (my agent, the camera's auto, and me by hand) in a balanced random order. It measures clipping, face exposure, time to settle and flicker. Then friends rate the clips blind. [Update with the results.] Next is a Raspberry Pi 5 on the rig, powered from the V-mount, with the dashboard on my phone. It costs about $244 in parts, and the Pi looks fast enough, so no Jetson is needed."

---

## Resume bullets (draft: real numbers only; update after Step 7)

- **Directed the design of an AI exposure assistant for the Sony cinema camera** that reads S-Log3 live view over USB at 24 fps (~10 ms of analysis per frame on an M2) and sets ISO through Sony's Camera Remote SDK; the camera confirms changes in 119–172 ms.
- **Designed explainable cinematography rules** (180° shutter, base ISO 800/4000, highlights → faces → scene) and a per-person "this face looks right" reference in place of a single skin-tone default. Validated in a 14-scenario simulator with zero exposure back-and-forth and 62 automated tests.
- **Specified layered safety for a working camera** (approved-settings allow-list in C++ and Python, read-only mode, kill switch, runaway guard, session snapshot and restore) and a blind test, written before shooting, comparing the agent with the camera's auto and manual exposure.
