# Rendering the films' 3D shots on the gaming PC

The Mac only does light Blender jobs (previews, test frames, low-res drafts). The full shot renders run on the gaming
PC (RTX 3080, Windows with WSL Ubuntu), then come back to the Mac for the edit.

The finished clips travel through a **private** Hugging Face dataset, `s4dAi/camera-agent-renders`. They never go
through the public GitHub repo.

## One-time setup (in the Ubuntu terminal on the PC)

1. Install the tools Blender and the upload step need:

   ```bash
   sudo apt update && sudo apt install -y git ffmpeg python3-pip libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libxkbcommon0 libsm6 libice6
   pip3 install --user --break-system-packages -U huggingface_hub
   ```

2. Check that WSL can see the graphics card. It should list the RTX 3080; if it doesn't, update the NVIDIA driver in Windows.

   ```bash
   nvidia-smi
   ```

3. Get the project:

   ```bash
   cd ~ && git clone https://github.com/saadhilalai/exposure-handled.git && cd exposure-handled
   ```

4. Sign in to Hugging Face once, with a **write** token from https://huggingface.co/settings/tokens (account s4dAi):

   ```bash
   ~/.local/bin/hf auth login
   ```

## Every time: render and send the shots back

```bash
cd ~/exposure-handled && git pull
bash video/blender/render_pc.sh
```

- **What it does:**
  - The first run downloads Blender 5.2.2 for Linux into your home folder. It must be the same version as the Mac's.
  - It renders the remaining shots on the GPU (OptiX, falling back to CUDA), one at a time.
  - It uploads each finished clip to the private dataset.
- **If it stops** (the PC sleeps, or you close the window): run the same command again. It skips finished shots and
  continues an unfinished one from its last frame. A failure stops the whole run, and nothing restarts on its own.
- **To render only some shots:** `bash video/blender/render_pc.sh h_xray h_chip`
- **Shots still to render:** s_catch and s_hero (story), then h_world, h_smash, h_xray, h_irisx, h_chip, h_swarm, h_kill and
  h_slam (hype).

Then tell the AI on the Mac "renders are up". It fetches them with `.venv/bin/python tools/fetch_renders.py` and
finishes the films.
