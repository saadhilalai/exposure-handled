"""Quick look renders of the model from a few angles (small and fast), to judge shapes, materials and light.

Run: Blender -b -P video/blender/preview.py -- [view ...] [--res 960] [--samples 32] [--out DIR]
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
import rig  # noqa: E402
from mathutils import Vector  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = {"--res": "960", "--samples": "32", "--light": "1", "--out": str(rig.ROOT / "video" / "blender" / "out" / "preview")}
views = []
i = 0
while i < len(argv):
    if argv[i] in opts:
        opts[argv[i]] = argv[i + 1]
        i += 2
    else:
        views.append(argv[i])
        i += 1

rig.load()
for L in bpy.data.lights:
    L.energy *= float(opts["--light"])
w = int(opts["--res"])
rig.quality((w, round(w * 9 / 16)), int(opts["--samples"]))
out = Path(opts["--out"])
out.mkdir(parents=True, exist_ok=True)
L = Vector((rig.LX, 0, rig.LZ))


def agent_at(p, rot_z=0.0, name="hero"):
    e = bpy.data.objects.new(name, None)
    e.instance_type = "COLLECTION"
    e.instance_collection = bpy.data.collections["crew proto"]
    bpy.context.scene.collection.objects.link(e)
    e.location = p
    e.rotation_euler = (0, 0, rot_z)
    return e


VIEWS = {
    # name: (explode, iris f, camera pos, target, lens mm, f-stop)
    "hero": (0, 4, (-0.32, -0.46, 0.17), (0.0, -0.02, 0.0), 70, 8),
    "rear": (0, 4, (-0.30, 0.42, 0.20), (0.0, 0.0, 0.0), 70, 8),
    "ports": (0, 4, (0.40, 0.05, 0.10), (0.0, 0.0, 0.0), 70, 8),
    "glass": (0, 2.8, (0.05, -0.32, 0.04), (rig.LX, -0.1, rig.LZ), 100, 5.6),
    "exploded": (1, 4, (0.62, -0.55, 0.30), (0.0, -0.10, 0.0), 50, 11),
    "iris": (1, 5.6, (rig.LX + 0.03, -0.43, rig.LZ + 0.02), (rig.LX, -0.25, rig.LZ), 90, 4),
    "board": (1, 4, (0.08, 0.32, 0.06), (0.02, 0.14, 0.004), 100, 4),
    "agent": (1, 4, None, None, 100, 2.8),
}
for v in views or ["hero", "rear", "ports", "glass", "exploded", "iris", "board", "agent"]:
    e, f, pos, tgt, mm, fs = VIEWS[v]
    rig.explode(e)
    rig.iris(f)
    bpy.context.view_layer.update()
    if v == "agent":
        core = rig.world_of("ai core")
        a = agent_at(core + Vector((0.0, 0.0028, 0.0)))
        a.rotation_euler = (math.pi / 2, 0, math.pi)          # stand on the board, facing the viewer
        tgt = core + Vector((0, 0.003, 0.0))
        pos = tgt + Vector((0.006, 0.024, 0.006))
    cam = rig.film_cam()
    rig.aim(cam, pos, tgt)
    rig.set_lens(mm, fs, (Vector(tgt) - Vector(pos)).length)
    rig.still(out / f"{v}.png")
    print("rendered", v)
