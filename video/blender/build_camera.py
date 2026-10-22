"""Build the films' photoreal camera in Blender, from nothing, and save it to video/blender/cache/camera.blend.

An original compact cinema camera in the spirit of a small full-frame cinema body (no maker's name, no logo, not a
copy of any product): a painted magnesium shell, a rubber grip, machined dials, vents, ports and screws, a fast prime
lens with six glass elements and an eleven-blade iris, and the insides for the exploded view (sensor, stabiliser plate,
main board with the AI core, cooling fan, battery). Plus the crew: tiny orange agent robots that work inside it.

Real scale (metres), so depth of field behaves like a real macro lens. The camera faces -Y; Z is up.
Every part remembers where it sits assembled and where it flies to in the exploded view (custom properties
"base", "ex", "exd", "exr"); shots.py animates between the two.

Run: /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P video/blender/build_camera.py
"""
import math
import random
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "video" / "blender" / "cache" / "camera.blend"
D, C = bpy.data, bpy.context
TAU = math.tau

# the lens axis: the mount sits a little toward the side away from the grip, a little low
LX, LZ = 0.008, -0.002
FRONT = -0.024                       # front face of the body (y)
MOUNT_FACE = FRONT - 0.0025          # front face of the steel bayonet
W, H, DEP = 0.129, 0.0775, 0.048     # body block


# ---------------------------------------------------------------- materials
def mat(name, **inp):
    m = D.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    for k, v in inp.items():
        p.inputs[k].default_value = v
    return m


def link(nt, a, b):
    nt.links.new(a, b)


def node(nt, kind, **props):
    n = nt.nodes.new(kind)
    for k, v in props.items():
        if k.startswith("in_"):
            n.inputs[k[3:].replace("_", " ")].default_value = v
        else:
            setattr(n, k, v)
    return n


def micro_bump(m, scale, strength, dist=0.00004, rough=None, rough_scale=60):
    """Fine grain (paint, bead blast or rubber) as a bump, and an optional slow roughness wobble."""
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    tc = node(nt, "ShaderNodeTexCoord")
    nz = node(nt, "ShaderNodeTexNoise", in_Scale=scale, in_Detail=4.0)
    link(nt, tc.outputs["Object"], nz.inputs["Vector"])
    b = node(nt, "ShaderNodeBump", in_Strength=strength, in_Distance=dist)
    link(nt, nz.outputs["Fac"], b.inputs["Height"])
    link(nt, b.outputs["Normal"], p.inputs["Normal"])
    if rough:
        n2 = node(nt, "ShaderNodeTexNoise", in_Scale=rough_scale, in_Detail=2.0)
        link(nt, tc.outputs["Object"], n2.inputs["Vector"])
        mr = node(nt, "ShaderNodeMapRange", in_To_Min=rough[0], in_To_Max=rough[1])
        mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = 0.35, 0.65
        link(nt, n2.outputs["Fac"], mr.inputs["Value"])
        link(nt, mr.outputs["Result"], p.inputs["Roughness"])
    return m


def radial_aniso(m, axis="Z", amount=0.75):
    """Turned metal: concentric brushing around the part's own axis."""
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    t = node(nt, "ShaderNodeTangent", direction_type="RADIAL", axis=axis)
    link(nt, t.outputs["Tangent"], p.inputs["Tangent"])
    p.inputs["Anisotropic"].default_value = amount
    return m


def emissive(name, color, strength):
    m = D.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.02, 0.01, 0.005, 1)
    p.inputs["Emission Color"].default_value = (*color, 1)
    p.inputs["Emission Strength"].default_value = strength
    p.inputs["Roughness"].default_value = 0.4
    return m


ORANGE = (1.0, 0.30, 0.045)          # the agents' colour (the site's AI orange, in linear light)


def build_materials():
    M = {}
    M["body"] = micro_bump(mat("magnesium paint", **{"Base Color": (0.016, 0.017, 0.018, 1), "Metallic": 0.45, "Roughness": 0.36,
                                                       "Coat Weight": 0.3, "Coat Roughness": 0.22}), 2600, 0.07, rough=(0.3, 0.42))
    M["raw"] = micro_bump(mat("raw magnesium", **{"Base Color": (0.42, 0.43, 0.45, 1), "Metallic": 1.0, "Roughness": 0.38}), 1800, 0.12)
    M["rubber"] = mat("rubber", **{"Base Color": (0.011, 0.011, 0.012, 1), "Roughness": 0.72, "Specular IOR Level": 0.35,
                                   "Sheen Weight": 0.25, "Sheen Roughness": 0.4})
    nt = M["rubber"].node_tree                                     # pebbled rubber: voronoi cells as bumps
    tc = node(nt, "ShaderNodeTexCoord")
    vo = node(nt, "ShaderNodeTexVoronoi", feature="SMOOTH_F1", in_Scale=1400.0)
    link(nt, tc.outputs["Object"], vo.inputs["Vector"])
    bp = node(nt, "ShaderNodeBump", in_Strength=0.55, in_Distance=0.00008)
    link(nt, vo.outputs["Distance"], bp.inputs["Height"])
    link(nt, bp.outputs["Normal"], nt.nodes["Principled BSDF"].inputs["Normal"])
    M["rubber_plain"] = mat("rubber plain", **{"Base Color": (0.012, 0.012, 0.013, 1), "Roughness": 0.62, "Specular IOR Level": 0.4})
    M["alu"] = radial_aniso(mat("turned aluminium", **{"Base Color": (0.80, 0.81, 0.83, 1), "Metallic": 1.0, "Roughness": 0.2}))
    M["alu_dark"] = radial_aniso(mat("dark anodised", **{"Base Color": (0.035, 0.036, 0.04, 1), "Metallic": 0.9, "Roughness": 0.26}))
    M["steel"] = radial_aniso(mat("polished steel", **{"Base Color": (0.86, 0.87, 0.88, 1), "Metallic": 1.0, "Roughness": 0.09}), amount=0.5)
    M["screw"] = mat("screw steel", **{"Base Color": (0.55, 0.56, 0.58, 1), "Metallic": 1.0, "Roughness": 0.25})
    M["barrel"] = micro_bump(mat("lens barrel", **{"Base Color": (0.018, 0.018, 0.02, 1), "Metallic": 0.55, "Roughness": 0.33,
                                                    "Coat Weight": 0.25, "Coat Roughness": 0.2}), 3000, 0.05)
    M["flock"] = mat("flocking", **{"Base Color": (0.004, 0.004, 0.004, 1), "Roughness": 0.9, "Specular IOR Level": 0.15})
    M["glass"] = mat("coated glass", **{"Base Color": (1, 1, 1, 1), "Transmission Weight": 1.0, "Roughness": 0.0, "IOR": 1.58,
                                         "Thin Film Thickness": 260.0, "Thin Film IOR": 1.38})
    M["glass_cover"] = mat("sensor cover glass", **{"Base Color": (0.55, 0.85, 1.0, 1), "Transmission Weight": 1.0, "Roughness": 0.02,
                                                     "IOR": 1.5, "Thin Film Thickness": 650.0, "Thin Film IOR": 1.45})
    M["blade"] = mat("iris blade", **{"Base Color": (0.012, 0.012, 0.013, 1), "Metallic": 0.7, "Roughness": 0.3})
    M["orange_ring"] = radial_aniso(mat("orange anodised", **{"Base Color": (1.0, 0.24, 0.03, 1), "Metallic": 0.75, "Roughness": 0.28}), amount=0.5)
    M["red"] = mat("rec red", **{"Base Color": (0.55, 0.012, 0.01, 1), "Roughness": 0.3, "Coat Weight": 0.6})
    M["paint_white"] = mat("index white", **{"Base Color": (0.8, 0.8, 0.78, 1), "Roughness": 0.5})
    M["ceramic"] = mat("ceramic", **{"Base Color": (0.55, 0.5, 0.42, 1), "Roughness": 0.55})
    M["gold"] = mat("gold", **{"Base Color": (1.0, 0.72, 0.36, 1), "Metallic": 1.0, "Roughness": 0.22})
    M["copper"] = radial_aniso(mat("copper", **{"Base Color": (0.95, 0.52, 0.32, 1), "Metallic": 1.0, "Roughness": 0.3}))
    M["pcb"] = micro_bump(mat("solder mask", **{"Base Color": (0.012, 0.016, 0.015, 1), "Roughness": 0.35, "Coat Weight": 0.6,
                                                 "Coat Roughness": 0.15}), 900, 0.05)
    M["chip"] = micro_bump(mat("chip", **{"Base Color": (0.02, 0.02, 0.022, 1), "Roughness": 0.55}), 4000, 0.08)
    M["lid"] = radial_aniso(mat("chip lid", **{"Base Color": (0.7, 0.71, 0.72, 1), "Metallic": 1.0, "Roughness": 0.3}))
    M["flex"] = mat("flex cable", **{"Base Color": (0.75, 0.35, 0.05, 1), "Roughness": 0.3, "Subsurface Weight": 0.3,
                                      "Coat Weight": 0.5})
    M["battery"] = micro_bump(mat("battery", **{"Base Color": (0.05, 0.05, 0.055, 1), "Roughness": 0.5}), 2000, 0.05)
    M["ai"] = emissive("ai glow", ORANGE, 6.0)
    M["ai_soft"] = emissive("ai trace", ORANGE, 2.5)
    M["tally"] = emissive("tally", (1.0, 0.08, 0.05), 0.0)
    # the sensor die: a microlens grid that splits light into colour
    die = mat("sensor die", **{"Base Color": (0.03, 0.035, 0.06, 1), "Metallic": 0.6, "Roughness": 0.12,
                               "Thin Film Thickness": 560.0, "Thin Film IOR": 1.9})
    nt = die.node_tree
    tc = node(nt, "ShaderNodeTexCoord")
    sep = node(nt, "ShaderNodeSeparateXYZ")
    link(nt, tc.outputs["Object"], sep.inputs["Vector"])
    w1 = node(nt, "ShaderNodeTexWave", wave_type="BANDS", bands_direction="X", in_Scale=1.0)
    w2 = node(nt, "ShaderNodeTexWave", wave_type="BANDS", bands_direction="Z", in_Scale=1.0)
    for w in (w1, w2):
        w.inputs["Scale"].default_value = 2600.0
        link(nt, tc.outputs["Object"], w.inputs["Vector"])
    mul = node(nt, "ShaderNodeMath", operation="MULTIPLY")
    link(nt, w1.outputs["Fac"], mul.inputs[0])
    link(nt, w2.outputs["Fac"], mul.inputs[1])
    bp = node(nt, "ShaderNodeBump", in_Strength=0.35, in_Distance=0.00002)
    link(nt, mul.outputs["Value"], bp.inputs["Height"])
    link(nt, bp.outputs["Normal"], nt.nodes["Principled BSDF"].inputs["Normal"])
    M["die"] = die
    # the rear screen shows a real frame from the camera's live view
    lcd = D.materials.new("screen")
    lcd.use_nodes = True
    nt = lcd.node_tree
    p = nt.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1)
    p.inputs["Roughness"].default_value = 0.04
    p.inputs["Coat Weight"].default_value = 1.0
    img_path = ROOT / "site" / "media" / "real" / "test1_05.jpg"
    if img_path.exists():
        im = D.images.load(str(img_path))
        im.pack()
        tx = node(nt, "ShaderNodeTexImage", image=im)
        link(nt, tx.outputs["Color"], p.inputs["Emission Color"])
        p.inputs["Emission Strength"].default_value = 0.35
    M["screen"] = lcd
    M["agent_shell"] = mat("agent shell", **{"Base Color": (*ORANGE, 1), "Roughness": 0.3, "Coat Weight": 0.8, "Coat Roughness": 0.08,
                                             "Subsurface Weight": 0.15})
    M["agent_dark"] = mat("agent joint", **{"Base Color": (0.03, 0.03, 0.033, 1), "Metallic": 0.8, "Roughness": 0.3})
    M["agent_thrust"] = emissive("agent thruster", (1.0, 0.45, 0.12), 12.0)
    M["agent_tip"] = emissive("agent tip", (1.0, 0.75, 0.45), 8.0)
    M["visor"] = visor_material()
    return M


def visor_material():
    """Black glass visor with a live histogram in it: bars whose heights dance with the 'W' of a 4D noise (keyframed)."""
    m = D.materials.new("agent visor")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.005, 0.005, 0.006, 1)
    p.inputs["Roughness"].default_value = 0.05
    p.inputs["Coat Weight"].default_value = 1.0
    tc = node(nt, "ShaderNodeTexCoord")
    sep = node(nt, "ShaderNodeSeparateXYZ")
    link(nt, tc.outputs["Generated"], sep.inputs["Vector"])
    snap = node(nt, "ShaderNodeMath", operation="SNAP")              # bars: x snapped to 1/18
    snap.inputs[1].default_value = 1 / 18
    link(nt, sep.outputs["X"], snap.inputs[0])
    nz = node(nt, "ShaderNodeTexNoise", noise_dimensions="4D", in_Scale=7.0, in_Detail=1.0)
    nz.name = "histogram"
    cx = node(nt, "ShaderNodeCombineXYZ")
    link(nt, snap.outputs["Value"], cx.inputs["X"])
    link(nt, cx.outputs["Vector"], nz.inputs["Vector"])
    # bar height (0.25..0.95 of the visor band) vs this point's height inside the band
    band = node(nt, "ShaderNodeMapRange", in_From_Min=0.52, in_From_Max=0.72)
    link(nt, sep.outputs["Z"], band.inputs["Value"])
    hi = node(nt, "ShaderNodeMapRange", in_From_Min=0.3, in_From_Max=0.7, in_To_Min=0.15, in_To_Max=1.0)
    link(nt, nz.outputs["Fac"], hi.inputs["Value"])
    lt = node(nt, "ShaderNodeMath", operation="LESS_THAN")
    link(nt, band.outputs["Result"], lt.inputs[0])
    link(nt, hi.outputs["Result"], lt.inputs[1])
    gap = node(nt, "ShaderNodeMath", operation="FRACT")               # thin gaps between bars
    s18 = node(nt, "ShaderNodeMath", operation="MULTIPLY")
    s18.inputs[1].default_value = 18
    link(nt, sep.outputs["X"], s18.inputs[0])
    link(nt, s18.outputs["Value"], gap.inputs[0])
    gl = node(nt, "ShaderNodeMath", operation="LESS_THAN")
    gl.inputs[1].default_value = 0.72
    link(nt, gap.outputs["Value"], gl.inputs[0])
    inband = node(nt, "ShaderNodeMath", operation="LESS_THAN")       # only inside the band
    inband.inputs[1].default_value = 1.0
    link(nt, band.outputs["Result"], inband.inputs[0])
    gt0 = node(nt, "ShaderNodeMath", operation="GREATER_THAN")
    gt0.inputs[1].default_value = 0.0
    link(nt, band.outputs["Result"], gt0.inputs[0])
    m1 = node(nt, "ShaderNodeMath", operation="MULTIPLY")
    link(nt, lt.outputs["Value"], m1.inputs[0])
    link(nt, gl.outputs["Value"], m1.inputs[1])
    m2 = node(nt, "ShaderNodeMath", operation="MULTIPLY")
    link(nt, m1.outputs["Value"], m2.inputs[0])
    link(nt, gt0.outputs["Value"], m2.inputs[1])
    m3 = node(nt, "ShaderNodeMath", operation="MULTIPLY")
    m3.inputs[1].default_value = 7.0
    link(nt, m2.outputs["Value"], m3.inputs[0])
    p.inputs["Emission Color"].default_value = (1.0, 0.55, 0.2, 1)
    link(nt, m3.outputs["Value"], p.inputs["Emission Strength"])
    return m


# ---------------------------------------------------------------- mesh helpers
COLS = {}


def col(name):
    if name not in COLS:
        c = D.collections.new(name)
        C.scene.collection.children.link(c)
        COLS[name] = c
    return COLS[name]


def obj(name, bm_or_me, m=None, collection="camera", parent=None, loc=(0, 0, 0), rot=(0, 0, 0), smooth=35):
    if isinstance(bm_or_me, bmesh.types.BMesh):
        me = D.meshes.new(name)
        bm_or_me.to_mesh(me)
        bm_or_me.free()
    else:
        me = bm_or_me
    ob = D.objects.new(name, me)
    col(collection).objects.link(ob)
    if m is not None:
        me.materials.append(m)
    if smooth:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(smooth))
        wn = ob.modifiers.new("flat faces", "WEIGHTED_NORMAL")
        wn.keep_sharp = True
        wn.weight = 80
    ob.location = loc
    ob.rotation_euler = rot
    if parent:
        ob.parent = parent
    return ob


def empty(name, collection="camera", parent=None, loc=(0, 0, 0)):
    e = D.objects.new(name, None)
    col(collection).objects.link(e)
    e.empty_display_size = 0.01
    e.location = loc
    if parent:
        e.parent = parent
    return e


def rbox(size, r, seg=5, sharp=()):
    """Rounded box centred on the origin; faces whose normal is in `sharp` keep crisp edges (for split shells)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bm.normal_update()
    skip = set()
    for f in bm.faces:
        for d in sharp:
            if f.normal.dot(Vector(d)) > 0.99:
                skip.update(f.edges)
    edges = [e for e in bm.edges if e not in skip]
    if r > 0:
        bmesh.ops.bevel(bm, geom=edges, offset=r, segments=seg, profile=0.5, affect="EDGES", clamp_overlap=True)
    return bm


def lathe(prof, seg=160, closed=True):
    """Spin a (radius, z) profile around Z. Closed profiles make solid rings; ends on the axis make caps."""
    bm = bmesh.new()
    vs = [bm.verts.new((r, 0, z)) for r, z in prof]
    es = [bm.edges.new((vs[i], vs[i + 1])) for i in range(len(vs) - 1)]
    if closed:
        es.append(bm.edges.new((vs[-1], vs[0])))
    bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), angle=TAU, steps=seg, use_merge=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def ring(r_in, r_out, z0, z1, seg=160, chamfer=0.0):
    c = chamfer
    if c:
        prof = [(r_in, z0), (r_out - c, z0), (r_out, z0 + c), (r_out, z1 - c), (r_out - c, z1), (r_in, z1)]
    else:
        prof = [(r_in, z0), (r_out, z0), (r_out, z1), (r_in, z1)]
    return lathe(prof, seg)


def ribbed(r_in, r_out, rib, n, z0, z1, duty=0.5, sub=4):
    """A ring with n ribs on the outside (knurled dials, focus-ring grip): square-ish teeth."""
    bm = bmesh.new()
    N = n * sub
    loops = []
    for z in (z0, z1):
        outer, inner = [], []
        for i in range(N):
            a = TAU * i / N
            r = r_out if (i % sub) / sub < duty else r_out - rib
            outer.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
            inner.append(bm.verts.new((r_in * math.cos(a), r_in * math.sin(a), z)))
        loops.append((outer, inner))
    (ob0, ib0), (ob1, ib1) = loops
    for i in range(N):
        j = (i + 1) % N
        bm.faces.new((ob0[i], ob0[j], ob1[j], ob1[i]))
        bm.faces.new((ib0[j], ib0[i], ib1[i], ib1[j]))
        bm.faces.new((ob1[i], ob1[j], ib1[j], ib1[i]))
        bm.faces.new((ob0[j], ob0[i], ib0[i], ib0[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def cyl(r, depth, seg=48, r2=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=depth)
    return bm


def sphere(r, u=32, v=16):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=r)
    return bm


def bake(objs):
    """Apply every modifier (booleans, bevels) so frames don't re-evaluate them."""
    dg = C.evaluated_depsgraph_get()
    dg.update()
    for ob in objs:
        if ob.type != "MESH" or not ob.modifiers:
            continue
        me = D.meshes.new_from_object(ob.evaluated_get(dg))
        ob.modifiers.clear()
        old = ob.data
        ob.data = me
        D.meshes.remove(old)


def cut(ob, cutters, inner_mat=None, bevel=0.0004):
    """Boolean the cutters out of ob (exact solver); new faces take the cutters' material; then soften the new edges."""
    c = D.collections.new(ob.name + " cutters")
    C.scene.collection.children.link(c)
    for k in cutters:
        for cc in k.users_collection:
            cc.objects.unlink(k)
        c.objects.link(k)
        k.hide_render = True
        if inner_mat is not None and not k.data.materials:
            k.data.materials.append(inner_mat)
    for old in list(ob.modifiers):
        ob.modifiers.remove(old)
    ob.data.shade_smooth()
    ob.data.set_sharp_from_angle(angle=math.radians(35))
    m = ob.modifiers.new("cut", "BOOLEAN")
    m.operation, m.solver, m.operand_type, m.collection = "DIFFERENCE", "EXACT", "COLLECTION", c
    m.material_mode = "TRANSFER"
    if bevel:
        b = ob.modifiers.new("soften", "BEVEL")
        b.width, b.segments, b.limit_method, b.angle_limit = bevel, 2, "ANGLE", math.radians(40)
        b.harden_normals = False
    wn = ob.modifiers.new("flat faces", "WEIGHTED_NORMAL")
    wn.keep_sharp, wn.weight = True, 80
    bake([ob])
    for k in list(c.objects):
        D.objects.remove(k)
    D.collections.remove(c)


def cutter(bm, loc=(0, 0, 0), rot=(0, 0, 0)):
    me = D.meshes.new("cutter")
    bm.to_mesh(me)
    bm.free()
    k = D.objects.new("cutter", me)
    C.scene.collection.objects.link(k)
    k.location, k.rotation_euler = loc, rot
    return k


PARTS = []


def part(ob, ex=(0, 0, 0), exd=0.0, exr=(0, 0, 0)):
    """Register an exploded-view part: where it flies (offset), when (delay 0..0.6) and how it tumbles."""
    ob["base"] = list(ob.location)
    ob["base_rot"] = list(ob.rotation_euler)
    ob["ex"] = list(ex)
    ob["exd"] = exd
    ob["exr"] = list(exr)
    PARTS.append(ob)
    return ob


AXIS_ROT = (math.pi / 2, 0, 0)       # lathe Z -> world -Y (out of the lens)


def on_axis(y):
    return (LX, y, LZ)


# ---------------------------------------------------------------- the body
def build_body(M, root):
    seam = -0.004
    # shells: hollow halves that meet at a crisp seam, open toward each other
    fy0, fy1 = FRONT, seam
    front = obj("front shell", rbox((W, fy1 - fy0, H), 0.0055, 6, sharp=[(0, 1, 0)]), M["body"], parent=root,
                loc=(0, (fy0 + fy1) / 2, 0))
    ry0, ry1 = seam + 0.0003, -FRONT
    rear = obj("rear shell", rbox((W, ry1 - ry0, H), 0.0055, 6, sharp=[(0, -1, 0)]), M["body"], parent=root,
               loc=(0, (ry0 + ry1) / 2, 0))
    wall = 0.0022
    hollow_f = cutter(rbox((W - 2 * wall, (fy1 - fy0) - wall + 0.002, H - 2 * wall), 0.003, 3), loc=(0, (fy0 + fy1) / 2 + wall / 2 + 0.001, 0))
    mount_hole = cutter(cyl(0.0236, 0.02, 128), loc=on_axis(FRONT), rot=AXIS_ROT)
    cut(front, [hollow_f, mount_hole], inner_mat=M["raw"])
    hollow_r = cutter(rbox((W - 2 * wall, (ry1 - ry0) - wall + 0.002, H - 2 * wall), 0.003, 3), loc=(0, (ry0 + ry1) / 2 - wall / 2 - 0.001, 0))
    ks = [hollow_r]
    # vents on the side away from the grip (+X): eleven rounded slots
    for i in range(11):
        ks.append(cutter(rbox((0.01, 0.0016, 0.019), 0.0007, 3), loc=(W / 2, 0.001 + i * 0.0021, 0.013)))
    # ports under the vents: HDMI, USB-C, two 3.5 mm jacks
    ks.append(cutter(rbox((0.01, 0.0142, 0.0052), 0.0008, 3), loc=(W / 2, 0.011, -0.0115)))
    ks.append(cutter(rbox((0.01, 0.0090, 0.0033), 0.00155, 4), loc=(W / 2, 0.011, -0.0205)))
    for j, y in enumerate((0.001, 0.019)):
        ks.append(cutter(cyl(0.0029, 0.01, 40), loc=(W / 2, y, -0.029), rot=(0, math.pi / 2, 0)))
    # three 1/4"-20 holes on top, two on the side
    for x in (-0.012, 0.016, 0.044):
        ks.append(cutter(cyl(0.00335, 0.012, 48), loc=(x, 0.010, H / 2)))
    cut(rear, ks, inner_mat=M["raw"])
    part(front, ex=(0, -0.045, 0), exd=0.08, exr=(0, 0, 0))
    part(rear, ex=(0, 0.20, 0), exd=0.12)

    # inside the vents: a dark baffle, so you see depth, not daylight
    baffle = obj("vent baffle", rbox((0.0006, 0.026, 0.024), 0.0002, 1), M["flock"], parent=rear, loc=(W / 2 - 0.004 - rear.location.x, 0.0115 - rear.location.y, 0.013))
    # threaded inserts in the top holes: steel rings with thread grooves
    for x in (-0.012, 0.016, 0.044):
        obj("thread insert", ring(0.0027, 0.0034, -0.006, -0.0003, 48), M["screw"], parent=rear, loc=(x, 0.010 - rear.location.y, H / 2))
        floor = obj("hole floor", cyl(0.0028, 0.0004, 32), M["flock"], parent=rear, loc=(x, 0.010 - rear.location.y, H / 2 - 0.0058))
    # port insides
    ry = rear.location.y
    obj("hdmi shell", rbox((0.004, 0.0136, 0.0046), 0.0006, 2), M["screw"], parent=rear, loc=(W / 2 - 0.0035, 0.011 - ry, -0.0115))
    obj("hdmi tongue", rbox((0.0045, 0.010, 0.0013), 0.0002, 1), M["chip"], parent=rear, loc=(W / 2 - 0.0028, 0.011 - ry, -0.0113))
    obj("usb shell", rbox((0.004, 0.0084, 0.0027), 0.0012, 3), M["screw"], parent=rear, loc=(W / 2 - 0.0035, 0.011 - ry, -0.0205))
    obj("usb tongue", rbox((0.0045, 0.0066, 0.0007), 0.0002, 1), M["chip"], parent=rear, loc=(W / 2 - 0.0028, 0.011 - ry, -0.0205))
    for y in (0.001, 0.019):
        obj("jack", ring(0.0018, 0.0026, -0.004, 0.0, 40), M["screw"], parent=rear, loc=(W / 2 - 0.0008, y - ry, -0.029),
            rot=(0, math.pi / 2, 0))

    # grip: a pebbled-rubber block wrapped round the front corner on the operator's right
    gx0, gx1, gy0, gy1 = -W / 2 - 0.001, -0.031, FRONT - 0.03, 0.006
    grip = obj("grip", grip_mesh(), M["rubber"], parent=root, loc=(0, 0, -0.0015))
    part(grip, ex=(-0.07, -0.03, 0), exd=0.1, exr=(0, 0, -0.35))
    gtop = -0.0015 + (H - 0.004) / 2
    # a thumb rest on the back, same rubber
    thumb = obj("thumb rest", rbox((0.028, 0.004, 0.016), 0.0018, 4), M["rubber"], parent=root, loc=(-0.048, -FRONT + 0.0012, 0.028))
    part(thumb, ex=(-0.02, 0.24, 0.02), exd=0.2)

    # bayonet: polished steel ring with three tabs and four countersunk screws, and the orange ring (the only colour outside)
    bay = obj("bayonet", ring(0.0232, 0.0292, 0, 0.0025, 192, chamfer=0.0004), M["steel"], parent=root, loc=on_axis(FRONT), rot=AXIS_ROT)
    obj("bayonet lip", ring(0.0212, 0.0234, 0.0, 0.0012, 160), M["steel"], parent=bay)
    for k in range(4):
        a = TAU * k / 4 + math.pi / 4
        s = screw(M, parent=bay, loc=(0.0262 * math.cos(a), 0.0262 * math.sin(a), 0.0025), r=0.0011)
    part(bay, ex=(0, -0.085, 0), exd=0.05, exr=(0, 0, 0.6))
    oring = obj("orange ring", ring(0.0292, 0.0306, 0.0, 0.0012, 192, chamfer=0.0002), M["orange_ring"], parent=root, loc=on_axis(FRONT - 0.0004),
                rot=AXIS_ROT)
    part(oring, ex=(0, -0.075, 0), exd=0.06)
    rel = obj("lens release", cyl(0.0034, 0.002, 48), M["alu"], parent=root, loc=(LX + 0.034, FRONT - 0.0009, LZ + 0.012), rot=AXIS_ROT)
    part(rel, ex=(0.03, -0.06, 0.01), exd=0.15, exr=(1.5, 0, 0))
    tally = obj("tally", cyl(0.0012, 0.0008, 24), M["tally"], parent=root, loc=(LX + 0.040, FRONT - 0.0003, 0.029), rot=AXIS_ROT)

    # top: record button with red ring on the grip, the front dial, the rear dial, a C1 button
    rec_ring = obj("rec ring", ring(0.0036, 0.0052, 0, 0.0012, 96, chamfer=0.0002), M["red"], parent=root, loc=(-0.050, -0.038, gtop - 0.0003))
    rec_btn = obj("rec button", lathe([(0, 0.0022), (0.0033, 0.0018), (0.0035, 0.0)], 96, closed=False), M["alu_dark"], parent=root,
                  loc=(-0.050, -0.038, gtop - 0.0003))
    part(rec_ring, ex=(0, 0, 0.06), exd=0.25, exr=(0, 0, 1.2))
    part(rec_btn, ex=(0, 0, 0.085), exd=0.3)
    fd = obj("front dial", ribbed(0.0015, 0.0085, 0.00045, 60, -0.0022, 0.0022, duty=0.5), M["alu"], parent=root,
             loc=(-0.047, FRONT - 0.026, gtop - 0.0022))
    part(fd, ex=(-0.01, -0.02, 0.07), exd=0.28, exr=(0, 0, 2.5))
    rd = obj("rear dial", ribbed(0.0015, 0.0095, 0.0005, 64, -0.0025, 0.0025, duty=0.5), M["alu"], parent=root,
             loc=(-0.030, 0.019, H / 2 - 0.0005))
    rd_cap = obj("rear dial cap", lathe([(0, 0.0026), (0.0085, 0.0026), (0.009, 0.0022)], 96, closed=False), M["alu"], parent=rd)
    part(rd, ex=(0, 0.03, 0.075), exd=0.3, exr=(0, 0, -2.5))
    c1 = obj("C1 button", lathe([(0, 0.0013), (0.0026, 0.0011), (0.0028, 0.0)], 64, closed=False), M["alu_dark"], parent=root,
             loc=(-0.013, 0.019, H / 2))
    part(c1, ex=(0, 0.02, 0.06), exd=0.33)

    # back: the screen on its hinge, the control wheel, a joystick, three buttons
    lcd = obj("screen body", rbox((0.078, 0.0075, 0.052), 0.0028, 4), M["body"], parent=root, loc=(0.014, -FRONT + 0.0042, 0.003))
    glass = obj("screen glass", rbox((0.072, 0.0006, 0.046), 0.0012, 2), M["screen"], parent=lcd, loc=(0, 0.0038, 0))
    part(lcd, ex=(0.0, 0.29, 0.0), exd=0.18, exr=(0.25, 0, 0))
    wheel = obj("control wheel", ribbed(0.0062, 0.0105, 0.0004, 72, -0.0013, 0.0013), M["alu_dark"], parent=root,
                loc=(-0.049, -FRONT + 0.0013, -0.010), rot=(math.pi / 2, 0, 0))
    centre = obj("wheel button", lathe([(0, 0.0016), (0.0055, 0.0012), (0.0058, 0)], 64, closed=False), M["alu_dark"], parent=wheel,
                 loc=(0, 0, 0.0002))
    part(wheel, ex=(-0.01, 0.27, -0.01), exd=0.22, exr=(0, 0, 1.8))
    joy = obj("joystick", lathe([(0, 0.0034), (0.0024, 0.0033), (0.0027, 0.0026), (0.0016, 0.0016), (0.0018, 0)], 48, closed=False),
              M["rubber_plain"], parent=root, loc=(-0.047, -FRONT, 0.010), rot=(-math.pi / 2, 0, 0))
    part(joy, ex=(-0.01, 0.26, 0.01), exd=0.25)
    for i, (x, z) in enumerate(((-0.059, 0.012), (-0.036, -0.030), (-0.058, -0.030))):
        b = obj("button", lathe([(0, 0.0012), (0.0024, 0.001), (0.0026, 0)], 48, closed=False), M["alu_dark"], parent=root,
                loc=(x, -FRONT, z), rot=(-math.pi / 2, 0, 0))
        part(b, ex=(0, 0.25, 0), exd=0.26 + 0.02 * i)

    # strap lugs
    for sx in (-1, 1):
        lug = obj("strap lug", lathe([(0.0017, -0.0008), (0.0027, -0.0008), (0.0027, 0.0008), (0.0017, 0.0008)], 48), M["steel"],
                  parent=root, loc=(sx * (W / 2 + 0.0012 + (0.001 if sx < 0 else 0)), 0.008, 0.027), rot=(math.pi / 2, 0, 0))
        part(lug, ex=(sx * 0.05, 0.02, 0.03), exd=0.3, exr=(1.0, 0.5, 0))
    # bottom screws and the tripod insert
    for x, y in ((-0.05, -0.016), (0.05, -0.016), (-0.05, 0.016), (0.05, 0.016)):
        s = screw(M, parent=root, loc=(x, y, -H / 2), r=0.0013, down=True)
        part(s, ex=(x * 0.6, y * 1.5, -0.06), exd=0.0, exr=(0, 0, 6))
    tri = obj("tripod insert", ring(0.0028, 0.0045, -0.0006, 0.0, 64), M["screw"], parent=root, loc=(LX, 0.0, -H / 2))
    # side screws by the ports
    for z in (0.026, -0.03):
        s = screw(M, parent=root, loc=(W / 2, -0.012, z), r=0.0011, side=True)
        part(s, ex=(0.07, -0.01, z * 0.6), exd=0.02, exr=(0, 6, 0))
    return front, rear


def grip_mesh():
    """The grip, seen from above: flat against the body on the inside, a full rounded belly at the front, wrapping the
    corner. A smooth outline (Catmull-Rom through a few points), extruded, with soft top and bottom edges."""
    ctrl = [(-0.0312, 0.004), (-0.0312, -0.030), (-0.0330, -0.045), (-0.0405, -0.0545), (-0.0520, -0.0560),
            (-0.0610, -0.0510), (-0.0656, -0.0400), (-0.0658, -0.010), (-0.0656, 0.004)]
    pts = []
    n = len(ctrl)
    for i in range(n - 1):
        p0, p1, p2, p3 = (Vector(ctrl[max(i - 1, 0)]), Vector(ctrl[i]), Vector(ctrl[i + 1]), Vector(ctrl[min(i + 2, n - 1)]))
        for k in range(12):
            t = k / 12
            pts.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    pts.append(Vector(ctrl[-1]))
    hz = (H - 0.004) / 2
    bm = bmesh.new()
    vs = [bm.verts.new((p.x, p.y, -hz)) for p in pts]
    f = bm.faces.new(vs)
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, verts=[e for e in r["geom"] if isinstance(e, bmesh.types.BMVert)], vec=(0, 0, 2 * hz))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    caps = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-9 and e.verts[0].co.y < 0.0035 and e.verts[1].co.y < 0.0035]
    bmesh.ops.bevel(bm, geom=caps, offset=0.0065, segments=8, profile=0.5, affect="EDGES", clamp_overlap=True)
    return bm


def screw(M, parent, loc, r, down=False, side=False):
    """A small pan-head screw with a hex socket."""
    bm = lathe([(0, 0.0005 * r / 0.0011), (r * 0.82, 0.00045 * r / 0.0011), (r, 0.00012), (r, 0)], 40, closed=False)
    s = obj("screw", bm, M["screw"], parent=parent, loc=loc)
    sock = obj("socket", cyl(r * 0.42, 0.0006, 6), M["flock"], parent=s, loc=(0, 0, 0.0004 * r / 0.0011))
    if down:
        s.rotation_euler = (math.pi, 0, 0)
    if side:
        s.rotation_euler = (0, math.pi / 2, 0)
    return s


# ---------------------------------------------------------------- the lens
LENS = {}


def build_lens(M, root):
    """A fast prime: steel mount, black barrel with an aperture ring and a ribbed focus ring, six coated elements, 11-blade iris.
    Lens-local z runs forward from the mount face; the lens object is rotated so z points out of the camera (-Y)."""
    lens = empty("lens", parent=root, loc=on_axis(MOUNT_FACE))
    lens.rotation_euler = AXIS_ROT
    part(lens, ex=(0, -0.06, 0), exd=0.0)

    def piece(name, bm, m, z, ex, exd, exr=0.0, loc=None):
        ob = obj(name, bm, m, parent=lens, loc=loc or (0, 0, z))
        part(ob, ex=(0, 0, ex), exd=exd, exr=(0, 0, exr))      # lens-local: z offset is along the axis
        return ob

    # barrel sections (profiles are (r, z) about each piece's own origin); exploded, they spread out along the axis
    piece("lens mount", ring(0.0205, 0.0235, 0, 0.0035, 160, chamfer=0.0003), M["steel"], 0.0, 0.02, 0.05, 0.4)
    piece("rear barrel", lathe([(0.0300, 0.0), (0.0305, 0.0), (0.0315, 0.002), (0.0315, 0.014), (0.0300, 0.014)], 160), M["barrel"], 0.0035,
          0.05, 0.08)
    piece("aperture ring", ribbed(0.0300, 0.0335, 0.0005, 90, 0, 0.010, duty=0.35), M["barrel"], 0.019, 0.12, 0.12, 0.8)
    piece("mid barrel", ring(0.0300, 0.0322, 0.0, 0.004, 160, chamfer=0.0002), M["barrel"], 0.029, 0.15, 0.14)
    piece("focus ring", ribbed(0.0315, 0.0352, 0.0012, 54, 0, 0.026, duty=0.5), M["rubber_plain"], 0.033, 0.22, 0.18, -0.6)
    piece("front barrel", lathe([(0.0300, 0.0), (0.0350, 0.0), (0.0350, 0.018), (0.0342, 0.0215), (0.0318, 0.0222), (0.0312, 0.0205),
                                 (0.0300, 0.0195)], 192), M["barrel"], 0.061, 0.34, 0.2, 0.3)
    piece("orange index", rbox((0.0012, 0.0006, 0.004), 0.0002, 1), M["orange_ring"], 0.0, 0.05, 0.08, loc=(0.0, 0.0318, 0.010))
    # inner walls: a flocked tube with baffles, so the glass reads deep
    piece("lens tube", lathe([(0.0205, 0.0035), (0.0300, 0.0035), (0.0300, 0.080), (0.0292, 0.080), (0.0292, 0.0045), (0.0205, 0.0045)], 128),
          M["flock"], 0.0, 0.0, 0.0)
    for z, rin in ((0.0175, 0.0178), (0.038, 0.0192), (0.0558, 0.0228)):
        piece("baffle", ring(rin, 0.0292, 0.0, 0.0007, 96), M["flock"], z, 0.0, 0.0)

    # glass: (name, z of the rear vertex, radius, centre thickness, rear and front curvature radii), exploded z offset
    elements = [
        ("rear element", 0.0100, 0.0170, 0.0060, 0.050, 0.080, 0.05),
        ("element 5", 0.0200, 0.0185, 0.0060, 0.070, 0.150, 0.08),
        ("element 4", 0.0305, 0.0180, 0.0025, -0.060, -0.080, 0.105),
        ("element 3", 0.0470, 0.0215, 0.0075, 0.090, 0.070, 0.175),
        ("element 2", 0.0600, 0.0245, 0.0045, -0.120, 0.150, 0.21),
        ("front element", 0.0710, 0.0284, 0.0095, -0.200, 0.070, 0.27),
    ]
    for name, z, r, t, rr, rf, e in elements:
        LENS[name] = piece(name, lathe(lens_profile(r, t, rr, rf), 160, closed=False), M["glass"], z, e, 0.1)
    # the iris: eleven blades between element 4 and element 3, in a housing ring
    iris = empty("iris", parent=lens, loc=(0, 0, 0.0425))
    part(iris, ex=(0, 0, 0.14), exd=0.1)
    LENS["iris"] = iris
    LENS["blades"] = []
    for k in range(11):
        piv = empty("blade pivot", parent=iris)
        piv.rotation_euler = (0, 0, TAU * k / 11)
        LENS["blades"].append(obj("iris blade", blade_mesh(), M["blade"], parent=piv, loc=(0, 0, 0.00007 * k), smooth=0))
    obj("iris housing", ring(0.0232, 0.0292, -0.0004, 0.0012, 128), M["barrel"], parent=iris)
    set_iris(8.0)
    return lens


def lens_profile(r, t, rr, rf, n=28):
    """A lens element as a (radius, z) chain: from the axis along its rear face, up the rim, back along its front face.
    rr > 0: rear face bulges backward; rf > 0: front face bulges forward (negative = hollow). t = centre thickness."""
    def s(R, x):
        return 0.0 if not R else math.copysign(abs(R) - math.sqrt(max(R * R - x * x, 0.0)), R)
    t = max(t, s(rr, r) + s(rf, r) + 0.0012)          # keep the rim at least 1.2 mm thick
    rear = [(r * i / n, s(rr, r * i / n)) for i in range(n + 1)]
    front = [(r * i / n, t - s(rf, r * i / n)) for i in range(n, -1, -1)]
    return rear + front


def blade_mesh():
    """One iris blade in unit space: x across (-1..1), inner edge at y = 0 (slightly curved), outer edge at y = 1."""
    bm = bmesh.new()
    n = 16
    pts = [(-1 + 2 * i / n, 0.06 * (-1 + 2 * i / n) ** 2) for i in range(n + 1)]
    pts += [(1 - 2 * i / n, 1.0) for i in range(n + 1)]
    vs = [bm.verts.new((x, y, 0)) for x, y in pts]
    f = bm.faces.new(vs)
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, verts=[e for e in r["geom"] if isinstance(e, bmesh.types.BMVert)], vec=(0, 0, 1.0))
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


IRIS_HIDE = 0.0252                   # blades always reach this radius, inside the iris housing


def set_iris(fnum):
    """Set the iris: f/1.4 wide open (17.5 mm hole radius), smaller as the f-number grows (area ~ 1/N^2). Returns the radius."""
    a = max(0.0175 * min(1.0, 1.4 / fnum), 0.0012)
    for b in LENS["blades"]:
        b.scale = (0.0085, IRIS_HIDE - a, 0.00015)
        b.location = (0.0, a, b.location.z)
    return a


# ---------------------------------------------------------------- inside
def build_insides(M, root):
    sensor_y = MOUNT_FACE + 0.018
    pkg = obj("sensor package", rbox((0.047, 0.0028, 0.039), 0.0008, 2), M["ceramic"], parent=root, loc=(LX, sensor_y + 0.0014, LZ))
    frame = obj("sensor frame", rbox((0.042, 0.0006, 0.031), 0.0003, 1), M["gold"], parent=pkg, loc=(0, -0.0015, 0))
    die = obj("sensor die", rbox((0.0359, 0.0005, 0.0240), 0.0001, 1), M["die"], parent=pkg, loc=(0, -0.0019, 0))
    for i in range(36):                                                                  # bond wires along the long edges
        x = -0.0172 + i * 0.00098
        for zz in (0.0126, -0.0126):
            w = obj("bond", cyl(0.00004, 0.0016, 6), M["gold"], parent=pkg, loc=(x, -0.0018, zz + (0.0006 if zz > 0 else -0.0006)),
                    smooth=0)
    part(pkg, ex=(0, 0.07, 0), exd=0.12, exr=(0, 0, 0))
    cover = obj("sensor cover", rbox((0.040, 0.0009, 0.030), 0.0004, 2), M["glass_cover"], parent=root, loc=(LX, sensor_y - 0.0016, LZ))
    part(cover, ex=(0, 0.035, 0), exd=0.1)
    LENS["sensor"] = die

    ibis = obj("stabiliser plate", rbox((0.072, 0.0035, 0.056), 0.002, 3), M["alu_dark"], parent=root, loc=(LX, sensor_y + 0.0055, LZ))
    for x, z in ((-0.029, 0.021), (0.029, 0.021), (-0.029, -0.021), (0.029, -0.021)):
        coil = obj("coil", ring(0.0012, 0.0045, 0, 0.002, 48), M["copper"], parent=ibis, loc=(x, 0.0018, z), rot=(-math.pi / 2, 0, 0))
    part(ibis, ex=(0, 0.10, 0), exd=0.14)

    # the main board: processor under a steel lid, memory, the AI core (where the crew lives), hundreds of tiny parts
    by = 0.0075
    board = obj("main board", rbox((0.112, 0.0016, 0.064), 0.0012, 2), M["pcb"], parent=root, loc=(0.004, by, -0.002))
    part(board, ex=(0, 0.135, 0), exd=0.16)
    rnd = random.Random(7)
    ob_y = 0.0008
    obj("processor", rbox((0.017, 0.0022, 0.017), 0.0006, 2), M["lid"], parent=board, loc=(-0.012, ob_y + 0.0011, 0.004))
    core = obj("ai core", rbox((0.013, 0.0018, 0.013), 0.0004, 2), M["chip"], parent=board, loc=(0.020, ob_y + 0.0009, 0.006))
    obj("ai core glow", rbox((0.0085, 0.0003, 0.0085), 0.0002, 1), M["ai"], parent=core, loc=(0, 0.001, 0))
    LENS["core"] = core
    for x, z in ((-0.036, 0.016), (-0.036, -0.004)):
        obj("memory", rbox((0.012, 0.0012, 0.009), 0.0003, 1), M["chip"], parent=board, loc=(x, ob_y + 0.0006, z))
    for x, z, w, h in ((0.043, -0.02, 0.012, 0.004), (-0.002, -0.026, 0.018, 0.003)):
        obj("connector", rbox((w, 0.0025, h), 0.0003, 1), M["chip"], parent=board, loc=(x, ob_y + 0.00125, z))
    traces = []                                                                          # glowing traces out of the AI core
    for k in range(14):
        z0 = 0.006 + (k - 6.5) * 0.0008
        x1 = 0.0265 + rnd.uniform(0.004, 0.02)
        traces.append(obj("trace", rbox((x1 - 0.0265, 0.00008, 0.00025), 0, 1), M["ai_soft"], parent=board,
                          loc=((x1 + 0.0265) / 2, ob_y + 0.00004, z0), smooth=0))
        if k % 3 == 0:
            z1 = z0 + rnd.choice((-1, 1)) * rnd.uniform(0.006, 0.016)
            traces.append(obj("trace", rbox((0.00025, 0.00008, abs(z1 - z0)), 0, 1), M["ai_soft"], parent=board,
                              loc=(x1, ob_y + 0.00004, (z0 + z1) / 2), smooth=0))
    smd = bmesh.new()                                                                    # 300 small parts in one mesh
    for i in range(300):
        x, z = rnd.uniform(-0.054, 0.054), rnd.uniform(-0.030, 0.030)
        if abs(x + 0.012) < 0.011 and abs(z - 0.004) < 0.011 or abs(x - 0.02) < 0.009 and abs(z - 0.006) < 0.009:
            continue
        w, h = rnd.choice(((0.001, 0.0005), (0.0016, 0.0008), (0.002, 0.0012), (0.0006, 0.0003)))
        if rnd.random() < 0.5:
            w, h = h, w
        g = bmesh.ops.create_cube(smd, size=1.0)
        bmesh.ops.scale(smd, vec=(w, 0.0005, h), verts=g["verts"])
        bmesh.ops.translate(smd, vec=(x, ob_y + 0.00025, z), verts=g["verts"])
    obj("small parts", smd, M["ceramic"], parent=board, smooth=0)
    # flex cable from the sensor to the board
    flex = obj("flex cable", rbox((0.024, 0.0002, 0.012), 0, 1), M["flex"], parent=root, loc=(LX - 0.002, (sensor_y + by) / 2 + 0.002, -0.028),
               rot=(0.5, 0, 0), smooth=0)
    part(flex, ex=(0, 0.11, -0.01), exd=0.15)

    # cooling: copper heat pipe, aluminium fins, and a blower fan behind the vents
    fan = empty("fan", parent=root, loc=(0.050, 0.016, 0.012))
    housing = obj("fan housing", ring(0.0068, 0.0076, -0.0025, 0.0025, 96), M["alu_dark"], parent=fan, rot=(0, math.pi / 2, 0))
    rotor = empty("fan rotor", parent=fan)
    rotor.rotation_euler = (0, math.pi / 2, 0)
    obj("fan hub", cyl(0.0028, 0.004, 48), M["alu_dark"], parent=rotor)
    for k in range(23):
        a = TAU * k / 23
        obj("fan blade", rbox((0.0036, 0.0003, 0.0036), 0, 1), M["chip"], parent=rotor,
            loc=(0.0047 * math.cos(a), 0.0047 * math.sin(a), 0), rot=(0, 0, a + 0.5), smooth=0)
    LENS["rotor"] = rotor
    part(fan, ex=(0.11, 0.16, 0.02), exd=0.2, exr=(0.0, 0.0, 0.0))
    fins = bmesh.new()
    for k in range(16):
        g = bmesh.ops.create_cube(fins, size=1.0)
        bmesh.ops.scale(fins, vec=(0.0004, 0.014, 0.022), verts=g["verts"])
        bmesh.ops.translate(fins, vec=(0.026 + k * 0.001, 0.0, 0.0), verts=g["verts"])
    fo = obj("cooling fins", fins, M["alu"], parent=root, loc=(-0.002, 0.016, 0.013), smooth=0)
    part(fo, ex=(0.09, 0.175, 0.05), exd=0.2)
    pipe = obj("heat pipe", cyl(0.0016, 0.05, 32), M["copper"], parent=root, loc=(0.012, 0.012, 0.024), rot=(0, math.pi / 2, 0))
    part(pipe, ex=(0.05, 0.155, 0.06), exd=0.18)

    bat = obj("battery", rbox((0.022, 0.038, 0.056), 0.0025, 3), M["battery"], parent=root, loc=(-0.048, -0.026, -0.006))
    part(bat, ex=(-0.12, -0.02, -0.03), exd=0.2, exr=(0, 0, 0.3))
    return board


# ---------------------------------------------------------------- the crew
def build_agent(M, name, collection, parent=None):
    """A tiny orange worker, ~4 mm tall: a glossy orange shell, a black visor with a live histogram, two arms with
    grippers, an antenna, and a glowing thruster ring underneath (it hovers)."""
    root = empty(name, collection=collection, parent=parent)
    root.empty_display_size = 0.002
    s = 1.0
    body = obj(name + " body", sphere(1.0, 40, 20), M["agent_shell"], collection=collection, parent=root, smooth=0)
    body.scale = (0.00150, 0.00135, 0.00175)
    body.data.shade_smooth()
    # visor: a band of a slightly larger shell, front side only
    bm = sphere(1.0, 64, 32)
    kill = [f for f in bm.faces if not (0.02 < f.calc_center_median().z < 0.66 and f.calc_center_median().y < -0.12)]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    v = obj(name + " visor", bm, M["visor"], collection=collection, parent=root, smooth=0)
    v.scale = (0.00158, 0.00143, 0.00183)
    so = v.modifiers.new("thick", "SOLIDIFY")
    so.thickness = 0.04
    v.data.shade_smooth()
    # a graphite belt and two ear pods with a status light: it reads as a little machine, not an egg
    obj(name + " belt", ring(0.00128, 0.00156, -0.00042, -0.00012, 64, chamfer=0.00004), M["agent_dark"], collection=collection, parent=root,
        smooth=30)
    for sx in (-1, 1):
        ear = obj(name + " ear", lathe([(0, 0.00016), (0.00042, 0.00014), (0.0005, 0.0), (0.0005, -0.0002)], 32, closed=False), M["agent_dark"],
                  collection=collection, parent=root, loc=(sx * 0.00138, 0.0, 0.00045), rot=(0, sx * math.pi / 2, 0))
        obj(name + " ear light", cyl(0.00016, 0.00005, 20), M["agent_tip"], collection=collection, parent=ear, loc=(0, 0, 0.00017))
    # thruster ring and its glow
    tr = obj(name + " thruster", ring(0.0005, 0.0008, -0.00012, 0.00012, 48), M["agent_thrust"], collection=collection, parent=root,
             loc=(0, 0, -0.00168), smooth=0)
    obj(name + " skirt", ring(0.00075, 0.00105, -0.0002, 0.0002, 48, chamfer=0.00008), M["agent_dark"], collection=collection, parent=root,
        loc=(0, 0, -0.00150))
    # antenna
    obj(name + " antenna", cyl(0.00005, 0.0011, 12), M["agent_dark"], collection=collection, parent=root, loc=(0.0004, 0.0002, 0.0021),
        rot=(0, -0.2, 0))
    obj(name + " antenna tip", sphere(0.00014, 16, 8), M["agent_tip"], collection=collection, parent=root, loc=(0.00051, 0.0002, 0.00265))
    arms = []
    for sx in (-1, 1):
        sh = empty(name + " shoulder", collection=collection, parent=root, loc=(sx * 0.00142, -0.0002, -0.0001))
        sh.empty_display_size = 0.0005
        obj(name + " joint", sphere(0.00032, 20, 10), M["agent_dark"], collection=collection, parent=sh)
        up = obj(name + " arm", cyl(0.00012, 0.0011, 16), M["agent_shell"], collection=collection, parent=sh, loc=(sx * 0.0003, -0.0003, -0.00035),
                 rot=(0.8, sx * 0.5, 0))
        el = empty(name + " elbow", collection=collection, parent=sh, loc=(sx * 0.0005, -0.0007, -0.0007))
        el.empty_display_size = 0.0004
        obj(name + " elbow joint", sphere(0.00016, 16, 8), M["agent_dark"], collection=collection, parent=el)
        fa = obj(name + " forearm", cyl(0.0001, 0.0009, 16), M["agent_dark"], collection=collection, parent=el, loc=(0, -0.00045, 0),
                 rot=(math.pi / 2, 0, 0))
        for f in (-1, 1):
            obj(name + " finger", rbox((0.00007, 0.00045, 0.00009), 0.00002, 1), M["agent_shell"], collection=collection, parent=el,
                loc=(f * 0.00011, -0.0011, 0), rot=(0, 0, f * 0.25), smooth=0)
        obj(name + " tool", sphere(0.00006, 12, 6), M["agent_tip"], collection=collection, parent=el, loc=(0, -0.00125, 0))
        arms.append((sh, el))
    root["arms"] = [a[0].name for a in arms]
    return root


# ---------------------------------------------------------------- studio
def build_studio():
    sc = C.scene
    w = D.worlds.new("void")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.0006, 0.0006, 0.0007, 1)
    bg.inputs["Strength"].default_value = 1.0
    sc.world = w

    def area(name, size, loc, power, color=(1, 1, 1), shape="RECTANGLE", target=(0, 0, 0)):
        L = D.lights.new(name, "AREA")
        L.shape = shape
        L.size, L.size_y = size
        L.energy = power
        L.color = color
        o = D.objects.new(name, L)
        col("studio").objects.link(o)
        o.location = loc
        d = Vector(target) - Vector(loc)
        o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        o.visible_camera = False
        return o

    area("key softbox", (0.9, 0.6), (-0.55, -0.55, 0.65), 11, (1.0, 0.95, 0.9))
    area("top strip", (1.2, 0.06), (0.0, -0.05, 0.75), 6, (1.0, 1.0, 1.0))
    area("rim left", (0.05, 1.0), (-0.65, 0.55, 0.15), 13, (0.85, 0.92, 1.0))
    area("rim right", (0.05, 1.0), (0.65, 0.5, 0.2), 10, (0.85, 0.92, 1.0))
    area("floor bounce", (1.0, 1.0), (0.0, -0.3, -0.7), 1.0, (1.0, 0.98, 0.96))
    area("lens card", (1.2, 0.3), (0.0, -1.2, 0.6), 5, (1.0, 1.0, 1.0))      # a card the front glass and the front face mirror
    warm = D.lights.new("crew glow", "POINT")
    warm.energy, warm.color, warm.shadow_soft_size = 0.0, (1.0, 0.45, 0.12), 0.01
    wo = D.objects.new("crew glow", warm)
    col("studio").objects.link(wo)

    cam = D.cameras.new("film camera")
    cam.lens, cam.sensor_width = 85, 36
    cam.clip_start, cam.clip_end = 0.002, 50
    cam.dof.use_dof = True
    cam.dof.aperture_fstop = 4.0
    cam.dof.aperture_blades = 9
    co = D.objects.new("film camera", cam)
    col("studio").objects.link(co)
    sc.camera = co
    co.location = (0.35, -0.55, 0.18)
    co.rotation_euler = (Vector((0, 0, 0)) - co.location).to_track_quat("-Z", "Y").to_euler()
    cam.dof.focus_distance = (co.location).length

    sc.render.engine = "CYCLES"
    sc.cycles.device = "GPU"
    pr = C.preferences.addons["cycles"].preferences
    pr.compute_device_type = "METAL"
    pr.get_devices()
    for d in pr.devices:
        d.use = d.type == "METAL"
    sc.cycles.samples = 96
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 12
    sc.cycles.transmission_bounces = 16
    sc.cycles.glossy_bounces = 6
    sc.cycles.diffuse_bounces = 3
    sc.cycles.transparent_max_bounces = 16
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.blur_glossy = 0.5
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    sc.render.resolution_x, sc.render.resolution_y = 3840, 2160
    sc.render.fps = 24
    sc.view_settings.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            sc.view_settings.look = look
            break
        except TypeError:
            pass
    sc.view_settings.exposure = 0.0


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    M = build_materials()
    root = empty("camera rig")
    build_body(M, root)
    build_lens(M, root)
    build_insides(M, root)
    # the crew: one prototype for instancing (kept out of the render layer), heroes are built per shot
    build_agent(M, "agent", "crew proto")
    build_studio()
    bake([ob for ob in D.objects if ob.type == "MESH" and ob.modifiers])
    C.view_layer.layer_collection.children["crew proto"].exclude = True
    OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT), compress=True)
    print("parts:", len(PARTS), "objects:", len(D.objects), "->", OUT)


if __name__ == "__main__":
    main()
