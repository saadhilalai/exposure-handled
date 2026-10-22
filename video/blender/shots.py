"""Render the films' 3D shots from the photoreal camera (cache/camera.blend, made by build_camera.py), path-traced in Cycles.

Each shot is a function of time: it returns where the film camera is, how far the camera model is exploded, the iris,
the crew of orange agents, the lights. The script keys that for every frame (so Cycles can motion-blur it), then
renders the frames to out/<shot>/ and encodes out/<shot>.mp4. Rendering resumes where it stopped (existing frames are
skipped), so a sleep or a crash only costs the frame in progress.

Run (inside Blender):
    Blender -b -P video/blender/shots.py -- SHOT [SHOT ...] [--res 1920] [--spp 24] [--stills 0,1.5,3]
--stills renders just those times (seconds) as PNGs, to check framing before the long render.
"""
import math
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
import rig  # noqa: E402
from mathutils import Euler, Quaternion, Vector  # noqa: E402

D, C = bpy.data, bpy.context
FPS = 24
OUT = rig.ROOT / "video" / "blender" / "out"
L0 = Vector((rig.LX, 0.0, rig.LZ))
BPM = 115.0
B = 60.0 / BPM                       # one beat of the hype film's music, in seconds


# ---------------------------------------------------------------- easing and keys
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def lerp(a, b, t):
    if isinstance(a, (tuple, list)):
        return Vector(a).lerp(Vector(b), t)
    return a + (b - a) * t


EASE = {
    "lin": lambda x: x,
    "io": lambda x: x * x * (3 - 2 * x),
    "out": lambda x: 1 - (1 - x) ** 3,
    "in": lambda x: x ** 3,
    "xout": lambda x: 1 - (1 - x) ** 5,
    "xin": lambda x: x ** 5,
    "xio": lambda x: 16 * x ** 5 if x < 0.5 else 1 - (-2 * x + 2) ** 5 / 2,
    "hold": lambda x: 0.0,
}


def kf(t, keys):
    """Keyframes [(time, value, ease_into_this_key), ...] -> value at t."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0, _), (t1, v1, e) in zip(keys, keys[1:]):
        if t <= t1:
            x = (t - t0) / max(1e-9, t1 - t0)
            return lerp(v0, v1, EASE[e](clamp(x)))
    return keys[-1][1]


def orbit(target, yaw, pitch, dist):
    """A position around target: yaw 0 = straight in front (the -Y side), positive yaw swings toward +X."""
    target = Vector(target)
    return target + Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch))) * dist


# ---------------------------------------------------------------- the crew
class Crew:
    """Instanced orange agents. Each has a work spot on a part (in that part's own coordinates, so it moves with the
    exploded view), hovers there, and can burst out of the AI core, swarm, or freeze."""

    def __init__(self, n, seed=3, kinds=None, scale=1.0):
        self.rng = random.Random(seed)
        self.items = []
        self.spots = self._spots(kinds)
        proto = D.collections["crew proto"]
        for i in range(n):
            e = D.objects.new("crew %03d" % i, None)
            e.instance_type = "COLLECTION"
            e.instance_collection = proto
            C.scene.collection.objects.link(e)
            e.rotation_mode = "QUATERNION"
            r = self.rng
            self.items.append({"ob": e, "spot": self.spots[i % len(self.spots)], "phase": r.uniform(0, math.tau),
                               "orbit": r.uniform(0.0025, 0.007), "speed": r.uniform(1.2, 2.6), "bob": r.uniform(0.0006, 0.0018),
                               "delay": r.uniform(0.0, 0.5), "lane": r.uniform(-1, 1), "s": scale * r.uniform(0.85, 1.15)})

    def _spots(self, kinds):
        """Work spots on the surfaces of the parts that matter (sensor, iris, board, fan, dials, lens elements)."""
        names = kinds or ["sensor package", "iris housing", "main board", "fan housing", "rear dial", "front dial", "element 3",
                          "element 4", "stabiliser plate", "ai core", "aperture ring", "focus ring", "bayonet", "rec ring"]
        spots = []
        r = self.rng
        for nm in names:
            if nm not in D.objects:
                continue
            o = D.objects[nm]
            bb = [Vector(c) for c in o.bound_box]
            lo = Vector((min(c.x for c in bb), min(c.y for c in bb), min(c.z for c in bb)))
            hi = Vector((max(c.x for c in bb), max(c.y for c in bb), max(c.z for c in bb)))
            for _ in range(12):
                p = Vector((r.uniform(lo.x, hi.x), r.uniform(lo.y, hi.y), r.uniform(lo.z, hi.z)))
                ax = r.randrange(3)
                p[ax] = lo[ax] if r.random() < 0.5 else hi[ax]           # on a face of the part's box
                spots.append((o, p, ax, 1 if p[ax] == hi[ax] else -1))
        r.shuffle(spots)
        return spots

    def spot_world(self, a):
        o, p, ax, sgn = a["spot"]
        n = Vector((0, 0, 0))
        n[ax] = sgn
        w = o.matrix_world
        nw = (w.to_3x3() @ n).normalized()
        return w @ p + nw * 0.0028, nw

    def place(self, t, mode="work", vis=1.0, burst_t0=None, freeze_t=None, swarm_c=None, swarm_r=0.25, speed=1.0, count=None):
        core = D.objects["ai core"].matrix_world.translation
        tt = t if freeze_t is None else min(t, freeze_t)
        for i, a in enumerate(self.items):
            e = a["ob"]
            on = count is None or i < count
            home, nrm = self.spot_world(a)
            ph = a["phase"] + tt * a["speed"] * speed
            hover = home + Vector((math.cos(ph) * a["orbit"], math.sin(ph * 0.7) * a["orbit"] * 0.6, math.sin(ph * 1.3) * a["bob"]))
            if mode == "swarm":
                c = Vector(swarm_c)
                u = ph * 0.6 + a["lane"]
                p = c + Vector((math.cos(u) * swarm_r * (0.6 + 0.4 * math.sin(a["phase"])), math.sin(u * 1.3) * swarm_r * 0.9,
                                math.sin(u * 0.9 + a["phase"]) * swarm_r * 0.35))
                p = p.lerp(hover, 0.25)
            else:
                p = hover
            if burst_t0 is not None:
                k = clamp((t - burst_t0 - a["delay"] * 0.6) / 0.7)
                k = 1 - (1 - k) ** 3
                p = core.lerp(p, k)
                on = on and t >= burst_t0 + a["delay"] * 0.6 - 0.02
            # face along the motion (look a little ahead)
            ph2 = ph + 0.15
            ahead = home + Vector((math.cos(ph2) * a["orbit"], math.sin(ph2 * 0.7) * a["orbit"] * 0.6, 0))
            d = (ahead - hover)
            if d.length < 1e-7:
                d = Vector((0, -1, 0))
            q = d.to_track_quat("-Y", "Z")
            e.location = p
            e.rotation_quaternion = q
            s = a["s"] * vis if on else 0.0
            e.scale = (s, s, s)

    def key(self, f):
        for a in self.items:
            e = a["ob"]
            e.keyframe_insert("location", frame=f)
            e.keyframe_insert("rotation_quaternion", frame=f)
            e.keyframe_insert("scale", frame=f)


def hero_agent(name="hero"):
    """A real (not instanced) copy of the agent, so its arms can move: returns (root, [(shoulder, elbow) x2])."""
    proto = D.collections["crew proto"]
    mp = {}
    for o in proto.objects:
        c = o.copy()
        if o.data:
            c.data = o.data
        C.scene.collection.objects.link(c)
        mp[o] = c
    for o, c in mp.items():
        c.parent = mp.get(o.parent)
    root = [c for o, c in mp.items() if o.parent is None][0]
    root.name = name
    sh = sorted([c for o, c in mp.items() if "shoulder" in o.name], key=lambda o: o.location.x)
    el = sorted([c for o, c in mp.items() if "elbow" in o.name and "joint" not in o.name], key=lambda o: o.matrix_local.translation.x)
    root.rotation_mode = "QUATERNION"
    return root, list(zip(sh, el))


# ---------------------------------------------------------------- materials over time
def freeze_mats(k):
    """k = 0: the crew's usual orange; k = 1: frozen red, thrusters out (the kill switch)."""
    red = (1.0, 0.06, 0.04)
    for nm, base, strength in (("agent thruster", (1.0, 0.45, 0.12), 12.0), ("agent tip", (1.0, 0.75, 0.45), 8.0),
                               ("ai glow", (1.0, 0.30, 0.045), 6.0), ("ai trace", (1.0, 0.30, 0.045), 2.5)):
        p = D.materials[nm].node_tree.nodes["Principled BSDF"]
        p.inputs["Emission Color"].default_value = (*lerp(base, red, k), 1)
        p.inputs["Emission Strength"].default_value = strength * (1 - 0.55 * k)
    p = D.materials["agent shell"].node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*lerp((1.0, 0.30, 0.045), (0.75, 0.03, 0.02), k), 1)
    p = D.materials["agent visor"].node_tree.nodes["Principled BSDF"]
    p.inputs["Emission Color"].default_value = (*lerp((1.0, 0.55, 0.2), red, k), 1)


def key_freeze(f):
    for nm in ("agent thruster", "agent tip", "ai glow", "ai trace", "agent visor"):
        p = D.materials[nm].node_tree.nodes["Principled BSDF"]
        p.inputs["Emission Color"].keyframe_insert("default_value", frame=f)
        p.inputs["Emission Strength"].keyframe_insert("default_value", frame=f)
    D.materials["agent shell"].node_tree.nodes["Principled BSDF"].inputs["Base Color"].keyframe_insert("default_value", frame=f)


def histogram(t, f):
    nz = D.materials["agent visor"].node_tree.nodes["histogram"]
    nz.inputs["W"].default_value = t * 2.2
    nz.inputs["W"].keyframe_insert("default_value", frame=f)


def lights(**k):
    """Scale lights by name: lights(key=1.0, rim_left=2.0, ...)."""
    names = {"key": "key softbox", "top": "top strip", "rim_left": "rim left", "rim_right": "rim right", "floor": "floor bounce",
             "card": "lens card", "glow": "crew glow"}
    for short, v in k.items():
        L = D.objects[names[short]]
        if "e0" not in L.keys():
            L["e0"] = L.data.energy
        L.data.energy = L["e0"] * v if short != "glow" else v


def key_lights(f):
    for L in D.objects:
        if L.type == "LIGHT":
            L.data.keyframe_insert("energy", frame=f)
            L.keyframe_insert("location", frame=f)


# ---------------------------------------------------------------- the shots
# Each returns {"dur": seconds, "setup": fn(), "at": fn(t, ctx) -> None (poses everything for time t)}
SHOTS = {}


def shot(name, dur, blur=True, spp=None):
    def deco(fn):
        SHOTS[name] = {"dur": dur, "fn": fn, "blur": blur, "spp": spp}
        return fn
    return deco


def cam(pos, target, mm, fstop, focus=None, roll=0.0):
    co = rig.film_cam()
    rig.aim(co, pos, target, roll)
    rig.set_lens(mm, fstop, focus if focus is not None else (Vector(target) - Vector(pos)).length)


def sweep_light():
    """A narrow moving strip for light sweeps across the body (made on first use)."""
    if "sweep" in D.objects:
        return D.objects["sweep"]
    L = D.lights.new("sweep", "AREA")
    L.shape, L.size, L.size_y, L.energy = "RECTANGLE", 0.02, 1.4, 0.0
    o = D.objects.new("sweep", L)
    C.scene.collection.objects.link(o)
    o.visible_camera = False
    return o


def aim_light(o, pos, target):
    o.location = pos
    o.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()


# --- the hype film (V2): beats of "Beast", 115 BPM ---------------------------------------------------------------
@shot("h_reveal", 4 * B)
def h_reveal(t, X):
    """Black. A hard strip of light rakes across the top edge and the lens: the silhouette appears. Slow push."""
    b = t / B
    rig.explode(0)
    rig.iris(4)
    lights(key=0.0, top=0.0, rim_left=kf(b, [(0, 0.0, "lin"), (0.5, 0.0, "lin"), (4, 2.0, "io")]),
           rim_right=kf(b, [(0, 0.0, "lin"), (2.0, 0.0, "lin"), (4, 1.6, "io")]), floor=0.0, card=kf(b, [(0, 0.0, "lin"), (2.5, 0.0, "lin"), (4, 0.5, "io")]))
    sw = sweep_light()
    sw.data.energy = 9.0
    x = kf(b, [(0, -0.7, "lin"), (4, 0.7, "io")])
    aim_light(sw, (x, 0.05, 0.6), (x * 0.15, -0.02, 0.0))
    pos = orbit((0.0, -0.03, 0.005), kf(b, [(0, -0.58, "lin"), (4, -0.5, "lin")]), 0.08, kf(b, [(0, 0.42, "lin"), (4, 0.36, "lin")]))
    cam(pos, (0.0, -0.035, 0.004), 50, 5.6)


@shot("h_dial", 1.5 * B)
def h_dial(t, X):
    """Macro: the rear dial's knurling turns past, razor-thin focus."""
    rig.explode(0)
    lights(key=0.15, top=0.0, rim_left=1.6, rim_right=1.2, card=0.1)
    d = D.objects["rear dial"]
    d.rotation_euler = Euler((0, 0, t * 1.6))
    c = rig.world_of("rear dial")
    pos = c + Vector((kf(t, [(0, 0.03, "lin"), (1.5 * B, 0.012, "lin")]), 0.07, 0.006))
    cam(pos, c + Vector((0.0, 0.006, 0.001)), 100, 4.0)


@shot("h_vents", 1.5 * B)
def h_vents(t, X):
    """Macro slide along the vents and ports on the side."""
    rig.explode(0)
    lights(key=0.2, top=0.6, rim_left=0.3, rim_right=2.4, card=0.2)
    y = kf(t, [(0, -0.004, "lin"), (1.5 * B, 0.022, "lin")])
    pos = Vector((0.13, y - 0.03, 0.03))
    cam(pos, Vector((0.064, y, 0.004)), 85, 4.0)


@shot("h_ring", 1.5 * B)
def h_ring(t, X):
    """The orange ring at the mount, rack focus from the grip edge onto the ring."""
    rig.explode(0)
    lights(key=0.7, top=1.0, rim_left=1.0, rim_right=1.0, card=0.6)
    a = kf(t, [(0, -0.35, "lin"), (1.5 * B, -0.15, "lin")])
    tgt = Vector((rig.LX - 0.022, -0.0255, rig.LZ + 0.02))
    pos = orbit(tgt, a, 0.16, 0.09)
    cam(pos, tgt, 100, 2.8, focus=kf(t, [(0, 0.06, "lin"), (0.4 * B, 0.06, "lin"), (1.1 * B, 0.09, "io")]))


@shot("h_eye", 2 * B)
def h_eye(t, X):
    """Head-on into the lens: the coatings glint, the iris inside closes a stop on the cut."""
    rig.explode(0)
    rig.iris(kf(t, [(0, 2.0, "lin"), (1.0 * B, 2.0, "lin"), (1.2 * B, 5.6, "xout")]))
    lights(key=0.4, top=1.2, rim_left=1.0, rim_right=1.0, card=0.7)
    d = kf(t, [(0, 0.24, "lin"), (2 * B, 0.17, "lin")])
    pos = Vector((rig.LX + 0.012, -0.11 - d, rig.LZ + 0.02))
    cam(pos, Vector((rig.LX, -0.10, rig.LZ)), 85, 4.0, focus=d + 0.005)


@shot("h_orbit", 4 * B)
def h_orbit(t, X):
    """A fast whip orbit around the whole camera that settles into a slow drift; hard rim light."""
    b = t / B
    rig.explode(0)
    rig.iris(4)
    lights(key=0.55, top=1.0, rim_left=1.8, rim_right=1.6, card=0.5)
    yaw = kf(b, [(0, 1.6, "lin"), (1.4, 0.55, "xout"), (4, 0.42, "lin")])
    pos = orbit((0.0, -0.03, 0.0), yaw, kf(b, [(0, 0.35, "lin"), (1.4, 0.16, "xout"), (4, 0.13, "lin")]),
                kf(b, [(0, 0.5, "lin"), (1.4, 0.44, "xout"), (4, 0.42, "lin")]))
    cam(pos, (0.0, -0.035, 0.0), 50, 8.0)


@shot("h_smash", 4 * B)
def h_smash(t, X):
    """The smash zoom: from a three-quarter view straight down the lens axis into the glass, accelerating."""
    b = t / B
    rig.explode(0)
    rig.iris(kf(b, [(0, 4.0, "lin"), (3.0, 4.0, "lin"), (3.8, 1.4, "xout")]))
    lights(key=0.7, top=1.2, rim_left=1.2, rim_right=1.2, card=1.4)
    yaw = kf(b, [(0, 0.5, "lin"), (2.0, 0.18, "io"), (4, 0.0, "in")])
    dist = kf(b, [(0, 0.55, "lin"), (2.0, 0.36, "io"), (3.4, 0.16, "in"), (4, 0.085, "in")])
    tgt = Vector((rig.LX, -0.10, rig.LZ))
    pos = orbit(tgt, yaw, kf(b, [(0, 0.12, "lin"), (4, 0.0, "io")]), dist)
    cam(pos, tgt, kf(b, [(0, 50, "lin"), (4, 35, "in")]), 4.0, focus=dist)


@shot("h_burst", 8 * B)
def h_burst(t, X):
    """THE DROP. The body blows apart in slow motion, the crew bursts out of the AI core, the camera swings round."""
    b = t / B
    # time warp: almost frozen for the first beat and a half (slow motion), then real speed
    e = kf(b, [(0, 0.0, "lin"), (0.15, 0.55, "xout"), (2.0, 0.8, "lin"), (5.0, 0.97, "io"), (8, 1.0, "lin")])
    rig.explode(e)
    rig.iris(5.6)
    lights(key=0.6, top=0.8, rim_left=1.6, rim_right=1.6, card=0.4,
           glow=kf(b, [(0, 0.0, "lin"), (0.3, 3.0, "xout"), (3, 0.8, "io")]))
    gl = D.objects["crew glow"]
    gl.location = D.objects["ai core"].matrix_world.translation
    tw = kf(b, [(0, 0.0, "lin"), (2.0, 0.25, "lin"), (8, 3.6, "in")])        # the crew's own clock (slow-mo, then fast)
    X["crew"].place(tw, burst_t0=0.05)
    yaw = kf(b, [(0, 0.42, "lin"), (2.0, 0.55, "lin"), (8, 1.15, "io")])
    tgt = Vector((0.0, kf(b, [(0, -0.05, "lin"), (8, -0.03, "io")]), 0.0))
    pos = orbit(tgt, yaw, kf(b, [(0, 0.06, "lin"), (8, 0.2, "io")]), kf(b, [(0, 0.46, "lin"), (2, 0.58, "out"), (8, 0.82, "io")]))
    cam(pos, tgt, 45, kf(b, [(0, 4.0, "lin"), (8, 8.0, "lin")]))


def _setup_burst(X):
    X["crew"] = Crew(160, seed=5)


SHOTS["h_burst"]["setup"] = _setup_burst


@shot("h_iris", 4 * B)
def h_iris(t, X):
    """Inside the lens: the iris snaps on each beat (f/11, f/8, f/4, f/2.8), the camera pushes through the opening."""
    b = t / B
    rig.explode(1.0)
    fs = kf(b, [(0, 11, "lin"), (0.9, 11, "lin"), (1.0, 8, "xout"), (1.9, 8, "lin"), (2.0, 4, "xout"), (2.9, 4, "lin"), (3.0, 2.0, "xout")])
    rig.iris(fs)
    lights(key=0.6, top=0.8, rim_left=1.5, rim_right=1.5, card=0.8, glow=0.35)
    ir = D.objects["iris"].matrix_world.translation
    X["crew"].place(t * 1.5, count=24)
    gl = D.objects["crew glow"]
    gl.location = ir + Vector((0.012, -0.012, 0.02))
    z = kf(b, [(0, 0.034, "lin"), (3.0, 0.026, "io"), (4, 0.002, "xin")])
    side = kf(b, [(0, 1.0, "lin"), (3.0, 0.55, "io"), (4, 0.0, "in")])
    pos = ir + Vector((0.016 * side, -z, 0.01 * side))
    cam(pos, ir + Vector((0, 0.01, 0)), 35, 4.0, focus=(Vector((0.016 * side, -z, 0.01 * side))).length)


def _setup_iris(X):
    X["crew"] = Crew(24, seed=8, kinds=["iris housing", "element 3", "element 4"])


SHOTS["h_iris"]["setup"] = _setup_iris


@shot("h_agent", 4 * B)
def h_agent(t, X):
    """Deep into one agent at the sensor: the visor's histogram dances, it reaches out and touches the sensor frame,
    a scan line sweeps the die; it turns to us."""
    b = t / B
    rig.explode(1.0)
    rig.iris(4)
    lights(key=0.5, top=0.4, rim_left=1.4, rim_right=1.2, card=0.3, glow=0.0)
    die = D.objects["sensor die"]
    dw = die.matrix_world
    centre = dw.translation
    hero, arms = X["hero"]
    hero.location = centre + Vector((0.004, -0.0058, 0.002))
    look = kf(b, [(0, 0.0, "lin"), (2.6, 0.0, "lin"), (3.3, 0.85, "io")])
    toward_die = Vector((0, 1, 0))
    toward_us = (rig.film_cam().location - hero.location).normalized()
    fwd = toward_die.lerp(toward_us, look).normalized()
    hero.rotation_quaternion = (-fwd).to_track_quat("Y", "Z")
    hero.location.z += 0.0003 * math.sin(t * 5.0)
    reach = kf(b, [(0, 0.0, "lin"), (0.8, 0.0, "lin"), (1.4, 1.0, "out"), (2.4, 1.0, "lin"), (2.9, 0.0, "io")])
    for i, (sh, el) in enumerate(arms):
        sh.rotation_euler = Euler((-1.1 * reach * (1 if i == 1 else 0.3) + 0.15 * math.sin(t * 3 + i), 0, 0))
        el.rotation_euler = Euler((-0.6 * reach * (1 if i == 1 else 0.4), 0, 0))
    histogram(t, X["f"])
    scan = X["scan"]
    sx = kf(b, [(0, -0.018, "lin"), (1.0, -0.018, "lin"), (3.0, 0.018, "io")])
    scan.location = centre + Vector((sx, -0.0004, 0))
    scan.scale = (1, 1, 1) if 1.0 < b < 3.05 else (0, 0, 0)
    tgt = hero.location + Vector((0.0, 0.0012, 0.0003))
    pos = tgt + Vector((kf(b, [(0, 0.042, "lin"), (4, 0.03, "io")]), kf(b, [(0, -0.022, "lin"), (4, -0.016, "io")]), 0.006))
    cam(pos, tgt, 100, 11.0, focus=(hero.location - pos).length)


def _setup_agent(X):
    X["hero"] = hero_agent()
    for o in D.objects:
        if o.parent is None and o.type == "EMPTY" and o.name.startswith("hero"):
            o.rotation_mode = "QUATERNION"
    me = D.meshes.new("scan")
    me.from_pydata([(0, 0, -0.0125), (0, 0, 0.0125), (0.00025, 0, 0.0125), (0.00025, 0, -0.0125)], [], [(0, 1, 2, 3)])
    sc = D.objects.new("scan", me)
    C.scene.collection.objects.link(sc)
    me.materials.append(D.materials["ai glow"])
    X["scan"] = sc
    X["crew"] = Crew(14, seed=11, kinds=["sensor package", "stabiliser plate"])


SHOTS["h_agent"]["setup"] = _setup_agent


@shot("h_swarm", 4 * B)
def h_swarm(t, X):
    """The whole exploded camera with the crew racing round it at full speed."""
    b = t / B
    rig.explode(1.0)
    rig.iris(4)
    lights(key=0.55, top=0.7, rim_left=1.6, rim_right=1.5, card=0.3, glow=1.2)
    D.objects["crew glow"].location = D.objects["ai core"].matrix_world.translation
    D.objects["fan rotor"].rotation_euler = Euler((0, math.pi / 2, t * 40))
    X["crew"].place(t * 3.2 + 2.0, mode="swarm", swarm_c=(0.0, -0.05, 0.0), swarm_r=0.2, speed=1.0)
    yaw = kf(b, [(0, -0.9, "lin"), (4, -0.45, "lin")])
    tgt = Vector((0.0, -0.06, 0.0))
    pos = orbit(tgt, yaw, 0.18, kf(b, [(0, 0.85, "lin"), (4, 0.72, "lin")]))
    cam(pos, tgt, 40, 8.0)


SHOTS["h_swarm"]["setup"] = lambda X: X.update(crew=Crew(200, seed=9))


@shot("h_kill", 4 * B)
def h_kill(t, X):
    """The kill switch: on the beat the crew stops dead and goes red, the thrusters die. The camera barely moves."""
    b = t / B
    rig.explode(1.0)
    rig.iris(4)
    k = kf(b, [(0, 0.0, "lin"), (1.0, 0.0, "lin"), (1.12, 1.0, "xout")])
    freeze_mats(k)
    key_freeze(X["f"])
    lights(key=0.5, top=0.6, rim_left=1.4, rim_right=1.3, card=0.3, glow=1.0 * (1 - k))
    D.objects["crew glow"].location = D.objects["ai core"].matrix_world.translation
    X["crew"].place(t * 3.2 + 9.0, mode="swarm", swarm_c=(0.0, -0.05, 0.0), swarm_r=0.2, freeze_t=1.0 * B * 3.2 + 9.0)
    tgt = Vector((0.0, -0.05, 0.0))
    pos = orbit(tgt, kf(b, [(0, -0.2, "lin"), (1.0, -0.17, "lin"), (4, -0.165, "out")]), 0.12,
                kf(b, [(0, 0.6, "lin"), (1.0, 0.56, "lin"), (4, 0.555, "out")]))
    cam(pos, tgt, 40, 8.0)


SHOTS["h_kill"]["setup"] = lambda X: X.update(crew=Crew(200, seed=9))


@shot("h_slam", 8 * B)
def h_slam(t, X):
    """The parts drift in slow motion, then slam home on the beat (2 beats in), a flash and a shake, then the hero turn."""
    b = t / B
    e = kf(b, [(0, 0.9, "lin"), (1.6, 0.78, "lin"), (2.0, 0.0, "in")])
    rig.explode(e)
    rig.iris(4)
    flash = math.exp(-max(0.0, b - 2.0) / 0.25) if b >= 2.0 else 0.0
    lights(key=0.6 + 2.0 * flash, top=0.9 + 2.0 * flash, rim_left=1.6, rim_right=1.6, card=0.5 + 1.5 * flash)
    sh = math.exp(-max(0.0, b - 2.0) / 0.3) if b >= 2.0 else 0.0
    jit = Vector((math.sin(t * 90) * 0.004 * sh, 0, math.cos(t * 77) * 0.003 * sh))
    yaw = kf(b, [(0, 1.1, "lin"), (2.0, 0.85, "lin"), (8, 0.42, "out")])
    tgt = Vector((0.0, -0.03, 0.0))
    pos = orbit(tgt, yaw, kf(b, [(0, 0.2, "lin"), (8, 0.1, "io")]), kf(b, [(0, 0.75, "lin"), (2.0, 0.6, "in"), (8, 0.46, "out")])) + jit
    cam(pos, tgt, 50, 8.0)


@shot("h_title", 8 * B)
def h_title(t, X):
    """The hero, turning slowly in the dark under the title; leave the upper third for the type."""
    b = t / B
    rig.explode(0)
    rig.iris(4)
    lights(key=0.55, top=1.0, rim_left=1.7, rim_right=1.5, card=0.6)
    yaw = kf(b, [(0, 0.55, "lin"), (8, 0.25, "lin")])
    tgt = Vector((0.0, -0.03, 0.022))
    pos = orbit(tgt, yaw, 0.12, 0.5)
    cam(pos, tgt, 50, 8.0)


# --- the abstract film (V1): calm, slow -----------------------------------------------------------------------------
@shot("a_form", 9.0)
def a_form(t, X):
    """Particles of light drift in the dark, then gather into the camera's shape. (The solid camera fades in in the edit.)"""
    lights(key=0.0, top=0.0, rim_left=0.0, rim_right=0.0, floor=0.0, card=0.0)
    yaw = kf(t, [(0, -0.75, "lin"), (9, -0.35, "io")])
    tgt = Vector((0.0, -0.03, 0.0))
    pos = orbit(tgt, yaw, kf(t, [(0, 0.3, "lin"), (9, 0.16, "io")]), kf(t, [(0, 0.95, "lin"), (9, 0.52, "io")]))
    cam(pos, tgt, 50, 5.6)


@shot("a_solid", 9.0)
def a_solid(t, X):
    """The same move as a_form, the real camera: crossfaded in over the particles in the edit."""
    rig.explode(0)
    rig.iris(4)
    lights(key=0.7, top=0.8, rim_left=1.2, rim_right=1.0, card=0.6)
    yaw = kf(t, [(0, -0.75, "lin"), (9, -0.35, "io")])
    tgt = Vector((0.0, -0.03, 0.0))
    pos = orbit(tgt, yaw, kf(t, [(0, 0.3, "lin"), (9, 0.16, "io")]), kf(t, [(0, 0.95, "lin"), (9, 0.52, "io")]))
    cam(pos, tgt, 50, 5.6)


@shot("a_open", 8.0)
def a_open(t, X):
    """The camera opens slowly, like a flower; the crew glows inside like fireflies. Soft light, lots of space."""
    rig.explode(kf(t, [(0, 0.0, "lin"), (6.5, 1.0, "io")]), spin=0.6)
    rig.iris(4)
    lights(key=0.6, top=0.6, rim_left=1.0, rim_right=0.9, card=0.3, glow=kf(t, [(0, 0.0, "lin"), (3, 0.0, "lin"), (6, 0.6, "io")]))
    D.objects["crew glow"].location = D.objects["ai core"].matrix_world.translation
    X["crew"].place(t * 0.6, burst_t0=3.2, speed=0.5)
    yaw = kf(t, [(0, 0.55, "lin"), (8, 0.95, "io")])
    tgt = Vector((0.0, kf(t, [(0, -0.03, "lin"), (8, -0.06, "io")]), 0.0))
    pos = orbit(tgt, yaw, 0.12, kf(t, [(0, 0.5, "lin"), (8, 0.85, "io")]))
    cam(pos, tgt, 45, 8.0)


SHOTS["a_open"]["setup"] = lambda X: X.update(crew=Crew(90, seed=21))


@shot("a_agent", 7.0)
def a_agent(t, X):
    """One agent, close: it looks at the sensor, the histogram in its visor moves, it makes a small adjustment."""
    rig.explode(1.0)
    rig.iris(4)
    lights(key=0.6, top=0.4, rim_left=1.2, rim_right=1.0, card=0.3, glow=0.2)
    die = D.objects["sensor die"]
    centre = die.matrix_world.translation
    hero, arms = X["hero"]
    hero.location = centre + Vector((-0.003, -0.0062, 0.001 + 0.0002 * math.sin(t * 2.0)))
    hero.rotation_quaternion = Vector((0, -1, 0)).to_track_quat("Y", "Z") @ Quaternion((0, 0, 1), 0.25 * math.sin(t * 0.6))
    reach = kf(t, [(0, 0.0, "lin"), (2.5, 0.0, "lin"), (3.5, 1.0, "io"), (5.0, 1.0, "lin"), (6.0, 0.0, "io")])
    for i, (sh, el) in enumerate(arms):
        sh.rotation_euler = Euler((-1.0 * reach * (1 if i == 0 else 0.25), 0, 0))
        el.rotation_euler = Euler((-0.5 * reach * (1 if i == 0 else 0.3), 0, 0))
    histogram(t * 0.5, X["f"])
    tgt = hero.location.copy()
    pos = tgt + Vector((kf(t, [(0, 0.012, "lin"), (7, 0.007, "io")]), kf(t, [(0, -0.028, "lin"), (7, -0.02, "io")]), 0.003))
    cam(pos, tgt, 100, 2.8)


SHOTS["a_agent"]["setup"] = lambda X: X.update(hero=hero_agent("hero calm"), crew=Crew(10, seed=12, kinds=["sensor package"]))


@shot("a_close", 8.0)
def a_close(t, X):
    """The camera closes again, gently, and the light settles on it: the end frame (title above)."""
    rig.explode(kf(t, [(0, 0.55, "lin"), (5.5, 0.0, "io")]), spin=0.6)
    rig.iris(4)
    lights(key=0.6, top=0.8, rim_left=1.3, rim_right=1.1, card=0.5)
    yaw = kf(t, [(0, 0.75, "lin"), (8, 0.4, "io")])
    tgt = Vector((0.0, -0.03, 0.03))
    pos = orbit(tgt, yaw, 0.12, kf(t, [(0, 0.72, "lin"), (8, 0.62, "io")]))
    cam(pos, tgt, 50, 8.0)


# --- the story film (V3) --------------------------------------------------------------------------------------------
@shot("s_catch", 4.0)
def s_catch(t, X):
    """Inside the camera at the moment the light drops: the crew turns as one, the iris opens two stops."""
    rig.explode(1.0)
    rig.iris(kf(t, [(0, 8.0, "lin"), (1.2, 8.0, "lin"), (2.0, 2.8, "xout")]))
    lights(key=0.5, top=0.5, rim_left=1.3, rim_right=1.2, card=0.6, glow=0.8)
    ir = D.objects["iris"].matrix_world.translation
    D.objects["crew glow"].location = ir + Vector((0.0, 0.0, 0.03))
    X["crew"].place(t * kf(t, [(0, 0.5, "lin"), (1.2, 0.5, "lin"), (1.6, 3.0, "out")]) if False else t, speed=kf(t, [(0, 0.5, "lin"), (1.3, 2.5, "out")]))
    tgt = ir
    pos = orbit(tgt, kf(t, [(0, 0.45, "lin"), (4, 0.3, "io")]), 0.2, kf(t, [(0, 0.12, "lin"), (4, 0.09, "io")]))
    cam(pos, tgt, 60, 4.0)


SHOTS["s_catch"]["setup"] = lambda X: X.update(crew=Crew(30, seed=31, kinds=["iris housing", "element 3", "element 4", "aperture ring"]))


@shot("s_hero", 6.0)
def s_hero(t, X):
    """The camera, assembled, very slow push in warm-and-cool light: the end frame for the story."""
    rig.explode(0)
    rig.iris(2.8)
    lights(key=0.55, top=0.8, rim_left=1.6, rim_right=1.0, card=0.6)
    yaw = kf(t, [(0, -0.42, "lin"), (6, -0.3, "io")])
    tgt = Vector((0.0, -0.03, 0.025))
    pos = orbit(tgt, yaw, 0.1, kf(t, [(0, 0.66, "lin"), (6, 0.58, "io")]))
    cam(pos, tgt, 50, 8.0)


# ---------------------------------------------------------------- particles (V1)
def make_dust(n=26000, seed=4):
    """Points sampled on the camera's visible surfaces, each with a scattered start point and a delay; a geometry-nodes
    modifier moves them from start to surface as its 'time' input grows, and draws each as a tiny glowing bead."""
    rng = random.Random(seed)
    tris = []
    dg = C.evaluated_depsgraph_get()
    rig.explode(0)
    C.view_layer.update()
    for o in D.collections["camera"].all_objects:
        if o.type != "MESH" or o.hide_render:
            continue
        if any(s in o.name for s in ("tube", "baffle", "small parts", "trace", "bond", "cutter", "socket", "floor", "hole")):
            continue
        me = o.evaluated_get(dg).to_mesh()
        me.calc_loop_triangles()
        mw = o.matrix_world
        for lt in me.loop_triangles:
            a, b, c = (mw @ me.vertices[i].co for i in lt.vertices)
            area = (b - a).cross(c - a).length / 2
            if area > 0:
                tris.append((area, a, b, c))
        o.evaluated_get(dg).to_mesh_clear()
    total = sum(t[0] for t in tris)
    pts, starts, delays = [], [], []
    acc = []
    s = 0.0
    for t in tris:
        s += t[0]
        acc.append(s)
    import bisect
    for i in range(n):
        k = bisect.bisect_left(acc, rng.random() * total)
        _, a, b, c = tris[min(k, len(tris) - 1)]
        u, v = rng.random(), rng.random()
        if u + v > 1:
            u, v = 1 - u, 1 - v
        p = a + (b - a) * u + (c - a) * v
        pts.append(p)
        d = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 0.6))).normalized() * rng.uniform(0.25, 1.1)
        starts.append(p + d + Vector((0, 0, rng.uniform(-0.05, 0.15))))
        delays.append(rng.uniform(0.0, 3.2) + (p.y + 0.12) * 4.0)      # the lens forms first, then the body
    me = D.meshes.new("dust")
    me.from_pydata([tuple(p) for p in pts], [], [])
    at = me.attributes.new("start", "FLOAT_VECTOR", "POINT")
    at.data.foreach_set("vector", [c for p in starts for c in p])
    dl = me.attributes.new("delay", "FLOAT", "POINT")
    dl.data.foreach_set("value", delays)
    ob = D.objects.new("dust", me)
    C.scene.collection.objects.link(ob)
    ng = dust_nodes()
    m = ob.modifiers.new("form", "NODES")
    m.node_group = ng
    return ob


def dust_nodes():
    ng = D.node_groups.new("dust form", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N = ng.nodes
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    clock = N.new("GeometryNodeInputSceneTime")                     # seconds = frame / fps: the shot's own clock
    st = N.new("GeometryNodeInputNamedAttribute")
    st.data_type = "FLOAT_VECTOR"
    st.inputs["Name"].default_value = "start"
    dl = N.new("GeometryNodeInputNamedAttribute")
    dl.data_type = "FLOAT"
    dl.inputs["Name"].default_value = "delay"
    pos = N.new("GeometryNodeInputPosition")
    sub = N.new("ShaderNodeMath")
    sub.operation = "SUBTRACT"
    ng.links.new(clock.outputs["Seconds"], sub.inputs[0])
    ng.links.new(dl.outputs["Attribute"], sub.inputs[1])
    div = N.new("ShaderNodeMath")
    div.operation = "DIVIDE"
    div.inputs[1].default_value = 2.6
    div.use_clamp = True
    ng.links.new(sub.outputs["Value"], div.inputs[0])
    sm = N.new("ShaderNodeMapRange")
    sm.interpolation_type = "SMOOTHERSTEP"
    ng.links.new(div.outputs["Value"], sm.inputs["Value"])
    mix = N.new("ShaderNodeMix")
    mix.data_type = "VECTOR"
    ng.links.new(sm.outputs["Result"], mix.inputs["Factor"])
    ng.links.new(st.outputs["Attribute"], mix.inputs[4])
    ng.links.new(pos.outputs["Position"], mix.inputs[5])
    # a slow drift on top while they travel (fades out as they land)
    nz = N.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "4D"
    nz.inputs["Scale"].default_value = 3.0
    ng.links.new(clock.outputs["Seconds"], nz.inputs["W"])
    ng.links.new(st.outputs["Attribute"], nz.inputs["Vector"])
    cen = N.new("ShaderNodeVectorMath")
    cen.operation = "SUBTRACT"
    cen.inputs[1].default_value = (0.5, 0.5, 0.5)
    ng.links.new(nz.outputs["Color"], cen.inputs[0])
    inv = N.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    ng.links.new(sm.outputs["Result"], inv.inputs[1])
    amt = N.new("ShaderNodeMath")
    amt.operation = "MULTIPLY"
    amt.inputs[1].default_value = 0.12
    ng.links.new(inv.outputs["Value"], amt.inputs[0])
    sc = N.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    ng.links.new(cen.outputs["Vector"], sc.inputs[0])
    ng.links.new(amt.outputs["Value"], sc.inputs["Scale"])
    add = N.new("ShaderNodeVectorMath")
    add.operation = "ADD"
    ng.links.new(mix.outputs[1], add.inputs[0])
    ng.links.new(sc.outputs["Vector"], add.inputs[1])
    sp = N.new("GeometryNodeSetPosition")
    ng.links.new(gi.outputs["Geometry"], sp.inputs["Geometry"])
    ng.links.new(add.outputs["Vector"], sp.inputs["Position"])
    m2p = N.new("GeometryNodeMeshToPoints")
    m2p.inputs["Radius"].default_value = 0.00045
    ng.links.new(sp.outputs["Geometry"], m2p.inputs["Mesh"])
    smat = N.new("GeometryNodeSetMaterial")
    mat = D.materials.get("dust") or _dust_mat()
    smat.inputs["Material"].default_value = mat
    ng.links.new(m2p.outputs["Points"], smat.inputs["Geometry"])
    ng.links.new(smat.outputs["Geometry"], go.inputs["Geometry"])
    return ng


def _dust_mat():
    m = D.materials.new("dust")
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1)
    p.inputs["Emission Color"].default_value = (1.0, 0.78, 0.55, 1)
    p.inputs["Emission Strength"].default_value = 9.0
    return m


def _setup_form(X):
    for o in D.collections["camera"].all_objects:
        o.hide_render = True
    X["dust"] = make_dust()


SHOTS["a_form"]["setup"] = _setup_form


# ---------------------------------------------------------------- driver
def bake_shot(name, X):
    S = SHOTS[name]
    n = round(S["dur"] * FPS)
    sc = C.scene
    sc.frame_start, sc.frame_end = 0, n - 1
    sc.render.use_motion_blur = S["blur"]
    for f in range(n):
        t = f / FPS
        X["f"] = f
        S["fn"](t, X)
        C.view_layer.update()
        if "crew" in X:
            pass
        rig.key_parts(f)
        for b in rig.blades():
            b.keyframe_insert("scale", frame=f)
            b.keyframe_insert("location", frame=f)
        rig.key_cam(f)
        key_lights(f)
        for nm in ("rear dial", "fan rotor"):
            D.objects[nm].keyframe_insert("rotation_euler", frame=f)
        if "crew" in X:
            X["crew"].key(f)
        if "hero" in X:
            hero, arms = X["hero"]
            hero.keyframe_insert("location", frame=f)
            hero.keyframe_insert("rotation_quaternion", frame=f)
            for sh, el in arms:
                sh.keyframe_insert("rotation_euler", frame=f)
                el.keyframe_insert("rotation_euler", frame=f)
        if "scan" in X:
            X["scan"].keyframe_insert("location", frame=f)
            X["scan"].keyframe_insert("scale", frame=f)
    rig.linear_keys()
    return n


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = {"--res": "1920", "--spp": "24", "--stills": None, "--threshold": "0.03", "--stilldir": str(OUT / "stills")}
    names, i = [], 0
    while i < len(argv):
        if argv[i] in opts:
            opts[argv[i]] = argv[i + 1]
            i += 2
        else:
            names.append(argv[i])
            i += 1
    for name in names:
        rig.load()
        X = {}
        if "setup" in SHOTS[name]:
            SHOTS[name]["setup"](X)
        n = bake_shot(name, X)
        w = int(opts["--res"])
        rig.quality((w, round(w * 9 / 16)), int(SHOTS[name]["spp"] or opts["--spp"]), threshold=float(opts["--threshold"]))
        sc = C.scene
        sc.render.use_persistent_data = True
        sc.render.fps = FPS
        sc.render.image_settings.file_format = "PNG"
        sc.render.image_settings.color_depth = "8"
        sc.render.image_settings.compression = 30
        if opts["--stills"]:
            d = Path(opts["--stilldir"])
            d.mkdir(parents=True, exist_ok=True)
            for s in opts["--stills"].split(","):
                f = min(n - 1, round(float(s) * FPS))
                sc.frame_set(f)
                sc.render.filepath = str(d / ("%s_%05.2fs.png" % (name, float(s))))
                bpy.ops.render.render(write_still=True)
            print("STILLS", name, opts["--stills"], flush=True)
            continue
        d = OUT / name
        d.mkdir(parents=True, exist_ok=True)
        sc.render.filepath = str(d / "f_")
        sc.render.use_overwrite = False
        sc.render.use_placeholder = True
        t0 = time.time()
        bpy.ops.render.render(animation=True)
        print("RENDERED %s: %d frames in %.0f s" % (name, n, time.time() - t0), flush=True)
        mp4 = OUT / (name + ".mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-start_number", "0", "-i", str(d / "f_%04d.png"),
                        "-c:v", "libx264", "-preset", "slow", "-crf", "12", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)],
                       check=True)
        print("ENCODED", mp4, flush=True)


if __name__ == "__main__":
    main()
