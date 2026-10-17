# Camera Agent

An AI camera assistant that runs exposure like a cinematographer. It watches the live image from a Sony FX2, picks ISO, shutter, iris, white balance and focus help for a chosen look (for example "Cinematic 24p, shallow"), changes them on the camera, and explains every choice in one line.

Status: early development. See [PROGRESS.md](PROGRESS.md).

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

## Built by

Built by Saad Hilal · S4D. Directed by Saad Hilal; code written with an AI coding assistant.
