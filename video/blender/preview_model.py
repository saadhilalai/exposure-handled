"""Quick look renders of the camera model (ortho front/top/side to compare with Sony's photos, and 3/4 views).
Run: Blender -b -P video/blender/preview_model.py -- [view ...] [--res 960] [--samples 24] [--out DIR] [--xray 0.0]"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = {"--res": "960", "--samples": "24", "--out": str(ROOT / "video" / "blender" / "out" / "fxprev"), "--xray": "0.0"}
views, i = [], 0
while i < len(argv):
    if argv[i] in opts:
        opts[argv[i]] = argv[i + 1]
        i += 2
    else:
        views.append(argv[i])
        i += 1
bpy.ops.wm.open_mainfile(filepath=str(ROOT / "video" / "blender" / "cache" / "model.blend"))
pr = bpy.context.preferences.addons["cycles"].preferences
pr.compute_device_type = "METAL"
pr.get_devices()
for d in pr.devices:
    d.use = d.type == "METAL"
sc = bpy.context.scene
sc.cycles.device = "GPU"
sc.cycles.samples = int(opts["--samples"])
w = int(opts["--res"])
sc.render.resolution_x, sc.render.resolution_y = w, round(w * 9 / 16)
sc.render.use_motion_blur = False
sc["xray"] = float(opts["--xray"])
for L in bpy.data.lights:
    if L.name not in ("agent light",):
        pass
out = Path(opts["--out"])
out.mkdir(parents=True, exist_ok=True)
cam = bpy.data.objects["film camera"]
V = {  # name: (pos, target, ortho scale or lens mm, ortho?)
    "front": ((0.0, -1.0, 0.0), (0.0, 0.0, 0.0), 0.16, True),
    "top": ((0.0, -0.01, 1.0), (0.0, -0.01, 0.0), 0.2, True),
    "side": ((1.0, -0.02, 0.0), (0.0, -0.02, 0.0), 0.2, True),
    "rear": ((0.0, 1.0, 0.0), (0.0, 0.0, 0.0), 0.16, True),
    "hero": ((-0.33, -0.42, 0.16), (0.0, -0.035, 0.0), 60, False),
    "back34": ((0.36, 0.38, 0.2), (0.0, 0.0, 0.0), 60, False),
    "grip": ((-0.45, -0.12, 0.08), (-0.02, -0.03, 0.0), 60, False),
}
for v in views or ["front", "hero", "rear", "top", "side", "back34"]:
    pos, tgt, sz, ortho = V[v]
    cam.data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam.data.ortho_scale = sz
        cam.data.dof.use_dof = False
    else:
        cam.data.lens = sz
        cam.data.dof.use_dof = True
        cam.data.dof.aperture_fstop = 11
        cam.data.dof.focus_distance = (Vector(tgt) - Vector(pos)).length
    cam.location = pos
    cam.rotation_mode = "QUATERNION"
    up = "Y" if v != "top" else "Y"
    cam.rotation_quaternion = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y" if v != "top" else "Y")
    sc.render.filepath = str(out / (v + ".png"))
    bpy.ops.render.render(write_still=True)
    print("rendered", v)
