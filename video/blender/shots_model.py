"""The films' 3D shots on the camera model (cache/model.blend from build_model.py), path-traced in Cycles.

Same idea as shots.py (each shot a function of time, keyed per frame so Cycles can motion-blur it, rendered resumably),
plus what the redo asked for:
- transparent renders with a shadow catcher, so the hype film can change the world behind a locked camera;
- the X-ray: the scene property "xray" fades every outer material to glass;
- agents that shine: brighter emission, a little light each, and light trails (ribbons rebuilt every frame from the
  same path functions that place them).

Run (inside Blender): Blender -b -P video/blender/shots_model.py -- SHOT [SHOT ...] [--res 1920] [--spp 24] [--stills 0,1.2]
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
import shots as S  # noqa: E402  (kf, orbit, cam, lights, sweep_light, aim_light, freeze_mats, histogram, hero_agent)
from mathutils import Euler, Quaternion, Vector  # noqa: E402

rig.BLEND = rig.ROOT / "video" / "blender" / "cache" / "model.blend"
D, C = bpy.data, bpy.context
FPS = 24
OUT = rig.ROOT / "video" / "blender" / "out"
B = 60.0 / 115.0
kf, orbit, cam, lights = S.kf, S.orbit, S.cam, S.lights
MX, MZ = 0.0125, -0.0015                   # lens axis
AX = Vector((MX, 0, MZ))


def mm(x, y, z):
    return Vector((x / 1000, y / 1000, z / 1000))


def iris(fnum):
    a = max(0.0215 * min(1.0, 2.8 / fnum), 0.0014)
    for b in rig.blades():
        b.scale = (0.0105, 0.0275 - a, 0.00015)
        b.location = (0.0, a, b.location.z)


def xray(v):
    C.scene["xray"] = float(v)
    # inside the glass camera the lens elements barely bend light, so the iris and the sensor read clearly
    g = D.materials["coated glass"].node_tree.nodes["Principled BSDF"]
    g.inputs["IOR"].default_value = 1.58 + (1.03 - 1.58) * min(1.0, float(v))


def tune_xray(ior=1.3, rough=0.03, glow=0.35, tint=(0.93, 0.96, 1.0)):
    """Clearer glass for the X-ray (after the test renders read as frosted acrylic): fewer, crisper reflections, fainter
    edge glow, a cool tint. Walks each X-ray mix from the material output (see build_model.xrayify)."""
    for mt in D.materials:
        nt = mt.node_tree
        out = nt.nodes.get("Material Output") if nt else None
        if not out or not out.inputs["Surface"].links:
            continue
        fin = out.inputs["Surface"].links[0].from_node
        if fin.type != "MIX_SHADER" or not fin.inputs["Fac"].links:
            continue
        a = fin.inputs["Fac"].links[0].from_node
        if a.type != "ATTRIBUTE" or a.attribute_name != "xray":
            continue
        add = fin.inputs[2].links[0].from_node
        mixg, em = add.inputs[0].links[0].from_node, add.inputs[1].links[0].from_node
        em.inputs["Strength"].links[0].from_node.inputs[1].default_value = glow
        mixg.inputs["Fac"].links[0].from_node.inputs["IOR"].default_value = ior
        mixg.inputs[1].links[0].from_node.inputs["Color"].default_value = (*tint, 1)
        mixg.inputs[2].links[0].from_node.inputs["Roughness"].default_value = rough


def shine(k=1.0):
    """The agents' glow (the redo: they must shine)."""
    for nm, s in (("agent thruster", 34.0), ("agent tip", 22.0), ("ai glow", 12.0), ("ai trace", 7.0)):
        D.materials[nm].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = s * k
    D.lights["agent light"].energy = 0.012 * k


# ---------------------------------------------------------------- the crew, with trails
class Crew:
    """Instanced agents with explicit path functions, so trails can sample where each one was a moment ago."""

    def __init__(self, n, seed=3, targets=None, scale=1.0):
        r = random.Random(seed)
        self.items, self.mode = [], ("work", {})
        spots = []
        for nm in targets or ["sensor package", "iris housing", "main board", "chip tile", "fan housing", "ai core", "stabiliser plate"]:
            obs = [o for o in D.objects if o.name == nm or o.name.startswith(nm + ".")]
            for o in obs:
                bb = [Vector(c) for c in o.bound_box]
                lo = Vector((min(c.x for c in bb), min(c.y for c in bb), min(c.z for c in bb)))
                hi = Vector((max(c.x for c in bb), max(c.y for c in bb), max(c.z for c in bb)))
                for _ in range(max(2, 14 // len(obs))):
                    p = Vector((r.uniform(lo.x, hi.x), r.uniform(lo.y, hi.y), r.uniform(lo.z, hi.z)))
                    ax = r.randrange(3)
                    p[ax] = lo[ax] if r.random() < 0.5 else hi[ax]
                    spots.append((o, p, ax, 1 if p[ax] == hi[ax] else -1))
        r.shuffle(spots)
        proto = D.collections["crew proto"]
        for i in range(n):
            e = D.objects.new("crew %03d" % i, None)
            e.instance_type, e.instance_collection = "COLLECTION", proto
            C.scene.collection.objects.link(e)
            e.rotation_mode = "QUATERNION"
            self.items.append({"ob": e, "spot": spots[i % len(spots)], "ph": r.uniform(0, math.tau), "orb": r.uniform(0.002, 0.006),
                               "spd": r.uniform(1.3, 2.6), "bob": r.uniform(0.0005, 0.0015), "dl": r.uniform(0, 0.5),
                               "lane": r.uniform(-1, 1), "s": scale * r.uniform(0.85, 1.15)})
        self.trail = None

    def home(self, a):
        o, p, ax, sg = a["spot"]
        n = Vector((0, 0, 0))
        n[ax] = sg
        w = o.matrix_world
        return w @ p + (w.to_3x3() @ n).normalized() * 0.0028

    def pos(self, a, t):
        mode, kw = self.mode
        tt = min(t, kw.get("freeze", 1e9))
        h = self.home(a)
        ph = a["ph"] + tt * a["spd"] * kw.get("speed", 1.0)
        p = h + Vector((math.cos(ph) * a["orb"], math.sin(ph * 0.7) * a["orb"] * 0.6, math.sin(ph * 1.3) * a["bob"]))
        if mode == "swarm":
            c, R = Vector(kw["centre"]), kw.get("radius", 0.08)
            u = ph * 0.55 + a["lane"]
            sw = c + Vector((math.cos(u) * R * (0.6 + 0.4 * math.sin(a["ph"])), math.sin(u * 1.3) * R * 0.8, math.sin(u * 0.9 + a["ph"]) * R * 0.4))
            p = sw.lerp(p, kw.get("home", 0.2))
        if "burst" in kw:                                     # out of the AI core, staggered
            k = max(0.0, min(1.0, (t - kw["burst"] - a["dl"] * 0.6) / 0.7))
            p = kw["core"].lerp(p, 1 - (1 - k) ** 3)
        return p

    def visible(self, a, t):
        kw = self.mode[1]
        return "burst" not in kw or t >= kw["burst"] + a["dl"] * 0.6 - 0.02

    def place(self, t, vis=1.0, count=None):
        for i, a in enumerate(self.items):
            e = a["ob"]
            p, p2 = self.pos(a, t), self.pos(a, t + 0.04)
            d = p2 - p
            e.location = p
            e.rotation_quaternion = (d if d.length > 1e-7 else Vector((0, -1, 0))).to_track_quat("-Y", "Z")
            on = (count is None or i < count) and self.visible(a, t)
            s = a["s"] * vis if on else 0.0
            e.scale = (s, s, s)

    def key(self, f):
        for a in self.items:
            for p in ("location", "rotation_quaternion", "scale"):
                a["ob"].keyframe_insert(p, frame=f)

    # light trails: a camera-facing ribbon behind each agent, glowing orange, fading to nothing
    def make_trail(self):
        me = D.meshes.new("trails")
        ob = D.objects.new("trails", me)
        C.scene.collection.objects.link(ob)
        ob.cycles.use_motion_blur = False
        m = D.materials.new("trail glow")
        m.use_nodes = True
        nt = m.node_tree
        p = nt.nodes["Principled BSDF"]
        nt.nodes.remove(p)
        at = nt.nodes.new("ShaderNodeAttribute")
        at.attribute_name = "fade"
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (1.0, 0.42, 0.1, 1)
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = 16.0
        nt.links.new(at.outputs["Fac"], mul.inputs[0])
        nt.links.new(mul.outputs["Value"], em.inputs["Strength"])
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mx = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(at.outputs["Fac"], mx.inputs["Fac"])
        nt.links.new(tr.outputs["BSDF"], mx.inputs[1])
        nt.links.new(em.outputs["Emission"], mx.inputs[2])
        nt.links.new(mx.outputs["Shader"], nt.nodes["Material Output"].inputs["Surface"])
        me.materials.append(m)
        self.trail = ob

    def build_trail(self, t, length=0.22, steps=10, width=0.0011):
        if not self.trail:
            return
        camp = D.objects["film camera"].matrix_world.translation
        verts, faces, fade = [], [], []
        for a in self.items:
            if a["ob"].scale.x < 1e-6:
                continue
            pts = [self.pos(a, t - length * k / steps) for k in range(steps + 1)]
            if (pts[0] - pts[-1]).length < 0.003:
                continue
            base = len(verts)
            for k, p in enumerate(pts):
                tang = (pts[max(k - 1, 0)] - pts[min(k + 1, steps)])
                side = tang.cross(camp - p)
                side = side.normalized() * width * (1 - k / steps) * a["s"] if side.length > 1e-9 else Vector((0, 0, 0))
                verts += [p + side, p - side]
                f = (1 - k / steps) ** 1.6
                fade += [f, f]
            for k in range(steps):
                i = base + 2 * k
                faces.append((i, i + 1, i + 3, i + 2))
        me = self.trail.data
        me.clear_geometry()
        me.from_pydata([tuple(v) for v in verts], [], faces)
        at = me.attributes.get("fade") or me.attributes.new("fade", "FLOAT", "POINT")
        if verts:
            at.data.foreach_set("value", fade)
        me.update()


# ---------------------------------------------------------------- shots
SHOTS = {}


def shot(name, dur, blur=True, spp=None, alpha=False):
    def deco(fn):
        SHOTS[name] = {"dur": dur, "fn": fn, "blur": blur, "spp": spp, "alpha": alpha}
        return fn
    return deco


def hero_pose(t, yaw0, yaw1, dur, dist0, dist1, pitch=0.1, tgt=(0.0, -0.03, 0.0), mmlen=50, fstop=8.0):
    yaw = kf(t, [(0, yaw0, "lin"), (dur, yaw1, "io")])
    pos = orbit(tgt, yaw, pitch, kf(t, [(0, dist0, "lin"), (dur, dist1, "io")]))
    cam(pos, tgt, mmlen, fstop)


# --- CALM: the camera as art, sparingly ---------------------------------------------------------------------------
@shot("c_silhouette", 5.0, alpha=True, spp=32)
def c_silhouette(t, X):
    """A dark silhouette in profile, only a warm rim tracing it, then one glint running along the lens."""
    xray(0)
    iris(4)
    lights(key=0.0, top=0.0, rim_left=kf(t, [(0, 0.6, "lin"), (5, 3.0, "io")]), rim_right=0.0, floor=0.0, card=0.0)
    for nm in ("rim left", "rim right"):
        D.objects[nm].data.color = (1.0, 0.78, 0.55)
    sw = S.sweep_light()
    sw.data.energy = kf(t, [(0, 0.0, "lin"), (2.6, 0.0, "lin"), (3.0, 14.0, "io"), (4.2, 14.0, "lin"), (4.6, 0.0, "io")])
    x = kf(t, [(0, -0.4, "lin"), (2.6, -0.4, "lin"), (4.6, 0.5, "io")])
    S.aim_light(sw, (x, -0.35, 0.3), (0.0, -0.08, 0.0))
    pos = orbit((0.0, -0.04, 0.004), kf(t, [(0, 1.42, "lin"), (5, 1.3, "io")]), 0.02, kf(t, [(0, 0.5, "lin"), (5, 0.44, "io")]))
    cam(pos, (0.0, -0.04, 0.004), 60, 8.0)


@shot("c_glint", 1.4, spp=32)
def c_glint(t, X):
    """The whole front of the lens, close: a line of light sweeps across the glass and its coatings."""
    xray(0)
    iris(2.8)
    lights(key=0.1, top=0.25, rim_left=0.8, rim_right=0.5, card=0.15)
    sw = S.sweep_light()
    sw.data.energy = 12.0
    x = kf(t, [(0, -0.45, "lin"), (1.4, 0.45, "io")])
    S.aim_light(sw, (x, -0.5, 0.3), (MX, -0.12, MZ))
    tgt = Vector((MX, -0.12, MZ))
    pos = tgt + Vector((0.07, -0.2, 0.05)).normalized() * kf(t, [(0, 0.24, "lin"), (1.4, 0.225, "io")])
    cam(pos, tgt, 85, 8.0)


@shot("c_iris", 1.2, spp=32)
def c_iris(t, X):
    """Straight into the lens: the iris closes a few stops, seen through the glass."""
    xray(0)
    iris(kf(t, [(0, 2.8, "lin"), (0.25, 2.8, "lin"), (1.1, 9.0, "io")]))
    lights(key=0.4, top=0.8, rim_left=0.4, rim_right=0.4, card=1.2)
    tgt = Vector((MX, -0.08, MZ))
    pos = Vector((MX + 0.006, -0.25, MZ + 0.008))
    cam(pos, tgt, 100, 5.6, focus=(Vector((MX, -0.074, MZ)) - pos).length)


@shot("c_dial", 1.0, spp=32)
def c_dial(t, X):
    """The front dial's knurl turning past, razor focus."""
    xray(0)
    lights(key=0.6, top=1.6, rim_left=1.8, rim_right=0.8, card=0.5)
    d = D.objects["front dial"]
    d.rotation_euler = Euler((0, 0, t * 1.4))
    c = d.matrix_world.translation
    pos = c + Vector((-0.03, -0.05, 0.012)) * 1.5
    cam(pos, c + Vector((0, -0.008, 0)), 100, 7.1)


@shot("c_ring", 1.0, spp=32)
def c_ring(t, X):
    """Along the zoom ring's ribs as the light rolls over them."""
    xray(0)
    lights(key=0.2, top=kf(t, [(0, 0.3, "lin"), (1, 1.4, "io")]), rim_left=1.2, rim_right=0.4, card=0.1)
    tgt = Vector((MX - 0.034, -0.06, MZ + 0.015))
    pos = tgt + Vector((-0.06, -0.035, 0.03)) * 1.5
    cam(pos, tgt, 100, 7.1)


# --- HYPE: the world changes, the camera stays ---------------------------------------------------------------------
# beats 0..12 of the film: per beat, (world/reflection colour, key colour, key, rim, iris). Solid colours, then places.
WORLDS = [
    ((0.0, 0.0, 0.0), (1.0, 0.95, 0.9), 0.0, 1.8, 4.0),       # 0 black: only a rim
    ((0.55, 0.32, 0.06), (1.0, 0.8, 0.55), 0.7, 1.4, 8.0),     # 1 ochre
    ((0.42, 0.04, 0.03), (1.0, 0.55, 0.45), 0.6, 1.4, 5.6),    # 2 deep red
    ((0.04, 0.09, 0.33), (0.6, 0.75, 1.0), 0.6, 1.6, 4.0),     # 3 cobalt
    ((0.25, 0.32, 0.18), (0.95, 1.0, 0.85), 0.7, 1.4, 5.6),    # 4 sage
    ((0.75, 0.72, 0.66), (1.0, 1.0, 0.98), 0.9, 1.0, 11.0),    # 5 bright paper
    ((0.6, 0.38, 0.18), (1.0, 0.72, 0.42), 0.8, 1.8, 8.0),     # 6 sunset
    ((0.03, 0.05, 0.12), (0.55, 0.65, 1.0), 0.35, 2.2, 2.8),   # 7 city night
    ((0.55, 0.42, 0.28), (1.0, 0.86, 0.66), 1.0, 1.2, 11.0),   # 8 desert noon
    ((0.12, 0.2, 0.08), (0.85, 1.0, 0.75), 0.5, 1.6, 5.6),     # 9 forest
    ((0.8, 0.8, 0.8), (1.0, 1.0, 1.0), 1.0, 1.0, 8.0),         # 10 white studio
    ((0.02, 0.02, 0.025), (1.0, 0.95, 0.9), 0.55, 1.8, 4.0),   # 11 black studio
]


@shot("h_world", 12 * B, alpha=True, spp=24)
def h_world(t, X):
    """Locked on the camera, slow push; on every beat a new world: its light, its reflections, its iris."""
    b = t / B
    i = min(int(b), len(WORLDS) - 1)
    wc, kc, key, rim, fs = WORLDS[i]
    xray(0)
    S.world_color(wc, 0.6)
    lights(key=key, top=0.6 + 0.4 * key, rim_left=rim, rim_right=rim * 0.85, floor=0.3 * key, card=0.4)
    D.objects["key softbox"].data.color = kc
    iris(fs)
    X["catcher"].hide_render = False
    tgt = Vector((0.0, -0.045, 0.0))
    pos = orbit(tgt, kf(b, [(0, -0.34, "lin"), (12, -0.3, "lin")]), 0.08, kf(b, [(0, 0.52, "lin"), (12, 0.47, "lin")]))
    cam(pos, tgt, 50, 8.0)


SHOTS["h_world"]["setup"] = lambda X: X.update(catcher=S.shadow_catcher(z=-0.0392))


@shot("h_smash", 4 * B, spp=24)
def h_smash(t, X):
    """From the hero view straight down the axis into the glass, accelerating."""
    b = t / B
    xray(0)
    iris(kf(b, [(0, 4.0, "lin"), (3.0, 4.0, "lin"), (3.8, 2.8, "xout")]))
    lights(key=0.6, top=1.2, rim_left=1.4, rim_right=1.2, card=1.4)
    yaw = kf(b, [(0, -0.34, "lin"), (2.0, -0.12, "io"), (4, 0.0, "in")])
    dist = kf(b, [(0, 0.5, "lin"), (2.0, 0.34, "io"), (3.4, 0.2, "in"), (4, 0.14, "in")])
    tgt = Vector((MX, -0.12, MZ))
    pos = orbit(tgt, yaw, kf(b, [(0, 0.08, "lin"), (4, 0.0, "io")]), dist)
    cam(pos, tgt, kf(b, [(0, 50, "lin"), (4, 35, "in")]), 4.0, focus=dist)


@shot("h_xray", 8 * B, spp=28)
def h_xray(t, X):
    """THE DROP: the body turns to glass in a flash; inside, the board and sensor glow and the crew bursts out of the
    AI core and streams to the sensor, the iris and the colour chip. A slow-motion swing round."""
    b = t / B
    xray(kf(b, [(0, 0.0, "lin"), (0.35, 1.0, "xout")]))
    iris(4)
    shine(1.0)
    lights(key=0.35, top=0.5, rim_left=1.6, rim_right=1.5, card=0.3, glow=kf(b, [(0, 0.0, "lin"), (0.4, 2.0, "xout"), (3, 0.6, "io")]))
    D.objects["crew glow"].location = D.objects["ai core"].matrix_world.translation
    tw = kf(b, [(0, 0.0, "lin"), (2.0, 0.3, "lin"), (8, 3.4, "in")])
    X["crew"].mode = ("work", {"burst": 0.1, "core": D.objects["ai core"].matrix_world.translation.copy(), "speed": 1.0})
    X["crew"].place(tw)
    X["tw"] = tw
    tgt = Vector((0.0, -0.02, 0.0))
    pos = orbit(tgt, kf(b, [(0, 0.55, "lin"), (8, 1.2, "io")]), kf(b, [(0, 0.15, "lin"), (8, 0.28, "io")]),
                kf(b, [(0, 0.36, "lin"), (8, 0.42, "io")]))
    cam(pos, tgt, 45, 5.6)


def _setup_xray(X):
    X["crew"] = Crew(140, seed=5)
    X["crew"].make_trail()


SHOTS["h_xray"]["setup"] = _setup_xray


def _close(X, target_name, n=26, seed=7):
    X["crew"] = Crew(n, seed=seed, targets=[target_name])
    X["crew"].make_trail()


@shot("h_sensor", 4 * B, spp=28)
def h_sensor(t, X):
    """Close on the sensor through the glass body: the crew sweeping its face, their light on the die."""
    b = t / B
    xray(1.0)
    shine(1.2)
    lights(key=0.3, top=0.4, rim_left=1.2, rim_right=1.0, card=0.2, glow=0.0)
    X["crew"].mode = ("work", {"speed": 2.2})
    X["crew"].place(t * 1.5)
    X["tw"] = t * 1.5
    die = D.objects["sensor die"].matrix_world.translation
    pos = die + Vector((kf(b, [(0, 0.05, "lin"), (4, 0.04, "io")]), kf(b, [(0, -0.075, "lin"), (4, -0.06, "io")]), 0.03))
    cam(pos, die, 60, 5.6)


SHOTS["h_sensor"]["setup"] = lambda X: _close(X, "sensor package", 26, 7)


@shot("h_irisx", 4 * B, spp=28)
def h_irisx(t, X):
    """The iris, seen through the glass lens barrel, with the crew on its ring: it snaps on each beat."""
    b = t / B
    xray(1.0)
    shine(1.2)
    iris(kf(b, [(0, 11, "lin"), (0.9, 11, "lin"), (1.0, 8, "xout"), (1.9, 8, "lin"), (2.0, 4, "xout"), (2.9, 4, "lin"), (3.0, 2.8, "xout")]))
    lights(key=0.4, top=0.5, rim_left=1.4, rim_right=1.2, card=0.6, glow=1.4)
    D.objects["crew glow"].location = D.objects["sensor die"].matrix_world.translation   # light behind the iris: the opening glows
    X["crew"].mode = ("work", {"speed": 1.6})
    X["crew"].place(t * 1.5)
    X["tw"] = t * 1.5
    ir = D.objects["iris"].matrix_world.translation
    pos = ir + Vector((0.035, -0.09, 0.025)) * kf(b, [(0, 1.0, "lin"), (4, 0.82, "io")])
    cam(pos, ir, 60, 5.6)


SHOTS["h_irisx"]["setup"] = lambda X: _close(X, "iris housing", 22, 9)


@shot("h_chip", 4 * B, spp=28)
def h_chip(t, X):
    """The colour chip on the board: the crew repaints its nine tiles from warm to neutral, one by one."""
    b = t / B
    xray(1.0)
    shine(1.2)
    lights(key=0.3, top=0.4, rim_left=1.2, rim_right=1.0, card=0.2)
    X["crew"].mode = ("work", {"speed": 1.8})
    X["crew"].place(t * 1.5)
    X["tw"] = t * 1.5
    tiles = sorted([o for o in D.objects if o.name.startswith("chip tile")], key=lambda o: o.name)
    warm, neutral = (1.0, 0.5, 0.2), (0.85, 0.9, 1.0)
    for i, o in enumerate(tiles):
        k = kf(b, [(0, 0.0, "lin"), (0.5 + i * 0.32, 0.0, "lin"), (0.75 + i * 0.32, 1.0, "out")])
        o["tint"] = k
    m = D.materials["colour chip"].node_tree.nodes["Principled BSDF"]
    avg = sum(o["tint"] for o in tiles) / max(1, len(tiles))
    m.inputs["Emission Color"].default_value = (*S.lerp(warm, neutral, avg), 1)
    m.inputs["Emission Color"].keyframe_insert("default_value", frame=X["f"])
    chip = D.objects["colour chip"].matrix_world.translation
    pos = chip + Vector((0.035, 0.075, 0.04)) * kf(b, [(0, 1.0, "lin"), (4, 0.85, "io")])
    cam(pos, chip, 70, 5.6)


SHOTS["h_chip"]["setup"] = lambda X: _close(X, "chip tile", 12, 13)


@shot("h_swarm", 4 * B, spp=28)
def h_swarm(t, X):
    """Wide on the glass camera, the crew racing round it with trails."""
    b = t / B
    xray(1.0)
    shine(1.0)
    lights(key=0.3, top=0.5, rim_left=1.6, rim_right=1.4, card=0.3, glow=1.0)
    D.objects["crew glow"].location = D.objects["ai core"].matrix_world.translation
    tw = t * 3.0 + 2.0
    X["crew"].mode = ("swarm", {"centre": (0.0, -0.03, 0.0), "radius": 0.09, "home": 0.25})
    X["crew"].place(tw)
    X["tw"] = tw
    tgt = Vector((0.0, -0.03, 0.0))
    pos = orbit(tgt, kf(b, [(0, -0.8, "lin"), (4, -0.4, "lin")]), 0.15, kf(b, [(0, 0.5, "lin"), (4, 0.44, "lin")]))
    cam(pos, tgt, 45, 6.0)


SHOTS["h_swarm"]["setup"] = lambda X: (X.update(crew=Crew(180, seed=9)), X["crew"].make_trail())


@shot("h_kill", 4 * B, spp=28)
def h_kill(t, X):
    """The kill switch: on the beat the crew stops dead and goes red; trails die."""
    b = t / B
    xray(1.0)
    shine(1.0)
    k = kf(b, [(0, 0.0, "lin"), (1.0, 0.0, "lin"), (1.12, 1.0, "xout")])
    S.freeze_mats(k)
    S.key_freeze(X["f"])
    lights(key=0.3, top=0.5, rim_left=1.4, rim_right=1.3, card=0.3, glow=1.0 * (1 - k))
    D.objects["crew glow"].location = D.objects["ai core"].matrix_world.translation
    tw = t * 3.0 + 9.0
    X["crew"].mode = ("swarm", {"centre": (0.0, -0.03, 0.0), "radius": 0.09, "home": 0.25, "freeze": 1.0 * B * 3.0 + 9.0})
    X["crew"].place(tw)
    X["tw"] = tw
    tgt = Vector((0.0, -0.03, 0.0))
    pos = orbit(tgt, kf(b, [(0, -0.2, "lin"), (1.0, -0.17, "lin"), (4, -0.165, "out")]), 0.12, 0.47)
    cam(pos, tgt, 45, 6.0)


SHOTS["h_kill"]["setup"] = lambda X: (X.update(crew=Crew(180, seed=9)), X["crew"].make_trail())


@shot("h_slam", 8 * B, spp=24)
def h_slam(t, X):
    """Glass back to solid in a flash on the beat (2 beats in), a shake, then the hero turns, held."""
    b = t / B
    xray(kf(b, [(0, 1.0, "lin"), (1.8, 1.0, "lin"), (2.0, 0.0, "in")]))
    shine(kf(b, [(0, 1.0, "lin"), (2.0, 0.0, "in")]))
    iris(4)
    flash = math.exp(-max(0.0, b - 2.0) / 0.25) if b >= 2.0 else 0.0
    lights(key=0.55 + 1.5 * flash, top=0.9 + 1.5 * flash, rim_left=1.7, rim_right=1.5, card=0.5 + 1.2 * flash)
    sh = math.exp(-max(0.0, b - 2.0) / 0.3) if b >= 2.0 else 0.0
    jit = Vector((math.sin(t * 90) * 0.003 * sh, 0, math.cos(t * 77) * 0.002 * sh))
    tgt = Vector((0.0, -0.035, 0.0))
    pos = orbit(tgt, kf(b, [(0, 0.9, "lin"), (2.0, 0.7, "lin"), (8, 0.36, "out")]), kf(b, [(0, 0.18, "lin"), (8, 0.1, "io")]),
                kf(b, [(0, 0.6, "lin"), (2.0, 0.5, "in"), (8, 0.44, "out")])) + jit
    cam(pos, tgt, 50, 8.0)


# --- STORY ------------------------------------------------------------------------------------------------------------
@shot("s_catch", 4.0, spp=28)
def s_catch(t, X):
    """Through the glass body at the sensor: an agent sees the light drop (its histogram jumps), whips round and reaches."""
    xray(1.0)
    shine(1.1)
    lights(key=0.4, top=0.4, rim_left=1.3, rim_right=1.1, card=0.3)
    centre = D.objects["sensor die"].matrix_world.translation
    hero, arms = X["hero"]
    jolt = kf(t, [(0, 0.0, "lin"), (1.1, 0.0, "lin"), (1.35, 1.0, "xout"), (3.2, 1.0, "lin"), (4.0, 0.3, "io")])
    hero.location = centre + Vector((0.002, -0.0065, 0.0015 + 0.0002 * math.sin(t * 4.0) + 0.0008 * jolt))
    fwd = Vector((0, 1, 0)).lerp(Vector((-0.6, -0.2, 0.75)).normalized(), jolt).normalized()
    hero.rotation_quaternion = (-fwd).to_track_quat("Y", "Z")
    reach = kf(t, [(0, 0.0, "lin"), (1.3, 0.0, "lin"), (1.6, 1.0, "xout"), (3.0, 1.0, "lin"), (3.6, 0.2, "io")])
    for i, (sh, el) in enumerate(arms):
        sh.rotation_euler = Euler((-1.2 * reach + 0.1 * math.sin(t * 3 + i), 0, 0))
        el.rotation_euler = Euler((-0.7 * reach, 0, 0))
    S.histogram(t * (1.0 + 3.0 * jolt), X["f"])
    X["crew"].mode = ("work", {"speed": 1.0})
    X["crew"].place(t)
    X["tw"] = t
    tgt = hero.location + Vector((0.0, 0.0, 0.0003))
    pos = tgt + Vector((kf(t, [(0, -0.021, "lin"), (4, -0.017, "io")]), kf(t, [(0, -0.024, "lin"), (4, -0.02, "io")]), 0.008))
    cam(pos, tgt, 100, 16.0, focus=(hero.location - pos).length - 0.0011)


def _setup_catch(X):
    X["hero"] = S.hero_agent("hero catch")
    X["crew"] = Crew(10, seed=33, targets=["sensor package", "stabiliser plate"])


SHOTS["s_catch"]["setup"] = _setup_catch


@shot("s_hero", 5.0, spp=24)
def s_hero(t, X):
    """The camera, assembled, a slow push in warm-and-cool light (5 s: what the story uses)."""
    xray(0)
    iris(2.8)
    lights(key=0.55, top=0.8, rim_left=1.6, rim_right=1.0, card=0.6)
    tgt = Vector((0.0, -0.03, 0.012))
    pos = orbit(tgt, kf(t, [(0, -0.42, "lin"), (5, -0.33, "io")]), 0.1, kf(t, [(0, 0.5, "lin"), (5, 0.455, "io")]))
    cam(pos, tgt, 50, 8.0)


@shot("p_fx_hero", 1.0, blur=False)
def p_fx_hero(t, X):
    xray(0)
    iris(2.8)
    lights(key=0.6, top=1.0, rim_left=1.8, rim_right=1.4, card=0.7)
    tgt = Vector((0.0, -0.04, 0.0))
    cam(orbit(tgt, -0.55, 0.15, 0.5), tgt, 60, 9.0)


@shot("p_fx_xray", 1.0, blur=False, spp=64)
def p_fx_xray(t, X):
    xray(1.0)
    shine(1.2)
    lights(key=0.3, top=0.5, rim_left=1.6, rim_right=1.4, card=0.3, glow=1.0)
    D.objects["crew glow"].location = D.objects["ai core"].matrix_world.translation
    X["crew"].mode = ("work", {"speed": 1.0})
    X["crew"].place(2.0)
    X["tw"] = 2.0
    tgt = Vector((0.0, -0.02, 0.0))
    cam(orbit(tgt, 0.8, 0.22, 0.4), tgt, 45, 6.0)


SHOTS["p_fx_xray"]["setup"] = lambda X: (X.update(crew=Crew(90, seed=5)), X["crew"].make_trail())


# ---------------------------------------------------------------- driver
def bake_shot(name, X):
    Sh = SHOTS[name]
    n = round(Sh["dur"] * FPS)
    sc = C.scene
    sc.frame_start, sc.frame_end = 0, n - 1
    sc.render.use_motion_blur = Sh["blur"]
    for f in range(n):
        t = f / FPS
        X["f"] = f
        for _ in range(2):                                   # twice: world matrices of this frame for the crew and hero
            Sh["fn"](t, X)
            C.view_layer.update()
        rig.key_cam(f)
        S.key_lights(f)
        for L in D.objects:
            if L.type == "LIGHT":
                L.data.keyframe_insert("color", frame=f)
        S.key_world(f)
        sc.keyframe_insert('["xray"]', frame=f)
        D.materials["coated glass"].node_tree.nodes["Principled BSDF"].inputs["IOR"].keyframe_insert("default_value", frame=f)
        for b in rig.blades():
            b.keyframe_insert("scale", frame=f)
            b.keyframe_insert("location", frame=f)
        for nm in ("front dial", "fan rotor"):
            if nm in D.objects:
                D.objects[nm].keyframe_insert("rotation_euler", frame=f)
        for nm in ("agent thruster", "agent tip", "ai glow", "ai trace"):
            D.materials[nm].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].keyframe_insert("default_value", frame=f)
        D.lights["agent light"].keyframe_insert("energy", frame=f)
        if "crew" in X:
            X["crew"].key(f)
        if "hero" in X:
            hero, arms = X["hero"]
            hero.keyframe_insert("location", frame=f)
            hero.keyframe_insert("rotation_quaternion", frame=f)
            for sh, el in arms:
                sh.keyframe_insert("rotation_euler", frame=f)
                el.keyframe_insert("rotation_euler", frame=f)
    rig.linear_keys()
    # trails follow the frame being rendered (also the motion-blur subframes): rebuilt from the same path functions
    if "crew" in X and X["crew"].trail is not None:
        crew = X["crew"]
        tw_of = {}
        for f in range(n):
            X["f"] = f
            Sh["fn"](f / FPS, X)
            tw_of[f] = X.get("tw", f / FPS)

        def on_frame(scene, depsgraph=None):
            f = scene.frame_current
            crew.build_trail(tw_of.get(f, f / FPS))
        bpy.app.handlers.frame_change_pre.clear()
        bpy.app.handlers.frame_change_pre.append(on_frame)
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
        tune_xray()
        X = {}
        if "setup" in SHOTS[name]:
            SHOTS[name]["setup"](X)
        n = bake_shot(name, X)
        w = int(opts["--res"])
        rig.quality((w, round(w * 9 / 16)), int(SHOTS[name]["spp"] or opts["--spp"]), threshold=float(opts["--threshold"]))
        sc = C.scene
        sc.render.use_persistent_data = False                    # the trails mesh changes every frame
        sc.render.fps = FPS
        alpha = SHOTS[name].get("alpha")
        sc.render.film_transparent = bool(alpha)
        sc.render.image_settings.file_format = "PNG"
        sc.render.image_settings.color_mode = "RGBA" if alpha else "RGB"
        sc.render.image_settings.color_depth = "8"
        sc.render.image_settings.compression = 30
        if opts["--stills"]:
            d = Path(opts["--stilldir"])
            d.mkdir(parents=True, exist_ok=True)
            for s_ in opts["--stills"].split(","):
                f = min(n - 1, round(float(s_) * FPS))
                sc.frame_set(f)
                sc.render.filepath = str(d / ("%s_%05.2fs.png" % (name, float(s_))))
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
        if alpha:
            out = OUT / (name + ".webm")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-start_number", "0", "-i", str(d / "f_%04d.png"),
                            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "18", "-row-mt", "1", "-g", "24",
                            "-auto-alt-ref", "0", str(out)], check=True)
        else:
            out = OUT / (name + ".mp4")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-start_number", "0", "-i", str(d / "f_%04d.png"),
                            "-c:v", "libx264", "-preset", "slow", "-crf", "12", "-g", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                            str(out)], check=True)
        print("ENCODED", out, flush=True)


if __name__ == "__main__":
    main()
