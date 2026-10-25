"""Build the camera the project actually uses: a faithful model of the Sony cinema camera (no logos, no printing), with a
24-50 mm-class zoom, its insides (sensor, stabiliser, board with the AI core and the colour chip, fan, battery) and the
crew of orange agents. Saves video/blender/cache/model.blend.

Every position comes from the measured reference table (Sony's own Sony cinema camera product photos and Help Guide drawings, scaled to
the official 129.7 x 77.8 mm; about +-1 mm on faces, +-2 mm in depth). Coordinates: mm, origin at the centre of the main
body box; the lens points -Y; +X is the port/EVF side, -X the grip; +Z up.

Every outer material can turn to glass ("X-ray"): a mix driven by the scene property "xray" (0..1), so a shot can fade
the body away and show what works inside.

Run: Blender -b --factory-startup -P video/blender/build_model.py
"""
import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_camera as bc  # noqa: E402  (helpers: mat, obj, rbox, lathe, ring, ribbed, cyl, sphere, cut, cutter, bake, agents, studio)

ROOT = bc.ROOT
OUT = ROOT / "video" / "blender" / "cache" / "model.blend"
D, C = bpy.data, bpy.context
TAU = math.tau


def m(*v):
    """mm -> metres (a number or a vector)."""
    return v[0] / 1000 if len(v) == 1 else tuple(x / 1000 for x in v)


# body box and mount (mm)
X0, X1, Z0, Z1 = -64.85, 64.85, -38.9, 38.9
YF, YR = -24.5, 16.6                        # front plate, rear panel
MX, MZ = 12.5, -1.5                         # E-mount centre
FLANGE = -31.5                              # mount flange (7 mm proud)


# ---------------------------------------------------------------- materials
def srgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def sparkle_paint(name, hexcol, rough=0.58, flake=0.35, bump=0.22):
    """Sony's coarse "sparkle" sand-texture paint: a grey base, fine sand bump, and tiny metallic flakes."""
    mt = bc.mat(name, **{"Base Color": (*srgb(hexcol), 1), "Metallic": 0.12, "Roughness": rough})
    nt = mt.node_tree
    p = nt.nodes["Principled BSDF"]
    tc = bc.node(nt, "ShaderNodeTexCoord")
    sand = bc.node(nt, "ShaderNodeTexNoise", in_Scale=3200.0, in_Detail=6.0)
    bc.link(nt, tc.outputs["Object"], sand.inputs["Vector"])
    bp = bc.node(nt, "ShaderNodeBump", in_Strength=bump, in_Distance=0.00004)
    bc.link(nt, sand.outputs["Fac"], bp.inputs["Height"])
    bc.link(nt, bp.outputs["Normal"], p.inputs["Normal"])
    vo = bc.node(nt, "ShaderNodeTexVoronoi", in_Scale=7000.0)               # flakes, about 0.14 mm
    bc.link(nt, tc.outputs["Object"], vo.inputs["Vector"])
    ramp = bc.node(nt, "ShaderNodeMapRange", in_From_Min=0.82, in_From_Max=0.9)
    sep = bc.node(nt, "ShaderNodeSeparateColor")
    bc.link(nt, vo.outputs["Color"], sep.inputs["Color"])
    bc.link(nt, sep.outputs[0], ramp.inputs["Value"])
    met = bc.node(nt, "ShaderNodeMath", operation="MULTIPLY")
    met.inputs[1].default_value = flake
    bc.link(nt, ramp.outputs["Result"], met.inputs[0])
    add = bc.node(nt, "ShaderNodeMath", operation="ADD")
    add.inputs[1].default_value = 0.12
    bc.link(nt, met.outputs["Value"], add.inputs[0])
    bc.link(nt, add.outputs["Value"], p.inputs["Metallic"])
    rr = bc.node(nt, "ShaderNodeMapRange", in_To_Min=rough, in_To_Max=rough - 0.25)
    bc.link(nt, ramp.outputs["Result"], rr.inputs["Value"])
    bc.link(nt, rr.outputs["Result"], p.inputs["Roughness"])
    return mt


def pebbled(name, hexcol, scale=650.0, strength=0.55, rough=0.75):
    mt = bc.mat(name, **{"Base Color": (*srgb(hexcol), 1), "Roughness": rough, "Specular IOR Level": 0.35, "Sheen Weight": 0.2})
    nt = mt.node_tree
    tc = bc.node(nt, "ShaderNodeTexCoord")
    vo = bc.node(nt, "ShaderNodeTexVoronoi", feature="SMOOTH_F1", in_Scale=scale)
    bc.link(nt, tc.outputs["Object"], vo.inputs["Vector"])
    nz = bc.node(nt, "ShaderNodeTexNoise", in_Scale=2600.0, in_Detail=3.0)
    bc.link(nt, tc.outputs["Object"], nz.inputs["Vector"])
    mx = bc.node(nt, "ShaderNodeMath", operation="ADD")
    bc.link(nt, vo.outputs["Distance"], mx.inputs[0])
    sc = bc.node(nt, "ShaderNodeMath", operation="MULTIPLY")
    sc.inputs[1].default_value = 0.25
    bc.link(nt, nz.outputs["Fac"], sc.inputs[0])
    bc.link(nt, sc.outputs["Value"], mx.inputs[1])
    bp = bc.node(nt, "ShaderNodeBump", in_Strength=strength, in_Distance=0.0001)
    bc.link(nt, mx.outputs["Value"], bp.inputs["Height"])
    bc.link(nt, bp.outputs["Normal"], nt.nodes["Principled BSDF"].inputs["Normal"])
    return mt


def xrayify(mt, edge=(0.75, 0.88, 1.0), glow=0.6):
    """Mix the material with a clear "X-ray" glass by the scene property "xray": transparent, a fresnel sheen, and
    faintly glowing edges, so the outline stays readable while the insides show."""
    nt = mt.node_tree
    out = nt.nodes["Material Output"]
    src = out.inputs["Surface"].links[0].from_socket
    attr = bc.node(nt, "ShaderNodeAttribute", attribute_type="VIEW_LAYER", attribute_name="xray")
    tr = bc.node(nt, "ShaderNodeBsdfTransparent")
    gl = bc.node(nt, "ShaderNodeBsdfGlossy", in_Roughness=0.08)
    fr = bc.node(nt, "ShaderNodeFresnel", in_IOR=1.45)
    mixg = bc.node(nt, "ShaderNodeMixShader")
    bc.link(nt, fr.outputs["Fac"], mixg.inputs["Fac"])
    bc.link(nt, tr.outputs["BSDF"], mixg.inputs[1])
    bc.link(nt, gl.outputs["BSDF"], mixg.inputs[2])
    lw = bc.node(nt, "ShaderNodeLayerWeight", in_Blend=0.25)
    pw = bc.node(nt, "ShaderNodeMath", operation="POWER")
    pw.inputs[1].default_value = 2.5
    bc.link(nt, lw.outputs["Facing"], pw.inputs[0])
    em = bc.node(nt, "ShaderNodeEmission")
    em.inputs["Color"].default_value = (*edge, 1)
    k = bc.node(nt, "ShaderNodeMath", operation="MULTIPLY")
    k.inputs[1].default_value = glow
    bc.link(nt, pw.outputs["Value"], k.inputs[0])
    bc.link(nt, k.outputs["Value"], em.inputs["Strength"])
    addx = bc.node(nt, "ShaderNodeAddShader")
    bc.link(nt, mixg.outputs["Shader"], addx.inputs[0])
    bc.link(nt, em.outputs["Emission"], addx.inputs[1])
    final = bc.node(nt, "ShaderNodeMixShader")
    bc.link(nt, attr.outputs["Fac"], final.inputs["Fac"])
    bc.link(nt, src, final.inputs[1])
    bc.link(nt, addx.outputs["Shader"], final.inputs[2])
    bc.link(nt, final.outputs["Shader"], out.inputs["Surface"])
    return mt


def fx_materials(M):
    M["body"] = sparkle_paint("cam sparkle paint", "#3b3c3f")
    M["evf"] = sparkle_paint("cam evf housing", "#2a2b2d", rough=0.5, flake=0.12, bump=0.12)
    M["rubber"] = pebbled("cam pebbled rubber", "#19191a")
    M["plastic"] = bc.micro_bump(bc.mat("cam hard plastic", **{"Base Color": (*srgb("#151515"), 1), "Roughness": 0.55}), 3500, 0.08)
    M["button"] = bc.mat("cam button", **{"Base Color": (*srgb("#101010"), 1), "Roughness": 0.35, "Coat Weight": 0.25})
    M["eyecup"] = pebbled("cam eyecup", "#0f0f10", scale=2600, strength=0.15, rough=0.6)
    M["bezel"] = bc.micro_bump(bc.mat("cam bezel", **{"Base Color": (0.006, 0.006, 0.006, 1), "Roughness": 0.7}), 4000, 0.06)
    M["mountsteel"] = bc.radial_aniso(bc.mat("cam mount", **{"Base Color": (0.78, 0.78, 0.79, 1), "Metallic": 1.0, "Roughness": 0.27}), amount=0.8)
    M["chrome"] = bc.mat("cam chrome", **{"Base Color": (0.9, 0.9, 0.9, 1), "Metallic": 1.0, "Roughness": 0.08})
    M["silver"] = bc.mat("cam shutter", **{"Base Color": (0.55, 0.55, 0.57, 1), "Metallic": 1.0, "Roughness": 0.35})
    M["lcdglass"] = bc.mat("cam lcd", **{"Base Color": (0.002, 0.002, 0.003, 1), "Roughness": 0.05, "Coat Weight": 1.0})
    M["lensbody"] = bc.micro_bump(bc.mat("lens satin black", **{"Base Color": (0.01, 0.01, 0.011, 1), "Metallic": 0.3, "Roughness": 0.42,
                                                                 "Coat Weight": 0.15}), 3000, 0.06)
    M["lensrubber"] = bc.mat("lens ring rubber", **{"Base Color": (0.008, 0.008, 0.008, 1), "Roughness": 0.62, "Specular IOR Level": 0.4})
    M["tallyred"] = bc.emissive("cam tally", (1.0, 0.05, 0.03), 0.0)
    M["white"] = bc.mat("index white", **{"Base Color": (0.85, 0.85, 0.85, 1), "Roughness": 0.4})
    M["chip_tile"] = bc.emissive("colour chip", (1.0, 0.55, 0.25), 1.5)
    for k in ("body", "evf", "rubber", "plastic", "button", "eyecup", "bezel", "lcdglass", "lensbody", "lensrubber", "mountsteel", "silver"):
        xrayify(M[k])
    return M


# ---------------------------------------------------------------- shape helpers
def loft(rings, cap=True):
    """Join closed rings of 3D points (same count) into a surface; cap the first and last."""
    bm = bmesh.new()
    vr = [[bm.verts.new(p) for p in r] for r in rings]
    n = len(rings[0])
    for a, b in zip(vr, vr[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap:
        bm.faces.new(vr[0][::-1])
        bm.faces.new(vr[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def rrect(w, h, r, n=10):
    """A rounded rectangle centred on 0 as a list of (u, v) points, counter-clockwise."""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


def catmull(ctrl, per=8):
    out = []
    n = len(ctrl)
    for i in range(n - 1):
        p0, p1, p2, p3 = (Vector(ctrl[max(i - 1, 0)]), Vector(ctrl[i]), Vector(ctrl[i + 1]), Vector(ctrl[min(i + 2, n - 1)]))
        for k in range(per):
            t = k / per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(Vector(ctrl[-1]))
    return out


def profile_x(yz, x0, x1, r_end=2.5, seg=5):
    """A YZ outline (closed, counter-clockwise in Y,Z) extruded along X from x0 to x1, end edges rounded."""
    bm = bmesh.new()
    a = [bm.verts.new((x0, y, z)) for y, z in yz]
    b = [bm.verts.new((x1, y, z)) for y, z in yz]
    n = len(yz)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(a[::-1])
    bm.faces.new(b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if r_end:
        edges = [e for e in bm.edges if abs(e.verts[0].co.x - e.verts[1].co.x) < 1e-9 and
                 (abs(e.verts[0].co.x - x0) < 1e-9 or abs(e.verts[0].co.x - x1) < 1e-9)]
        bmesh.ops.bevel(bm, geom=edges, offset=r_end, segments=seg, profile=0.5, affect="EDGES", clamp_overlap=True)
    return bm


def fillet(poly, r, n=6):
    """Round every corner of a 2D polygon with radius r (r may be a list per corner)."""
    out = []
    k = len(poly)
    for i in range(k):
        p0, p1, p2 = Vector(poly[i - 1]), Vector(poly[i]), Vector(poly[(i + 1) % k])
        rr = r[i] if isinstance(r, (list, tuple)) else r
        if rr <= 0:
            out.append(tuple(p1))
            continue
        d0, d1 = (p0 - p1).normalized(), (p2 - p1).normalized()
        ang = math.acos(max(-1, min(1, d0.dot(d1))))
        t = rr / math.tan(ang / 2)
        a, b = p1 + d0 * t, p1 + d1 * t
        for s in range(n + 1):                      # quadratic bezier a -> p1 -> b
            u = s / n
            q = a * (1 - u) ** 2 + p1 * 2 * u * (1 - u) + b * u * u
            out.append((q.x, q.y))
    return out


def scale_bm(bm):
    bmesh.ops.scale(bm, vec=(0.001, 0.001, 0.001), verts=bm.verts)
    return bm


def mk(name, bm, mt, parent, loc=(0, 0, 0), rot=(0, 0, 0), smooth=35, mm=True):
    if mm:
        scale_bm(bm)
        loc = m(*loc)
    return bc.obj(name, bm, mt, parent=parent, loc=loc, rot=rot, smooth=smooth)


def btn(name, M, parent, x, y, z, d=7.0, h=1.4, face="top", mt=None, bezel=True):
    """A slightly domed button in a body-colour bezel ring. face: top (+Z), rear (+Y), front (-Y), side (+X/-X)."""
    rot = {"top": (0, 0, 0), "rear": (-math.pi / 2, 0, 0), "front": (math.pi / 2, 0, 0), "px": (0, math.pi / 2, 0),
           "nx": (0, -math.pi / 2, 0)}[face]
    r = d / 2
    cap = bc.lathe([(0, h), (r * 0.7, h - 0.2), (r, h - 0.6), (r, 0)], 48, closed=False)
    b = mk(name, cap, mt or M["button"], parent, (x, y, z), rot)
    if bezel:
        mk(name + " bezel", bc.ring(r + 0.15, r + 1.4, -0.2, 0.5, 48, chamfer=0.2), M["body"], parent, (x, y, z), rot)
    return b


# ---------------------------------------------------------------- the body
def build_body(M, root):
    # main shell, as a YZ profile extruded along X: flat top to Y +7.5, the upper rear panel leaning forward to
    # (Y +16.6, Z +18), then the rear panel down to the base
    yz = [(YF, Z0), (YR, Z0), (YR, 18.0), (9.0, 38.0), (7.5, Z1), (YF, Z1)]
    yz = fillet(yz, [2.5, 2.5, 3.0, 2.0, 2.0, 3.2], 6)
    shell = mk("body shell", profile_x(yz, X0, X1, 2.6, 6), M["body"], root)
    # hollow it (so the X-ray shows the insides) and cut the mount throat, the exhaust recess, top holes, shoe recess
    inner = [(YF + 2.2, Z0 + 2.2), (YR - 2.2, Z0 + 2.2), (YR - 2.2, 17.0), (7.5, 36.4), (6.0, Z1 - 2.2), (YF + 2.2, Z1 - 2.2)]
    ks = [bc.cutter(scale_bm(profile_x(inner, X0 + 2.2, X1 - 2.2, 0)))]
    ks.append(bc.cutter(bc.cyl(m(23.0), m(20), 128), loc=m(MX, YF, MZ), rot=(math.pi / 2, 0, 0)))
    ks.append(bc.cutter(scale_bm(bc.rbox((10, 6.6, 55.6), 1.0, 2)), loc=m(X1, 10.15, -9.05)))           # exhaust recess
    for x in (36.6, -11.6):
        ks.append(bc.cutter(bc.cyl(m(3.3), m(10), 40), loc=m(x, -17.5, Z1)))
    ks.append(bc.cutter(scale_bm(bc.rbox((21.3, 20.9, 4.0), 1.2, 3)), loc=m(12.4, -8.65, Z1)))            # shoe recess
    ks.append(bc.cutter(bc.cyl(m(1.6), m(8), 24), loc=m(X1, 0, 18), rot=(0, math.pi / 2, 0)))             # M3 hole
    bc.cut(shell, ks, inner_mat=M["bezel"], bevel=0.0003)

    # exhaust fins: about 14 horizontal black slats in the recess (pitch 3.8)
    fins = bmesh.new()
    for i in range(14):
        z = 17.0 - i * 3.8
        g = bmesh.ops.create_cube(fins, size=1.0)
        bmesh.ops.scale(fins, vec=(4.0, 6.0, 0.9), verts=g["verts"])
        bmesh.ops.translate(fins, vec=(X1 - 3.0, 10.15, z), verts=g["verts"])
    mk("exhaust fins", fins, M["plastic"], root, smooth=0)
    # port-side doors (closed): a hair proud of the side, with their split lines
    mk("hdmi door", bc.rbox((0.5, 12.4, 25.5), 0.25, 2), M["body"], root, (X1 + 0.2, -16.1, 24.15))
    mk("usb door", bc.rbox((0.5, 12.6, 27.6), 0.25, 2), M["body"], root, (X1 + 0.2, 1.3, -8.5))
    for y in (-10.2, 1.0):
        mk("jack", bc.ring(1.6, 2.7, -0.6, 0.0, 32), M["bezel"], root, (X1 + 0.05, y, -27.1), (0, math.pi / 2, 0))
    mk("strap bar +x", bc.rbox((2.8, 12.0, 4.6), 1.0, 3), M["plastic"], root, (X1 + 1.4, -8.0, 33.4))

    # the grip: lofted from the measured front profile; rubber up to the shoulder, hard plastic above
    zf = [(-38.1, -48.2), (-34.6, -50.1), (-31.2, -50.6), (-24.4, -51.4), (-17.6, -52.0), (-10.7, -52.5), (-3.9, -51.9), (2.9, -50.2),
          (6.4, -49.1), (9.8, -48.5), (13.2, -49.2), (16.6, -52.4), (22.0, -52.6), (28.0, -52.2), (33.0, -51.0), (35.5, -48.8), (37.2, -45.5)]

    def plan(yf, shrink=0.0):
        s = shrink
        ctrl = [(-24.3 - s, YF + 0.6), (-25.4 - s, -34.0), (-28.5 - s, -43.5), (-34.0, yf + 3.2 + s), (-42.0, yf + s), (-50.5, yf + 0.2 + s),
                (-57.5, yf + 3.0 + s), (-62.6 + s, -44.0), (-64.85 + s, -34.0), (-64.85 + s, YF + 0.6)]
        return [(p.x, p.y) for p in catmull(ctrl, 6)]

    def grip_rings(z_lo, z_hi, shrink=0.0):
        rings = []
        rows = [r for r in zf if z_lo <= r[0] <= z_hi]
        if rows[0][0] > z_lo:
            rows.insert(0, (z_lo, zf[0][1]))
        for z, yf in rows:
            rings.append([(x, y, z) for x, y in plan(yf, shrink)])
        return rings
    rub = mk("grip rubber", loft(grip_rings(-38.1, 33.0)), M["rubber"], root)
    top = grip_rings(33.0, 37.2, 0.4)
    top.append([(x, y, 38.4) for x, y in plan(-42.0, 3.0)])                    # the shoulder rounds onto the top plate
    mk("grip shoulder", loft(top), M["plastic"], root)
    # the rubber also wraps the grip side (to behind the card door) and a strip on the back
    mk("side rubber", bc.rbox((0.7, 41.0, 71.6), 1.6, 3), M["rubber"], root, (X0 - 0.35, -4.0, -1.2))
    mk("card door seam", bc.rbox((0.25, 25.4, 63.2), 0.6, 2), M["bezel"], root, (X0 - 0.72, -0.15, -5.6))
    mk("card door", bc.rbox((0.7, 24.6, 62.4), 0.5, 2), M["rubber"], root, (X0 - 0.75, -0.15, -5.6))
    mk("card latch", bc.rbox((0.9, 5.0, 9.0), 0.6, 2), M["plastic"], root, (X0 - 1.0, 6.5, -2.0))
    mk("grip-side hole", bc.ring(3.2, 4.6, -0.8, 0.0, 40), M["bezel"], root, (X0 - 0.9, -28.2, 27.6), (0, -math.pi / 2, 0))
    mk("strap bar -x", bc.rbox((2.8, 15.6, 5.0), 1.0, 3), M["plastic"], root, (X0 - 1.4, -7.6, 33.5))
    mk("rear rubber", bc.rbox((10.0, 0.7, 52.0), 1.6, 3), M["rubber"], root, (X0 + 5.0, YR + 0.35, -12.0))

    # mount: matte black bezel, brushed stainless bayonet 7 mm proud, four screws, index dot
    mk("mount bezel", bc.lathe([(23.4, 0), (31.25, 0), (31.25, 1.6), (29.8, 3.2), (23.4, 3.2)], 160), M["bezel"], root, (MX, YF, MZ),
       (math.pi / 2, 0, 0))
    mk("mount flange", bc.lathe([(23.0, 3.2), (29.3, 3.2), (29.3, 6.4), (28.8, 7.0), (23.0, 7.0)], 192), M["mountsteel"], root, (MX, YF, MZ),
       (math.pi / 2, 0, 0))
    mk("mount lip", bc.ring(21.2, 23.2, 5.6, 7.0, 160), M["mountsteel"], root, (MX, YF, MZ), (math.pi / 2, 0, 0))
    for k in range(4):
        a = TAU * k / 4 + math.pi / 4
        mk("mount screw", bc.lathe([(0, 0.55), (0.9, 0.45), (1.1, 0)], 24, closed=False), M["chrome"], root,
           (MX + 26.3 * math.cos(a), FLANGE + 0.0, MZ + 26.3 * math.sin(a)), (math.pi / 2, 0, 0))
    mk("mount index", bc.cyl(0.9, 0.3, 24), M["white"], root, (MX - 8.0, FLANGE - 0.05, MZ + 27.5), (math.pi / 2, 0, 0))
    # front details: lens release, C6/REC, tally, light sensor, mic slits
    btn("lens release", M, root, -17.0, YF, -19.3, d=9.0, h=1.6, face="front", mt=M["bezel"])
    btn("C6", M, root, 56.5, YF, -30.2, d=6.6, h=1.2, face="front")
    mk("tally", bc.rbox((4.0, 1.2, 1.6), 0.4, 2), M["tallyred"], root, (54.5, YF + 0.3, Z1 - 0.2))
    mk("light sensor", bc.cyl(1.6, 0.6, 24), M["lcdglass"], root, (-20.1, YF - 0.05, 33.1), (math.pi / 2, 0, 0))
    for x in (-2.7, 27.8):
        for i in range(4):
            mk("mic slit", bc.rbox((0.9, 0.6, 2.6), 0.3, 1), M["bezel"], root, (x - 2.4 + i * 1.6, YF - 0.1, 31.3))
    mk("base band", bc.rbox((X1 - X0 - 3.0, YR - YF - 1.0, 1.2), 0.5, 2), M["bezel"], root, (0, (YF + YR) / 2, Z0 + 0.4))

    # top: shutter + zoom lever on the grip shoulder, front dial, C1-C3, REC, multi-selector, shoe, holes, hinge plate
    sh = mk("zoom lever", bc.lathe([(4.6, 0), (8.4, 0), (8.4, 2.2), (4.6, 2.2)], 64), M["plastic"], root, (-50.0, -45.0, 37.6))
    mk("zoom tab", bc.rbox((5.0, 4.0, 2.0), 0.8, 2), M["plastic"], root, (-50.0, -54.5, 38.7))
    mk("shutter", bc.lathe([(0, 3.9), (3.0, 3.6), (4.6, 2.6), (4.6, 0)], 48, closed=False), M["silver"], root, (-50.0, -45.0, 37.6))
    fd = mk("front dial", bc.ribbed(1.5, 9.75, 0.45, 72, -1.75, 1.75, duty=0.5), M["plastic"], root, (-51.2, -51.0, 23.3))
    btn("C1", M, root, -36.7, -30.3, 38.0, d=7.0)
    btn("C2", M, root, -33.6, -18.3, Z1, d=7.0)
    btn("C3", M, root, -47.7, -18.3, Z1, d=7.0)
    btn("REC", M, root, -29.5, -4.4, Z1, d=9.0, h=1.8)
    mk("REC ring", bc.ring(4.55, 5.2, 0, 0.6, 64), M["plastic"], root, (-29.5, -4.4, Z1))
    ms = mk("multi-selector", bc.lathe([(0, 2.4), (3.5, 2.1), (5.4, 1.0), (5.6, 0)], 48, closed=False), M["eyecup"], root, (-46.4, -4.9, Z1))
    rnd = random.Random(3)
    for i in range(19):
        a, rr = rnd.uniform(0, TAU), 4.6 * math.sqrt(rnd.random())
        mk("selector bump", bc.sphere(0.45, 10, 6), M["eyecup"], root, (-46.4 + math.cos(a) * rr, -4.9 + math.sin(a) * rr,
                                                                        Z1 + 2.3 - 0.06 * rr * rr), smooth=0)
    shoe = mk("shoe", bc.rbox((21.3, 20.9, 0.8), 0.6, 2), M["bezel"], root, (12.4, -8.65, Z1 - 2.6))
    for sx in (-1, 1):
        mk("shoe rail", bc.rbox((3.0, 20.0, 1.0), 0.3, 2), M["chrome"], root, (12.4 + sx * 8.4, -8.65, Z1 - 1.7))
    mk("shoe spring", bc.rbox((7.0, 9.0, 0.6), 0.3, 1), M["chrome"], root, (12.4, -11.0, Z1 - 2.0))
    for x in (36.6, -11.6):
        mk("top hole floor", bc.cyl(3.0, 0.4, 32), M["bezel"], root, (x, -17.5, Z1 - 5.0))

    # upper rear panel (leaning): rear dial, MENU, power switch
    lean = math.atan2(16.6 - 9.0, 38.0 - 18.0)
    rd = mk("rear dial", bc.ribbed(1.5, 9.6, 0.45, 72, -2.0, 2.0, duty=0.5), M["plastic"], root, (-29.7, 12.2, 33.5), (lean * 0.3, 0, 0))
    btn("MENU", M, root, -11.9, 12.4, 25.6, d=7.2, face="rear")
    mk("power switch", bc.rbox((11.0, 2.6, 4.2), 1.2, 3), M["plastic"], root, (7.4, 13.0, 25.2))
    mk("power tab", bc.rbox((3.2, 3.4, 4.6), 1.0, 2), M["plastic"], root, (9.6, 14.2, 25.2))
    # rear: buttons, control wheel
    for name, x, z in (("C5", -33.9, 17.2), ("Fn", -33.9, 2.5), ("HOME", -45.9, 2.4), ("playback", -33.9, -30.8), ("C4", -45.9, -30.8)):
        btn(name, M, root, x, YR, z, d=7.0, face="rear")
    cw = mk("control wheel", bc.ribbed(5.2, 10.8, 0.35, 90, 0.0, 2.2, duty=0.5), M["plastic"], root, (-38.8, YR, -14.0), (-math.pi / 2, 0, 0))
    btn("wheel centre", M, root, -38.8, YR + 0.4, -14.0, d=9.2, h=1.4, face="rear", bezel=False)

    # LCD: a slab on the back, hinged on the +X edge; the screen shows a frame of Saad's own footage
    lcd = mk("lcd", bc.rbox((81.6, 7.9, 52.9), 2.4, 4), M["body"], root, (17.0, (YR + 24.5) / 2, -10.0))
    mk("lcd frame", bc.rbox((78.0, 0.6, 49.6), 1.6, 3), M["bezel"], root, (17.0, 24.6, -10.0))
    scr = mk("lcd screen", bc.rbox((64.4, 0.5, 43.4), 0.6, 2), M["screen"], root, (15.1, 24.9, -10.5))
    mk("lcd hinge", bc.rbox((9.4, 8.5, 52.9), 2.2, 4), M["evf"], root, (59.7, 20.25, -10.0))

    # EVF: housing (front level with the top plate, rising 6 mm to the eyepiece), diopter box, hinge plate, eyecup
    evf = bc.empty("evf hinge", parent=root, loc=m(44.0, -10.0, 39.0))
    housing_yz = fillet([(7.5, 18.0), (37.0, 18.0), (37.0, 44.5), (26.0, 44.5), (21.0, 39.4), (7.5, 39.4)], [1.5, 2.5, 3.0, 4.0, 4.0, 1.5], 6)
    hz = [(y + 10.0, z - 39.0) for y, z in housing_yz]                       # hinge-local
    mk("evf housing", profile_x(hz, 31.0 - 44.0, 63.3 - 44.0, 2.4, 5), M["evf"], evf)
    mk("diopter box", bc.rbox((7.0, 17.0, 12.0), 1.6, 3), M["evf"], evf, (34.5 - 44.0, 25.5 + 10.0, 32.0 - 39.0))
    mk("diopter dial", bc.ribbed(1.0, 3.6, 0.3, 36, -1.5, 1.5), M["plastic"], evf, (31.0 - 44.0, 28.0 + 10.0, 34.0 - 39.0), (0, math.pi / 2, 0))
    mk("evf hinge plate", bc.rbox((33.4, 17.6, 0.6), 0.8, 2), M["evf"], evf, (43.5 - 44.0, -1.3 + 10.0, -0.1))
    btn("C7", M, evf, 63.3 - 44.0, 22.0 + 10.0, 30.0 - 39.0, d=6.0, face="px")
    for i in range(6):                                                      # raised grip ridge on the outer face
        mk("evf ridge", bc.rbox((0.8, 1.0, 8.0), 0.3, 1), M["evf"], evf, (63.5 - 44.0, 29.5 + i * 1.3 + 10.0, 36.0 - 39.0))
    # eyecup: oval rings lofted from the housing out to a flared lip, hollow
    def oval(cx, cz, w, h, y, n=48):
        return [(cx + w / 2 * math.cos(TAU * i / n) * (1 + 0.06 * math.cos(TAU * i / n)), y, cz + h / 2 * math.sin(TAU * i / n)) for i in range(n)]
    cx, cz = 42.5 - 44.0, 31.5 - 39.0
    outer = [oval(cx, cz, 38, 28, 37.0 + 10.0), oval(cx, cz, 42, 31, 44.0 + 10.0), oval(cx + 0.5, cz + 0.3, 46, 34, 52.0 + 10.0),
             oval(cx + 0.8, cz + 0.4, 48, 36, 56.5 + 10.0), oval(cx + 0.8, cz + 0.4, 46.5, 34.5, 58.0 + 10.0)]
    inner_r = [oval(cx + 0.8, cz + 0.4, 38.5, 27, 58.0 + 10.0), oval(cx + 0.5, cz + 0.2, 34, 24, 50.0 + 10.0), oval(cx, cz, 26, 19, 41.0 + 10.0)]
    bm = loft(outer + inner_r, cap=False)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mk("eyecup", bm, M["eyecup"], evf)
    mk("eyepiece glass", bc.rbox((22.0, 0.8, 16.0), 3.0, 3), M["glass"], evf, (cx, 41.5 + 10.0, cz))
    mk("eyepiece back", bc.rbox((26.0, 0.6, 20.0), 3.0, 3), M["flock"], evf, (cx, 40.0 + 10.0, cz))
    return shell, evf, lcd


# ---------------------------------------------------------------- the lens (a 24-50 mm-class zoom, no markings)
LENS = {}


def build_lens(M, root):
    """Rings from the mount: chrome bayonet, rear barrel, wide ribbed zoom ring, a control band with a switch and a
    button, a finely ribbed focus ring, front barrel with a 67 mm filter thread, deep coated glass, an 11-blade iris."""
    lens = bc.empty("lens", parent=root, loc=m(MX, FLANGE, MZ))
    lens.rotation_euler = (math.pi / 2, 0, 0)

    def piece(name, bm, mt, z=0.0, rot=(0, 0, 0)):
        return mk(name, bm, mt, lens, (0, 0, z), rot)
    piece("lens mount", bc.lathe([(21.0, 0), (23.2, 0), (23.2, 2.4), (21.0, 2.4)], 160), M["mountsteel"])
    piece("lens rear", bc.lathe([(21.0, 2.4), (30.5, 2.4), (32.5, 5.0), (34.6, 13.0), (34.6, 15.0), (21.0, 15.0)], 160), M["lensbody"])
    piece("zoom ring", bc.ribbed(33.5, 37.4, 0.9, 72, 15.5, 41.0, duty=0.55), M["lensrubber"])
    piece("control band", bc.lathe([(33.0, 41.5), (36.9, 41.5), (36.9, 49.0), (33.0, 49.0)], 160), M["lensbody"])
    sw = piece("af switch", bc.rbox((3.0, 5.0, 2.0), 0.6, 2), M["lensbody"], 45.0)
    sw.location = m(-31.5, 21.5, 45.0)
    sw.rotation_euler = (0, 0, math.radians(-34))
    hb = piece("focus hold", bc.cyl(2.6, 2.0, 32), M["button"], 45.0)
    hb.location = m(-21.0, 30.5, 45.2)
    hb.rotation_euler = (math.radians(-90), 0, math.radians(-34))
    piece("focus ring", bc.ribbed(33.5, 37.0, 0.45, 140, 49.5, 69.0, duty=0.5), M["lensrubber"])
    piece("front barrel", bc.lathe([(33.0, 69.5), (37.4, 69.5), (37.4, 88.0), (36.6, 91.6), (35.0, 92.3), (33.6, 91.2), (33.6, 86.0), (33.0, 85.0)], 192),
          M["lensbody"])
    piece("lens tube", bc.lathe([(21.0, 2.4), (32.0, 2.4), (32.0, 86.0), (31.2, 86.0), (31.2, 3.4), (21.0, 3.4)], 128), M["flock"])
    elements = [("rear element", 6.0, 18.0, 6.5, 0.05, 0.08), ("element 5", 18.0, 20.5, 6.5, 0.07, 0.15),
                ("element 4", 30.0, 21.0, 3.0, -0.06, -0.08), ("element 3", 50.0, 25.0, 8.0, 0.09, 0.07),
                ("element 2", 64.0, 28.5, 5.0, -0.12, 0.15), ("front element", 75.0, 30.6, 10.0, -0.2, 0.075)]
    for name, z, r, t, rr, rf in elements:
        LENS[name] = piece(name, bc.lathe(bc.lens_profile(r, t, rr * 1000, rf * 1000), 160, closed=False), M["glass"], z)
    iris = bc.empty("iris", parent=lens, loc=m(0, 0, 42.0))
    LENS["iris"] = iris
    LENS["blades"] = []
    for k in range(11):
        piv = bc.empty("blade pivot", parent=iris)
        piv.rotation_euler = (0, 0, TAU * k / 11)
        LENS["blades"].append(bc.obj("iris blade", bc.blade_mesh(), M["blade"], parent=piv, loc=(0, 0, 0.00007 * k), smooth=0))
    mk("iris housing", bc.ring(26.0, 31.5, -0.4, 1.2, 128), M["lensbody"], iris)
    set_iris(4.0)
    return lens


IRIS_OPEN, IRIS_HIDE = 0.0215, 0.0275


def set_iris(fnum):
    a = max(IRIS_OPEN * min(1.0, 2.8 / fnum), 0.0014)
    for b in LENS["blades"]:
        b.scale = (0.0105, IRIS_HIDE - a, 0.00015)
        b.location = (0.0, a, b.location.z)
    return a


# ---------------------------------------------------------------- inside
def build_insides(M, root):
    """The parts the X-ray shows: sensor (18 mm behind the flange), stabiliser plate, main board with the processor, the
    AI core and the colour chip (3 x 3 tiles the crew repaints), the fan by the exhaust fins, the battery in the grip."""
    bc.LX, bc.LZ, bc.MOUNT_FACE, bc.FRONT, bc.W, bc.H = m(MX), m(MZ), m(FLANGE), m(YF), m(X1 - X0), m(Z1 - Z0)
    board = bc.build_insides(M, root)
    for o in list(D.objects):                                             # this camera doesn't come apart: no explode
        for k in ("ex", "exd", "exr", "base", "base_rot"):
            if k in o.keys():
                del o[k]
    D.objects["fan"].location = m(54.0, 6.0, -10.0)
    D.objects["cooling fins"].location = m(-2.0, 6.0, -10.0)
    D.objects["heat pipe"].location = m(20.0, 4.0, 10.0)
    D.objects["battery"].location = m(-46.0, -24.0, -8.0)
    D.objects["battery"].dimensions = m(28.0, 40.0, 54.0)
    D.objects["flex cable"].location = m(MX - 2.0, -6.0, -26.0)
    # the colour chip: nine tiles on the board, warm until the crew repaints them
    chip = bc.empty("colour chip", parent=board, loc=(m(-34.0), 0.0012, m(-18.0)))
    tiles = []
    for i in range(9):
        t = bc.obj("chip tile", bc.rbox((0.0034, 0.0006, 0.0034), 0.0003, 1), M["chip_tile"], parent=chip,
                   loc=(((i % 3) - 1) * 0.0040, 0.0, ((i // 3) - 1) * 0.0040), smooth=0)
        tiles.append(t)
    return board


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    M = bc.build_materials()
    M = fx_materials(M)
    shot = ROOT / "video" / "blender" / "cache" / "screen_field.jpg"           # the LCD shows a frame of Saad's own footage
    if shot.exists():
        im = D.images.load(str(shot))
        im.pack()
        for n in M["screen"].node_tree.nodes:
            if n.type == "TEX_IMAGE":
                n.image = im
        M["screen"].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.4
    root = bc.empty("camera rig")
    build_body(M, root)
    build_lens(M, root)
    build_insides(M, root)
    bc.build_agent(M, "agent", "crew proto")
    proto = D.collections["crew proto"]
    L = D.lights.new("agent light", "POINT")                               # each agent spills a little light on what it touches
    L.energy, L.color, L.shadow_soft_size = 0.004, (1.0, 0.45, 0.12), 0.0006
    lo = D.objects.new("agent light", L)
    proto.objects.link(lo)
    lo.parent = D.objects["agent"]
    lo.location = (0, -0.0006, -0.0016)
    bc.build_studio()
    C.scene["xray"] = 0.0
    bc.bake([ob for ob in D.objects if ob.type == "MESH" and ob.modifiers])
    C.view_layer.layer_collection.children["crew proto"].exclude = True
    OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT), compress=True)
    print("camera objects:", len(D.objects), "->", OUT)


if __name__ == "__main__":
    main()
