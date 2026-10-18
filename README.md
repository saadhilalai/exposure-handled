# Camera Agent

An AI camera assistant that runs exposure like a cinematographer. It watches the live image from a Sony FX2, picks ISO, shutter, iris, white balance and focus help for a chosen look (for example "Cinematic 24p, shallow"), changes them on the camera, and explains every choice in one line.

Status: early development. See [PROGRESS.md](PROGRESS.md).

## Exposing every skin tone correctly

The agent is designed to expose correctly across skin tones.

- **It never guesses or labels anyone's skin tone.** It measures how bright each face is, in stops relative to 18% grey, and compares that with a target.
- **The default face target is +0.5 stop.** The common "skin at +1 stop" rule of thumb comes from lighter skin and pushes darker skin too bright, so the default sits lower (director's decision, 2026-10-17).
- **Set each person once (planned for the dashboard, Step 6):** frame the person, press "this face looks right", and the agent holds that exposure for that person from then on. The cinematographer's eye decides, not a formula.
- **Faces never clip:** a clipping face is treated like a clipping window, for everyone.
- **Honest status:** not yet tested on a range of skin tones with the real camera. That is part of the Step 7 test plan.

## Try the agent without a camera

```
.venv/bin/python tools/run_agent.py --fake
```

This runs the full loop (eyes → brain → safety gate → bridge) against a fake FX2 that speaks the real bridge's protocol. Keys: SPACE kill switch, `p` pause, `1`-`5` look, `q` quit. Details: [docs/step5-brain.md](docs/step5-brain.md).

## Getting Sony's Camera Remote SDK

This project talks to the camera through Sony's Camera Remote SDK. Sony's license does not allow the SDK files (libraries, headers, sample code, docs) to be shared, so they are **not** in this repo. Each developer downloads them from Sony:

1. Go to Sony's Camera Remote SDK page: https://www.sony.net/CameraRemoteSDK/
2. Read and accept Sony's license agreement, then download the package for your OS (this project was built with **CrSDK v2.02.00 for macOS**).
3. Put the zip in the project folder and unzip it into `sdk/`:

   ```
   unzip CrSDK_v2.02.00_*_Mac.zip -d sdk/
   cd sdk && unzip RemoteCli.zip -d RemoteCli && unzip CrSDK_API_Reference_v2.02.00.zip -d CrSDK_API_Reference_v2.02.00
   ```

`sdk/` and the zip are listed in `.gitignore` so they are never committed.

On macOS, remove the download "quarantine" flag from Sony's libraries (Sony's instruction):

```
cd sdk/RemoteCli/external/crsdk
xattr -d com.apple.quarantine libCr_Core.dylib libmonitor_protocol*.dylib CrAdapter/*.dylib
```

## Build and run the read-only probe

Needs CMake (`brew install cmake`) and Apple's Command Line Tools.

```
cmake -S bridge -B build/bridge
cmake --build build/bridge -j2
mkdir -p sessions/test && (cd build/bridge && ./probe_readonly ../../sessions/test)
python3 tools/show_settings.py sessions/test
```

The probe only reads. It cannot change camera settings (see `docs/step2-first-connection.md`).

## Built by

Built by Saad Hilal · S4D. Directed by Saad Hilal; code written with an AI coding assistant.
