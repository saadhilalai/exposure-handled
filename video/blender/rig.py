"""Shared helpers for posing the camera model: the exploded view, the iris, the film camera, the crew, rendering.

Imported by shots.py and preview.py inside Blender (they add this folder to sys.path).
"""
import math
from pathlib import Path

import bpy
from mathutils import Euler, Vector

ROOT = Path(__file__).resolve().parents[2]
BLEND = ROOT / "video" / "blender" / "cache" / "camera.blend"
D, C = bpy.data, bpy.context
LX, LZ = 0.008, -0.002
MOUNT_FACE = -0.0265


def use_gpu():
    """Pick the GPU: Metal on the Mac; OptiX on the PC (RTX 3080), falling back to CUDA. BLENDER_DEVICE (OPTIX, CUDA,
    METAL, CPU) forces one. Turns on that type's GPUs only, and says what it's using."""
    import os
    import sys
    pr = C.preferences.addons["cycles"].preferences
    forced = os.environ.get("BLENDER_DEVICE", "").upper()
    order = [forced] if forced else (["METAL"] if sys.platform == "darwin" else ["OPTIX", "CUDA"])
    for kind in order:
        if kind == "CPU":
            break
        try:
            pr.compute_device_type = kind
        except TypeError:                                # this build doesn't offer it (e.g. METAL on Linux)
            print("GPU: %s not available in this Blender" % kind, flush=True)
            continue
        pr.get_devices()
        gpus = [d for d in pr.devices if d.type == kind]
        if not gpus:
            print("GPU: no %s device found" % kind, flush=True)
            continue
        for d in pr.devices:
            d.use = d.type == kind
        C.scene.cycles.device = "GPU"
        print("DEVICE: %s (%s)" % (kind, ", ".join(d.name for d in gpus)), flush=True)
        return kind
    pr.compute_device_type = "NONE"
    C.scene.cycles.device = "CPU"
    print("DEVICE: CPU (no GPU found: this will be slow)", flush=True)
    return "CPU"


def load():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    use_gpu()


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def smooth(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_io(x, p=3.0):
    x = clamp(x)
    return 0.5 * (2 * x) ** p if x < 0.5 else 1 - 0.5 * (2 * (1 - x)) ** p


def parts():
    return [o for o in D.objects if "ex" in o.keys()]


def explode(e, spin=1.0):
    """0 = assembled, 1 = fully exploded. Each part starts after its own delay and eases out (a soft landing)."""
    for o in parts():
        d = o["exd"]
        k = clamp((e - d) / max(1e-6, 1.0 - d)) if e > 0 else 0.0
        k = 1 - (1 - k) ** 3 if e <= 1 else k
        b, ex, br, er = Vector(o["base"]), Vector(o["ex"]), Vector(o["base_rot"]), Vector(o["exr"])
        o.location = b + ex * k
        o.rotation_euler = Euler(br + er * (k * spin))


def key_parts(frame):
    for o in parts():
        o.keyframe_insert("location", frame=frame)
        o.keyframe_insert("rotation_euler", frame=frame)


def iris(fnum):
    a = max(0.0175 * min(1.0, 1.4 / fnum), 0.0012)
    for b in blades():
        b.scale = (0.0085, 0.0252 - a, 0.00015)
        b.location = (0.0, a, b.location.z)
    return a


def blades():
    return sorted([o for o in D.objects if o.name.startswith("iris blade")], key=lambda o: o.name)


def key_iris(frame):
    for b in blades():
        b.keyframe_insert("scale", frame=frame)
        b.keyframe_insert("location", frame=frame)


def world_of(name, local=(0, 0, 0)):
    o = D.objects[name]
    return o.matrix_world @ Vector(local)


def aim(cam_ob, pos, target, roll=0.0):
    pos, target = Vector(pos), Vector(target)
    cam_ob.location = pos
    q = (target - pos).to_track_quat("-Z", "Y")
    if roll:
        from mathutils import Quaternion
        q = q @ Quaternion((0, 0, 1), roll)
    cam_ob.rotation_mode = "QUATERNION"
    cam_ob.rotation_quaternion = q


def film_cam():
    return D.objects["film camera"]


def set_lens(mm=None, fstop=None, focus=None):
    cam = film_cam().data
    if mm is not None:
        cam.lens = mm
    if fstop is not None:
        cam.dof.aperture_fstop = fstop
    if focus is not None:
        cam.dof.focus_distance = focus


def key_cam(frame):
    co = film_cam()
    co.keyframe_insert("location", frame=frame)
    co.keyframe_insert("rotation_quaternion", frame=frame)
    co.data.keyframe_insert("lens", frame=frame)
    co.data.dof.keyframe_insert("focus_distance", frame=frame)
    co.data.dof.keyframe_insert("aperture_fstop", frame=frame)


def linear_keys():
    for a in D.actions:
        for fc in getattr(a, "fcurves", []):
            for k in fc.keyframe_points:
                k.interpolation = "LINEAR"


def quality(res=(3840, 2160), samples=96, scale=100, threshold=0.02):
    sc = C.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = scale
    sc.cycles.samples = samples
    sc.cycles.adaptive_threshold = threshold


def still(path):
    sc = C.scene
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "8"
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
