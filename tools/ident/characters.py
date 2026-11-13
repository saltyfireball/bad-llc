"""Bad Omen ident characters: the raven (Director of Omens) and the cat.

SLRM-1922. Builds tools/ident/characters.blend from nothing, in code only
(no downloaded models, textures or HDRIs). Deterministic: the only
randomness is random.Random(1922).

Run from the worktree root:

    blender -b --factory-startup -P tools/ident/characters.py
    blender -b --factory-startup -P tools/ident/characters.py -- --review

--review also renders contact sheets (EEVEE) to tools/ident/out/characters/.
The saved .blend never contains the review camera, lights or set.

Units, axes, ground
-------------------
Metres. +Z up. Both characters face -X at rest (beak / nose toward -X);
their right side is +Y, left is -Y (.L bones sit at -Y). The floor is z = 0
at the root: feet and paws touch z = 0 when the root is at z = 0.
To walk toward +X in world, set root rotation_euler.z = pi
(rigs.key_raven_walk does this for you from start_xy -> end_xy).

Collections: "RAVEN" and "CAT". Append the collections (rigs.append_characters
does it); every object carries a custom property "bo_role" so helpers find
parts even after a rename on append.

RAVEN (collection RAVEN)
------------------------
RAVEN_ROOT   Empty at the ground point between the feet. Key its location
             and rotation_euler.z to move/turn the bird. Height to head top
             0.345 m (crown tufts 0.36 m), beak tip to tail tip 0.43 m.
             Custom properties:
               ["umbrella_open"]  0 = closed, 1 = open (0..1.2, a little
                                  over 1 reads as the pop). Drives the
                                  canopy shape key "Open".
RAVEN_RIG    Armature, child of RAVEN_ROOT. All control bones have their
             local axes equal to the raven's axes (X back, Y right, Z up),
             so pose location/rotation_euler (mode XYZ) read in those axes,
             about the bone's pivot:
               root        (0, 0, 0)            master offset, rarely needed
               body        (0.015, 0, 0.13)     hip pivot. loc z = bob,
                                                rot x = waddle, rot y = lean
               head        (-0.045, 0, 0.245)   neck base. rot z = head turn
                                                (+ toward raven's left),
                                                rot y = look up (+),
                                                loc x = head bob (- = thrust)
               tail        (0.085, 0, 0.12)     tail base. rot z = sideways
                                                flick (+ toward right),
                                                rot y = flick (- = up)
               wing.L/.R   (-0.03, -+0.055, 0.215) shoulders. Wings are
                                                folded tight at rest; small
                                                rot only (a shrug)
               foot_ik.L/.R (0, -+0.026, 0.014) ankle. IK targets: loc
                                                moves the foot (toes on the
                                                floor at loc z = 0), rot y
                                                curls the toes (- = down)
               umbrella    (-0.15, 0, 0.276)    the grip in the beak; the
                                                umbrella parts hang off it
             Non-keyed deform chain: thigh.L/.R -> tarsus.L/.R (IK, 2 bones).
Parts (rigidly bone-parented meshes, Subdivision Surface):
             RAVEN_body, RAVEN_wing.L/.R, RAVEN_badge(+_stripe, _clip,
             _text), RAVEN_lanyard (body), RAVEN_head, RAVEN_beak,
             RAVEN_eye.L/.R (+_lid, _iris, _pupil), RAVEN_hackles,
             RAVEN_tufts, RAVEN_bristles (head), RAVEN_tail (tail),
             RAVEN_thigh.L/.R, RAVEN_tarsus.L/.R, RAVEN_toes.L/.R.
Umbrella:    RAVEN_umbrella_canopy (shape key "Open", driven by
             RAVEN_ROOT["umbrella_open"]), RAVEN_umbrella_shaft,
             RAVEN_umbrella_handle (bone-coloured crook), all on bone
             "umbrella". Held in the beak, shaft up and a little back; open
             canopy is 0.24 m across, its rim ~0.41 m above the floor, top
             ~0.49 m. Visible by default (closed, carried like a cane);
             hide with rigs.key_umbrella_visible.
Materials:   BO_raven_feather (blue-black, coat + sheen + thin film),
             BO_raven_beak, BO_raven_leg, BO_bone, BO_red, BO_ink,
             BO_umbrella, BO_umbrella_lining.

CAT (collection CAT)
--------------------
CAT_ROOT     Empty at the ground under the body centre. 0.25 m at the
             shoulder, ~0.75 m nose to tail tip stretched. Faces -X.
             Custom property ["bound"]: 0 = gathered (legs under, back
             arched), 1 = stretched (front legs reaching, hind legs
             thrown back). Drives the shape key "Stretch" on CAT_body.
             Loop it 0-1-0 every ~6 frames (rigs.key_cat_bound).
CAT_body     One mesh: body, head, ears, legs, tail (BO_cat) and two small
             eyes (BO_cat_eye, faint manila glow; set its Emission
             Strength to 0 for a plain black cat). Paws touch z = 0 in the
             gathered pose; in the stretched pose they are 0-2 cm up (the
             helper also lifts the root a few cm then).
Use motion blur in the scene; the shape key and root motion both blur.
"""

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_BLEND = os.path.join(HERE, "characters.blend")
REVIEW_DIR = os.path.join(HERE, "out", "characters")
RNG = random.Random(1922)

Y = Vector((0.0, 1.0, 0.0))


# ====================================================================== util

def srgb(hexstr):
    """Hex sRGB -> linear RGBA tuple."""
    h = hexstr.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (out[0], out[1], out[2], 1.0)


def catmull(points, n):
    """Resample a polyline through `points` to n points (Catmull-Rom),
    parameterised by index so the count never depends on the shape."""
    pts = [Vector(p) for p in points]
    if len(pts) == 2:
        return [pts[0].lerp(pts[1], i / (n - 1)) for i in range(n)]
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    out = []
    segs = len(pts) - 1
    for i in range(n):
        t = i / (n - 1) * segs
        k = min(int(t), segs - 1)
        u = t - k
        p0, p1, p2, p3 = ext[k], ext[k + 1], ext[k + 2], ext[k + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * u
                          + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * u * u * u))
    return out


def lerp_list(vals, n):
    """Resample a list of tuples to n entries, linear by index."""
    out = []
    segs = len(vals) - 1
    for i in range(n):
        t = i / (n - 1) * segs
        k = min(int(t), segs - 1)
        u = t - k
        a, b = vals[k], vals[k + 1]
        out.append(tuple(x + (y - x) * u for x, y in zip(a, b)))
    return out


def loft(spine, radii, n=None, ring=16, cap0=0.0, cap1=0.0, side=Y, twist=0.0):
    """Tube through `spine` with elliptical sections.

    radii: per control point (rs, rn_up, rn_down): half width along `side`,
    half height on the "up" side of the spine and on the "down" side.
    cap0/cap1: length of the end cap point beyond the first/last section
    (0 gives a flat-ish cap at the section centre).
    Returns (verts, faces); fixed topology for a given n and ring.
    """
    n = n or max(len(spine), 2)
    pts = catmull(spine, n) if len(spine) != n else [Vector(p) for p in spine]
    rad = lerp_list([tuple(r) for r in radii], n)
    verts, faces = [], []
    tangents = []
    for i in range(n):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, n - 1)]
        tangents.append((b - a).normalized())
    for i in range(n):
        t = tangents[i]
        s = (side - t * side.dot(t))
        if s.length < 1e-6:
            s = Vector((1, 0, 0)) - t * t.x
        s.normalize()
        up = s.cross(t)
        if up.z < -1e-6:
            up = -up
        if abs(up.z) <= 1e-6 and up.x > 0:
            up = -up
        rs, ru, rd = rad[i]
        for j in range(ring):
            a = 2 * math.pi * j / ring + twist
            c, si = math.cos(a), math.sin(a)
            rn = ru if si > 0 else rd
            verts.append(pts[i] + s * (rs * c) + up * (rn * si))
    for i in range(n - 1):
        for j in range(ring):
            a = i * ring + j
            b = i * ring + (j + 1) % ring
            faces.append((a, b, b + ring, a + ring))
    # caps
    c0 = len(verts)
    verts.append(pts[0] - tangents[0] * cap0)
    for j in range(ring):
        faces.append((c0, (j + 1) % ring, j))
    c1 = len(verts)
    verts.append(pts[-1] + tangents[-1] * cap1)
    base = (n - 1) * ring
    for j in range(ring):
        faces.append((c1, base + j, base + (j + 1) % ring))
    return verts, faces


def ellipsoid(center, radii, rot=None, seg=16, rings=10):
    """UV ellipsoid as (verts, faces)."""
    rot = rot or Matrix.Identity(3)
    verts, faces = [], []
    verts.append(Vector(center) + rot @ Vector((0, 0, radii[2])))
    for r in range(1, rings):
        th = math.pi * r / rings
        for s in range(seg):
            ph = 2 * math.pi * s / seg
            v = Vector((math.sin(th) * math.cos(ph) * radii[0],
                        math.sin(th) * math.sin(ph) * radii[1],
                        math.cos(th) * radii[2]))
            verts.append(Vector(center) + rot @ v)
    verts.append(Vector(center) + rot @ Vector((0, 0, -radii[2])))
    last = len(verts) - 1
    for s in range(seg):
        faces.append((0, 1 + s, 1 + (s + 1) % seg))
    for r in range(rings - 2):
        for s in range(seg):
            a = 1 + r * seg + s
            b = 1 + r * seg + (s + 1) % seg
            faces.append((a, a + seg, b + seg, b))
    base = 1 + (rings - 2) * seg
    for s in range(seg):
        faces.append((last, base + (s + 1) % seg, base + s))
    return verts, faces


def box(center, size, rot=None):
    rot = rot or Matrix.Identity(3)
    hx, hy, hz = [v / 2 for v in size]
    vs = [Vector(center) + rot @ Vector((x, y, z))
          for x in (-hx, hx) for y in (-hy, hy) for z in (-hz, hz)]
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return vs, fs


class Geo:
    """Accumulates parts (verts, faces, material index) into one mesh."""

    def __init__(self):
        self.verts, self.faces, self.mats = [], [], []

    def add(self, part, mat=0):
        vs, fs = part
        off = len(self.verts)
        self.verts.extend(Vector(v) for v in vs)
        self.faces.extend(tuple(i + off for i in f) for f in fs)
        self.mats.extend([mat] * len(fs))
        return self


def make_mesh(name, geo, materials, coll, subsurf=2, smooth=True, recalc=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in geo.verts], [], geo.faces)
    me.update()
    if recalc:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
    for m in materials:
        me.materials.append(m)
    for p, mi in zip(me.polygons, geo.mats):
        p.material_index = mi
        p.use_smooth = smooth
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if subsurf:
        mod = ob.modifiers.new("Subdivision", "SUBSURF")
        mod.levels = 1
        mod.render_levels = subsurf
    return ob


def single(part, mat=0):
    return Geo().add(part, mat)


# ================================================================= materials

def _principled(mat):
    nt = mat.node_tree
    if nt is None:
        mat.use_nodes = True
        nt = mat.node_tree
    return nt, nt.nodes.get("Principled BSDF")


def material(name, color, rough=0.5, metal=0.0, coat=0.0, coat_rough=0.1,
             sheen=0.0, sheen_tint=(1, 1, 1, 1), sheen_rough=0.5, film=0.0,
             spec_tint=None, emission=None, emission_strength=0.0):
    m = bpy.data.materials.new(name)
    nt, p = _principled(m)
    p.inputs["Base Color"].default_value = color
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    p.inputs["Coat Weight"].default_value = coat
    p.inputs["Coat Roughness"].default_value = coat_rough
    p.inputs["Sheen Weight"].default_value = sheen
    p.inputs["Sheen Tint"].default_value = sheen_tint
    p.inputs["Sheen Roughness"].default_value = sheen_rough
    if film:
        p.inputs["Thin Film Thickness"].default_value = film
        p.inputs["Thin Film IOR"].default_value = 1.45
    if spec_tint:
        p.inputs["Specular Tint"].default_value = spec_tint
    if emission:
        p.inputs["Emission Color"].default_value = emission
        p.inputs["Emission Strength"].default_value = emission_strength
    m.diffuse_color = color
    return m


def feather_material():
    """Glossy blue-black with a faint feather-barb bump (procedural)."""
    m = material("BO_raven_feather", (0.010, 0.011, 0.016, 1.0), rough=0.34,
                 coat=0.55, coat_rough=0.18, sheen=0.7,
                 sheen_tint=(0.42, 0.50, 0.85, 1.0), sheen_rough=0.35,
                 film=420.0, spec_tint=(0.55, 0.62, 0.9, 1.0))
    nt, p = _principled(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (90.0, 260.0, 90.0)
    wave = nt.nodes.new("ShaderNodeTexNoise")
    wave.inputs["Scale"].default_value = 1.0
    wave.inputs["Detail"].default_value = 3.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    bump.inputs["Distance"].default_value = 0.001
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], wave.inputs["Vector"])
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Coat Normal"])
    return m


def build_materials():
    M = {}
    M["feather"] = feather_material()
    M["beak"] = material("BO_raven_beak", srgb("#2c2c31"), rough=0.22, coat=0.6,
                         coat_rough=0.08, spec_tint=(0.7, 0.75, 0.9, 1.0))
    M["leg"] = material("BO_raven_leg", srgb("#3a3833"), rough=0.4, coat=0.3)
    M["bone"] = material("BO_bone", srgb("#e8e2d6"), rough=0.45)
    M["red"] = material("BO_red", srgb("#b3261e"), rough=0.35, coat=0.3)
    M["ink"] = material("BO_ink", srgb("#0b0b0c"), rough=0.08, coat=1.0, coat_rough=0.02)
    M["ash"] = material("BO_ash", srgb("#6b6760"), rough=0.3, metal=0.6)
    M["umbrella"] = material("BO_umbrella", (0.008, 0.008, 0.010, 1.0), rough=0.38,
                             coat=0.35, coat_rough=0.25, sheen=0.15,
                             sheen_tint=(0.55, 0.58, 0.7, 1.0))
    M["lining"] = material("BO_umbrella_lining", (0.09, 0.012, 0.010, 1.0), rough=0.6)
    M["shaft"] = material("BO_umbrella_shaft", (0.02, 0.02, 0.022, 1.0), rough=0.25, metal=0.8)
    M["cat"] = material("BO_cat", (0.006, 0.006, 0.007, 1.0), rough=0.55,
                        sheen=0.8, sheen_tint=(0.5, 0.5, 0.55, 1.0), sheen_rough=0.3)
    M["cat_eye"] = material("BO_cat_eye", srgb("#cbb88c"), rough=0.1,
                            emission=srgb("#cbb88c"), emission_strength=0.6)
    return M


# ===================================================================== rig

def add_bone(eb, name, head, parent=None, length=0.03, tail=None, connect=False):
    b = eb.new(name)
    b.head = Vector(head)
    b.tail = Vector(tail) if tail is not None else Vector(head) + Vector((0, length, 0))
    b.roll = 0.0
    if parent:
        b.parent = eb[parent]
        b.use_connect = connect
    return b


def bone_parent(ob, arm, bone_name):
    """Rigidly parent ob (modelled in rest world space) to a bone."""
    ob.parent = arm
    ob.parent_type = "BONE"
    ob.parent_bone = bone_name
    b = arm.data.bones[bone_name]
    ob.matrix_parent_inverse = (arm.matrix_world @ b.matrix_local
                                @ Matrix.Translation((0, b.length, 0))).inverted()


def tag(ob, role):
    ob["bo_role"] = role
    return ob


# =================================================================== raven

RAVEN_BONES = {
    "root": (0.0, 0.0, 0.0),
    "body": (0.015, 0.0, 0.13),
    "head": (-0.045, 0.0, 0.245),
    "tail": (0.085, 0.0, 0.12),
    "wing.L": (-0.03, -0.055, 0.215),
    "wing.R": (-0.03, 0.055, 0.215),
    "foot_ik.L": (0.0, -0.026, 0.014),
    "foot_ik.R": (0.0, 0.026, 0.014),
    "umbrella": (-0.150, 0.0, 0.276),
}

HEAD_C = Vector((-0.064, 0.0, 0.293))


def raven_body():
    spine = [(-0.050, 0, 0.268), (-0.054, 0, 0.228), (-0.036, 0, 0.183),
             (0.004, 0, 0.148), (0.050, 0, 0.128), (0.092, 0, 0.118)]
    # (half width, half height on the back side, on the chest side)
    radii = [(0.036, 0.034, 0.036), (0.054, 0.048, 0.060), (0.064, 0.056, 0.070),
             (0.062, 0.056, 0.064), (0.046, 0.040, 0.044), (0.022, 0.018, 0.020)]
    return loft(spine, radii, n=12, ring=20, cap0=0.02, cap1=0.012)


def raven_head():
    c = HEAD_C
    spine = [c + Vector((0.048, 0, 0.004)), c + Vector((0.018, 0, 0.002)),
             c + Vector((-0.012, 0, 0.0)), c + Vector((-0.040, 0, -0.006))]
    radii = [(0.030, 0.030, 0.034), (0.050, 0.050, 0.050), (0.050, 0.050, 0.048),
             (0.032, 0.030, 0.030)]
    return loft(spine, radii, n=9, ring=20, cap0=0.014, cap1=0.008)


def raven_beak():
    spine = [(-0.096, 0, 0.285), (-0.130, 0, 0.283), (-0.163, 0, 0.276),
             (-0.190, 0, 0.263), (-0.206, 0, 0.249)]
    radii = [(0.021, 0.024, 0.021), (0.017, 0.020, 0.015), (0.012, 0.014, 0.010),
             (0.007, 0.008, 0.006), (0.003, 0.003, 0.002)]
    return loft(spine, radii, n=10, ring=16, cap0=0.0, cap1=0.008)


def cone(base, tip, r0, r1=0.0, ring=8, flat=1.0):
    """Feather-ish spike: base -> tip, round base radius r0."""
    base, tip = Vector(base), Vector(tip)
    mid = base.lerp(tip, 0.5)
    return loft([base, mid, tip], [(r0, r0 * flat, r0 * flat),
                                   (r0 * 0.7, r0 * 0.7 * flat, r0 * 0.7 * flat),
                                   (max(r1, r0 * 0.12),) * 3],
                n=3, ring=ring, cap0=0.0, cap1=0.004)


def raven_hackles():
    g = Geo()
    for i in range(11):
        y = -0.026 + 0.052 * i / 10.0 + RNG.uniform(-0.002, 0.002)
        x = -0.080 + RNG.uniform(-0.004, 0.006) + abs(y) * 0.5
        z = 0.258 + RNG.uniform(-0.004, 0.004) + abs(y) * 0.2
        L = 0.026 + RNG.uniform(0.0, 0.008) - abs(y) * 0.3
        tip = Vector((x + 0.004 + RNG.uniform(-0.003, 0.003), y * 1.15, z - L))
        g.add(cone((x, y, z + 0.008), tip, 0.011, flat=0.5))
    return g


def raven_tufts():
    g = Geo()
    for (dx, dy, h) in ((-0.008, 0.0, 0.024), (0.010, -0.010, 0.018), (0.010, 0.010, 0.018),
                        (0.026, 0.0, 0.014)):
        b = HEAD_C + Vector((dx, dy, 0.040))
        g.add(cone(b, b + Vector((0.012, dy * 0.6, h)), 0.008))
    return g


def raven_bristles():
    g = Geo()
    for dy in (-0.010, 0.0, 0.010):
        b = Vector((-0.090, dy, 0.300))
        g.add(cone(b, Vector((-0.122, dy * 1.2, 0.292)), 0.007, flat=0.6))
    return g


def raven_wing(sgn):
    g = Geo()
    spine = [(-0.040, sgn * 0.046, 0.222), (0.004, sgn * 0.064, 0.188),
             (0.052, sgn * 0.060, 0.146), (0.100, sgn * 0.046, 0.115),
             (0.150, sgn * 0.030, 0.096)]
    radii = [(0.014, 0.030, 0.030), (0.016, 0.046, 0.046), (0.014, 0.042, 0.038),
             (0.009, 0.028, 0.022), (0.004, 0.012, 0.008)]
    g.add(loft(spine, radii, n=12, ring=16, cap0=0.012, cap1=0.022))
    # primaries: a fan of blades past the rump, the jagged edge in the svg
    for k, (dz, L) in enumerate(((0.000, 0.090), (-0.016, 0.075), (-0.032, 0.058))):
        b = Vector((0.085, sgn * (0.050 - 0.004 * k), 0.122 + dz * 0.4))
        d = Vector((1.0, -sgn * 0.18, -0.55 + dz * 9.0)).normalized()
        tip = b + d * L
        g.add(loft([b, b.lerp(tip, 0.5), tip],
                   [(0.004, 0.010, 0.010), (0.004, 0.011, 0.010), (0.002, 0.004, 0.004)],
                   n=5, ring=10, cap0=0.004, cap1=0.012))
    return g


def raven_tail():
    g = Geo()
    base = Vector(RAVEN_BONES["tail"]) + Vector((-0.012, 0, 0.004))
    # wedge: centre feathers longest; the fan opens sideways and a little
    # vertically so it still reads as a wedge in side view.
    for k in range(-2, 3):
        yaw = math.radians(11.0 * k)
        pitch = math.radians(-24.0 + 4.0 * abs(k))
        L = 0.135 - 0.018 * abs(k)
        d = Vector((math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw),
                    math.sin(pitch)))
        b = base + Vector((0, 0.006 * k, 0.003 * abs(k)))
        tip = b + d * L
        g.add(loft([b, b + d * (0.35 * L), b + d * (0.8 * L), tip],
                   [(0.012, 0.006, 0.006), (0.017, 0.005, 0.005), (0.017, 0.004, 0.004),
                    (0.006, 0.002, 0.002)],
                   n=7, ring=12, cap0=0.004, cap1=0.014))
    # tail coverts: a short thick wedge on top that blends into the rump
    tip = base + Vector((0.07, 0, -0.022))
    g.add(loft([base, base.lerp(tip, 0.5), tip],
               [(0.028, 0.012, 0.012), (0.026, 0.010, 0.010), (0.012, 0.004, 0.004)],
               n=5, ring=14, cap0=0.004, cap1=0.012))
    return g


def raven_leg_parts(sgn):
    hip = Vector((0.015, sgn * 0.024, 0.122))
    heel = Vector((0.034, sgn * 0.026, 0.060))
    ankle = Vector((0.0, sgn * 0.026, 0.014))
    thigh = single(loft([hip, hip.lerp(heel, 0.5), heel + Vector((0, 0, 0.006))],
                        [(0.022, 0.022, 0.022), (0.019, 0.019, 0.019), (0.010, 0.010, 0.010)],
                        n=5, ring=12, cap0=0.01, cap1=0.004))
    tarsus = single(loft([heel + Vector((0, 0, 0.008)), heel.lerp(ankle, 0.5), ankle],
                         [(0.0055, 0.0055, 0.0055), (0.0045, 0.0045, 0.0045),
                          (0.0048, 0.0048, 0.0048)], n=4, ring=10, cap0=0.003, cap1=0.003))
    toes = Geo()
    for ang in (-24.0, 0.0, 24.0):
        a = math.radians(ang)
        d = Vector((-math.cos(a), math.sin(a) * sgn, 0.0))
        L = 0.040 if ang == 0 else 0.032
        p0 = ankle + Vector((0, 0, -0.004))
        p1 = Vector((ankle.x, ankle.y, 0.0045)) + d * (L * 0.45)
        p2 = Vector((ankle.x, ankle.y, 0.0030)) + d * L
        toes.add(loft([p0, p1, p2], [(0.0042, 0.0042, 0.0042), (0.0036, 0.0036, 0.0036),
                                     (0.0022, 0.0022, 0.0022)],
                      n=5, ring=8, cap0=0.002, cap1=0.006))
    p0 = ankle + Vector((0, 0, -0.004))
    toes.add(loft([p0, Vector((0.014, ankle.y, 0.004)), Vector((0.026, ankle.y, 0.003))],
                  [(0.0040,) * 3, (0.0034,) * 3, (0.0020,) * 3], n=5, ring=8,
                  cap0=0.002, cap1=0.006))
    return thigh, tarsus, toes, hip, heel, ankle


def ray_to(obj, origin, direction):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    inv = ev.matrix_world.inverted()
    ok, loc, nor, _ = ev.ray_cast(inv @ Vector(origin), (inv.to_3x3() @ Vector(direction)).normalized())
    if not ok:
        raise RuntimeError("ray missed " + obj.name)
    n = (ev.matrix_world.to_3x3() @ nor).normalized()
    if n.dot(Vector(direction)) > 0:
        n = -n
    return ev.matrix_world @ loc, n


def frame_from_normal(nor, up_hint=Vector((0, 0, 1))):
    """3x3 with local Z = nor, local X roughly horizontal."""
    z = Vector(nor).normalized()
    x = up_hint.cross(z)
    if x.length < 1e-6:
        x = Vector((1, 0, 0))
    x.normalize()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed()


def hemisphere(center, r, rot, seg=20, rings=6, cut=0.0):
    """Upper dome (local z >= cut*r) of a sphere; open bottom."""
    verts, faces = [Vector(center) + rot @ Vector((0, 0, r))], []
    th_max = math.acos(max(-1.0, min(1.0, cut)))
    for k in range(1, rings + 1):
        th = th_max * k / rings
        for s in range(seg):
            ph = 2 * math.pi * s / seg
            verts.append(Vector(center) + rot @ Vector((math.sin(th) * math.cos(ph) * r,
                                                        math.sin(th) * math.sin(ph) * r,
                                                        math.cos(th) * r)))
    for s in range(seg):
        faces.append((0, 1 + s, 1 + (s + 1) % seg))
    for k in range(rings - 1):
        for s in range(seg):
            a = 1 + k * seg + s
            b = 1 + k * seg + (s + 1) % seg
            faces.append((a, a + seg, b + seg, b))
    return verts, faces


def build_raven(M):
    coll = bpy.data.collections.new("RAVEN")
    bpy.context.scene.collection.children.link(coll)

    root = bpy.data.objects.new("RAVEN_ROOT", None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.1
    coll.objects.link(root)
    tag(root, "raven_root")
    root["umbrella_open"] = 0.0
    root.id_properties_ui("umbrella_open").update(
        min=0.0, max=1.2, soft_min=0.0, soft_max=1.0,
        description="0 closed, 1 open (drives the canopy shape key Open)")

    # ---- armature
    ad = bpy.data.armatures.new("RAVEN_RIG")
    arm = bpy.data.objects.new("RAVEN_RIG", ad)
    coll.objects.link(arm)
    arm.parent = root
    tag(arm, "raven_rig")
    ad.display_type = "STICK"
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = ad.edit_bones
    B = RAVEN_BONES
    add_bone(eb, "root", B["root"], length=0.06)
    add_bone(eb, "body", B["body"], "root")
    add_bone(eb, "head", B["head"], "body")
    add_bone(eb, "umbrella", B["umbrella"], "head", length=0.02)
    add_bone(eb, "tail", B["tail"], "body")
    for side, sgn in (("L", -1), ("R", 1)):
        add_bone(eb, "wing." + side, B["wing." + side], "body", length=0.02)
        add_bone(eb, "foot_ik." + side, B["foot_ik." + side], "root", length=0.02)
        hip = (0.015, sgn * 0.024, 0.122)
        heel = (0.034, sgn * 0.026, 0.060)
        ankle = B["foot_ik." + side]
        th = add_bone(eb, "thigh." + side, hip, "body", tail=heel)
        th.use_deform = False
        ta = add_bone(eb, "tarsus." + side, heel, "thigh." + side, tail=ankle, connect=True)
        ta.use_deform = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
    for side in ("L", "R"):
        c = arm.pose.bones["tarsus." + side].constraints.new("IK")
        c.target = arm
        c.subtarget = "foot_ik." + side
        c.chain_count = 2
        c.use_rotation = False

    def part(name, geo, mats, bone, role=None, subsurf=2):
        ob = make_mesh(name, geo, mats, coll, subsurf=subsurf)
        bone_parent(ob, arm, bone)
        tag(ob, role or ("raven_" + name.split("_", 1)[1]))
        return ob

    F = M["feather"]
    body = part("RAVEN_body", single(raven_body()), [F], "body")
    head = part("RAVEN_head", single(raven_head()), [F], "head")
    part("RAVEN_beak", single(raven_beak()), [M["beak"]], "head")
    part("RAVEN_hackles", raven_hackles(), [F], "head")
    part("RAVEN_tufts", raven_tufts(), [F], "head")
    part("RAVEN_bristles", raven_bristles(), [F], "head")
    part("RAVEN_tail", raven_tail(), [F], "tail")
    for side, sgn in (("L", -1), ("R", 1)):
        part("RAVEN_wing." + side, raven_wing(sgn), [F], "wing." + side)
        thigh, tarsus, toes, hip, heel, ankle = raven_leg_parts(sgn)
        part("RAVEN_thigh." + side, thigh, [F], "thigh." + side)
        part("RAVEN_tarsus." + side, tarsus, [M["leg"]], "tarsus." + side)
        part("RAVEN_toes." + side, toes, [M["leg"]], "foot_ik." + side)

    # ---- eyes: bone sclera, heavy flat lid (deadpan), red iris, ink pupil
    bpy.context.view_layer.update()
    for side, sgn in (("L", -1), ("R", 1)):
        az = math.radians(58.0)
        d = Vector((-math.cos(az), sgn * math.sin(az), 0.16)).normalized()
        hit, nor = ray_to(head, HEAD_C + d * 0.2, -d)
        r = 0.0140
        c = hit - nor * 0.0045
        rot = frame_from_normal(nor)
        sclera = single(ellipsoid(c, (r, r, r), seg=20, rings=12))
        part("RAVEN_eye." + side, sclera, [M["bone"]], "head", subsurf=1)
        # lid: dome over the top, its edge tilted down toward the beak
        lid_rot = (Matrix.Rotation(math.radians(-8.0 * -sgn), 3, d) @
                   frame_from_normal(Vector((0, 0, 1)).lerp(nor, 0.18)))
        lid = single(hemisphere(c, r * 1.10, lid_rot, cut=-0.08))
        part("RAVEN_eye." + side + "_lid", lid, [F], "head", subsurf=1)
        # iris looks forward-ish: offset from the eye normal toward -X
        look = (nor + Vector((-0.75, 0, -0.25))).normalized()
        ic = c + look * (r * 0.80)
        irot = frame_from_normal(look)
        iris = single(ellipsoid(ic, (0.0074, 0.0074, 0.0028), rot=irot, seg=16, rings=8))
        part("RAVEN_eye." + side + "_iris", iris, [M["red"]], "head", subsurf=1)
        pc = c + look * (r * 0.92)
        pupil = single(ellipsoid(pc, (0.0042, 0.0042, 0.0022), rot=irot, seg=12, rings=6))
        part("RAVEN_eye." + side + "_pupil", pupil, [M["ink"]], "head", subsurf=1)

    # ---- badge on the chest, tilted like the svg (-7 deg), red lanyard
    hit, nor = ray_to(body, Vector((-0.4, 0.0, 0.170)), Vector((1, 0, 0)))
    brot = Matrix.Rotation(math.radians(-7.0), 3, nor) @ frame_from_normal(nor)
    bc = hit + nor * 0.0065
    W, H = 0.040, 0.027
    ax, ay = brot.col[0], brot.col[1]  # ax across, ay up the card

    def on_card(u, v, w=0.0):
        return bc + ax * u + ay * v + nor * w

    badge = part("RAVEN_badge", single(box(bc, (W, H, 0.0028), rot=brot)), [M["bone"]], "body",
                 subsurf=0)
    bev = badge.modifiers.new("Bevel", "BEVEL")
    bev.width = 0.0008
    bev.segments = 2
    part("RAVEN_badge_stripe", single(box(on_card(0, H * 0.40, 0.0012), (W * 1.005, H * 0.2, 0.0012),
                                          rot=brot)), [M["red"]], "body", subsurf=0)
    part("RAVEN_badge_clip", single(box(on_card(0, H * 0.52, 0.0008), (0.006, 0.004, 0.003),
                                        rot=brot)), [M["ash"]], "body", subsurf=0)
    txt = Geo()
    for v, w in ((0.10, 0.75), (-0.10, 0.62), (-0.28, 0.48)):
        txt.add(box(on_card(-W * (0.5 - w / 2) * 0.88, H * v, 0.0016), (W * w * 0.85, 0.0018, 0.0006),
                    rot=brot))
    part("RAVEN_badge_text", txt, [M["ink"]], "body", subsurf=0)
    # lanyard: from both top corners up round the back of the neck
    left, right = on_card(-W * 0.32, H * 0.5), on_card(W * 0.32, H * 0.5)
    path = [right, Vector((-0.084, 0.030, 0.222)), Vector((-0.060, 0.047, 0.240)),
            Vector((-0.030, 0.042, 0.250)), Vector((-0.010, 0.0, 0.254)),
            Vector((-0.030, -0.042, 0.250)), Vector((-0.060, -0.047, 0.240)),
            Vector((-0.084, -0.030, 0.222)), left]
    lan = single(loft(path, [(0.0016,) * 3] * len(path), n=40, ring=6))
    part("RAVEN_lanyard", lan, [M["red"]], "body", subsurf=0)

    build_umbrella(M, coll, arm, root)
    return root


def build_umbrella(M, coll, arm, root):
    grip = Vector(RAVEN_BONES["umbrella"])
    axis = Vector((0.07, 0.0, 0.225)).normalized()
    top = grip + axis * 0.215
    rot = frame_from_normal(axis, up_hint=Vector((0, 1, 0)))  # local Z = shaft

    # canopy: 8 ribs, scalloped edge; basis = closed, shape key Open
    ribs, per, rings = 8, 6, 12
    seg = ribs * per
    L = 0.155

    def canopy(open_):
        vs = [Vector((0, 0, 0))]
        th_max = 1.12
        R = L / th_max
        for k in range(1, rings + 1):
            r = k / rings
            for s in range(seg):
                a = 2 * math.pi * s / seg
                pleat = abs(math.sin(ribs * a / 2.0))  # 0 on ribs, 1 between
                if open_:
                    rr = r * (1.0 - 0.11 * pleat * r ** 2)
                    th = th_max * rr
                    rad = R * math.sin(th)
                    z = -R * (1 - math.cos(th)) - 0.004 * pleat * r
                    vs.append(Vector((rad * math.cos(a), rad * math.sin(a), z)))
                else:
                    rad = (0.0045 + 0.017 * math.sin(math.pi * min(1.0, r ** 0.8) * 0.85)) * \
                          (0.72 + 0.55 * pleat)
                    z = -L * 0.96 * r
                    vs.append(Vector((rad * math.cos(a), rad * math.sin(a), z)))
        return [top + rot @ v for v in vs]

    fs = [(0, 1 + (s + 1) % seg, 1 + s) for s in range(seg)]
    for k in range(rings - 1):
        for s in range(seg):
            a = 1 + k * seg + s
            b = 1 + k * seg + (s + 1) % seg
            fs.append((a, b, b + seg, a + seg))
    g = Geo()
    g.add((canopy(False), fs))
    can = make_mesh("RAVEN_umbrella_canopy", g, [M["lining"], M["umbrella"]], coll, subsurf=0,
                    recalc=False)
    sol = can.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.0018
    sol.offset = -1.0
    sol.material_offset = 1  # shell (outside) = index 1 = BO_umbrella
    sol.material_offset_rim = 0
    sub = can.modifiers.new("Subdivision", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 1
    can.shape_key_add(name="Basis", from_mix=False)
    sk = can.shape_key_add(name="Open", from_mix=False)
    sk.slider_max = 1.2
    for i, v in enumerate(canopy(True)):
        sk.data[i].co = v
    fc = sk.driver_add("value")
    drv = fc.driver
    drv.type = "AVERAGE"
    var = drv.variables.new()
    var.name = "open"
    var.type = "SINGLE_PROP"
    var.targets[0].id_type = "OBJECT"
    var.targets[0].id = root
    var.targets[0].data_path = '["umbrella_open"]'
    bone_parent(can, arm, "umbrella")
    tag(can, "umbrella_canopy")

    # shaft with a ferrule spike on top
    bottom = grip - axis * 0.028
    shaft = Geo()
    shaft.add(loft([bottom, grip, top, top + axis * 0.022],
                   [(0.0032,) * 3, (0.0032,) * 3, (0.0030,) * 3, (0.0012,) * 3],
                   n=4, ring=8, cap0=0.0, cap1=0.006))
    # runner/notch: small collar under the canopy
    shaft.add(loft([top - axis * 0.05, top - axis * 0.042], [(0.0055,) * 3, (0.0055,) * 3],
                   n=2, ring=10))
    ob = make_mesh("RAVEN_umbrella_shaft", shaft, [M["shaft"]], coll, subsurf=1)
    bone_parent(ob, arm, "umbrella")
    tag(ob, "umbrella_shaft")

    # crook handle (bone): J curving forward (-X) below the beak
    fwd = Vector((-1, 0, 0))
    pts = []
    rh = 0.013
    c = bottom + fwd * rh
    for k in range(9):
        a = math.pi * k / 8.0
        pts.append(c - fwd * rh * math.cos(a) - axis * rh * math.sin(a))
    pts = [bottom + axis * 0.004] + pts
    handle = single(loft(pts, [(0.0042,) * 3] * len(pts), n=14, ring=10, cap0=0.0, cap1=0.003))
    ob = make_mesh("RAVEN_umbrella_handle", handle, [M["bone"]], coll, subsurf=1)
    bone_parent(ob, arm, "umbrella")
    tag(ob, "umbrella_handle")


# ===================================================================== cat

CAT_POSES = {
    # gathered (bound 0): legs under, back arched
    0: dict(spine=[(-0.205, 0, 0.200), (-0.150, 0, 0.188), (-0.090, 0, 0.192),
                   (-0.010, 0, 0.222), (0.065, 0, 0.200), (0.110, 0, 0.170)],
            head=(-0.250, 0.0, 0.190), pitch=-12.0,
            fl=[(-0.115, 0.155), (-0.080, 0.085), (-0.020, 0.040), (0.035, 0.012)],
            fr=[(-0.100, 0.155), (-0.055, 0.085), (0.005, 0.035), (0.060, 0.012)],
            hl=[(0.090, 0.160), (0.030, 0.110), (0.020, 0.050), (-0.050, 0.012)],
            hr=[(0.100, 0.160), (0.045, 0.110), (0.040, 0.050), (-0.025, 0.012)],
            tail=[(0.110, 0, 0.180), (0.170, 0, 0.215), (0.225, 0, 0.250),
                  (0.270, 0, 0.300), (0.300, 0, 0.330)]),
    # stretched (bound 1): long and flat, front legs reaching, hind legs back
    1: dict(spine=[(-0.275, 0, 0.200), (-0.205, 0, 0.192), (-0.135, 0, 0.188),
                   (-0.030, 0, 0.190), (0.075, 0, 0.186), (0.130, 0, 0.172)],
            head=(-0.340, 0.0, 0.205), pitch=-4.0,
            fl=[(-0.190, 0.160), (-0.275, 0.105), (-0.360, 0.060), (-0.410, 0.040)],
            fr=[(-0.175, 0.160), (-0.250, 0.098), (-0.320, 0.045), (-0.365, 0.022)],
            hl=[(0.115, 0.160), (0.170, 0.110), (0.260, 0.080), (0.320, 0.065)],
            hr=[(0.125, 0.160), (0.185, 0.100), (0.270, 0.060), (0.330, 0.040)],
            tail=[(0.135, 0, 0.175), (0.215, 0, 0.185), (0.300, 0, 0.195),
                  (0.380, 0, 0.215), (0.440, 0, 0.240)]),
}


def cat_geo(P):
    g = Geo()
    sp = P["spine"]
    # body: neck -> chest -> ribs -> loin -> haunch
    g.add(loft(sp, [(0.026, 0.028, 0.030), (0.042, 0.046, 0.060), (0.048, 0.050, 0.064),
                    (0.040, 0.044, 0.046), (0.046, 0.050, 0.054), (0.034, 0.034, 0.040)],
               n=14, ring=16, cap0=0.01, cap1=0.02))
    # head in local frame, then placed
    hc = Vector(P["head"])
    hr = Matrix.Rotation(math.radians(-P["pitch"]), 3, Y)
    T = lambda v: hc + hr @ (Vector(v) * 1.18)

    def place(part):
        vs, fs = part
        return [T(v) for v in vs], fs

    g.add(place(loft([(0.040, 0, 0.004), (0.010, 0, 0.004), (-0.022, 0, -0.002),
                      (-0.048, 0, -0.012)],
                     [(0.026, 0.026, 0.026), (0.038, 0.036, 0.034), (0.032, 0.028, 0.030),
                      (0.014, 0.012, 0.012)], n=7, ring=16, cap0=0.01, cap1=0.006)))
    for sgn in (-1, 1):
        b = Vector((0.010, sgn * 0.020, 0.024))
        tip = Vector((0.022, sgn * 0.030, 0.062))
        g.add(place(loft([b, b.lerp(tip, 0.5), tip],
                         [(0.009, 0.013, 0.013), (0.006, 0.009, 0.009), (0.001, 0.002, 0.002)],
                         n=4, ring=10, cap0=0.0, cap1=0.004, side=Vector((0, 0, 0)) + Y)))
    # legs (x, z) chains at +-y
    for key, y, r0 in (("fl", -0.030, 0.028), ("fr", 0.030, 0.028),
                       ("hl", -0.030, 0.042), ("hr", 0.030, 0.042)):
        pts = [Vector((x, y, z)) for x, z in P[key]]
        # shoulder / haunch start up inside the body so the leg grows out of it
        pts[0] = pts[0] + Vector((0, 0, 0.025))
        rad = [(r0 * 0.8, r0 * 1.1, r0 * 1.1), (r0 * 0.5,) * 3, (0.011,) * 3,
               (0.014, 0.011, 0.010)]
        g.add(loft(pts, rad, n=10, ring=10, cap0=0.006, cap1=0.012))
    # tail
    g.add(loft(P["tail"], [(0.020,) * 3, (0.012,) * 3, (0.011,) * 3, (0.010,) * 3, (0.009,) * 3],
               n=16, ring=10, cap0=0.004, cap1=0.012))
    # eyes (material 1): almonds on the face front
    for sgn in (-1, 1):
        g.add(place(ellipsoid((-0.026, sgn * 0.020, 0.010), (0.004, 0.0075, 0.0045),
                              rot=Matrix.Rotation(math.radians(sgn * 35.0), 3, (0, 0, 1)),
                              seg=10, rings=6)), mat=1)
    return g


def build_cat(M):
    coll = bpy.data.collections.new("CAT")
    bpy.context.scene.collection.children.link(coll)
    root = bpy.data.objects.new("CAT_ROOT", None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.1
    coll.objects.link(root)
    tag(root, "cat_root")
    root["bound"] = 0.0
    root.id_properties_ui("bound").update(min=0.0, max=1.0,
                                          description="0 gathered, 1 stretched")
    g0, g1 = cat_geo(CAT_POSES[0]), cat_geo(CAT_POSES[1])
    assert len(g0.verts) == len(g1.verts)
    ob = make_mesh("CAT_body", g0, [M["cat"], M["cat_eye"]], coll, subsurf=2)
    ob.shape_key_add(name="Basis", from_mix=False)
    sk = ob.shape_key_add(name="Stretch", from_mix=False)
    for i, v in enumerate(g1.verts):
        sk.data[i].co = v
    fc = sk.driver_add("value")
    fc.driver.type = "AVERAGE"
    var = fc.driver.variables.new()
    var.name = "bound"
    var.type = "SINGLE_PROP"
    var.targets[0].id_type = "OBJECT"
    var.targets[0].id = root
    var.targets[0].data_path = '["bound"]'
    ob.parent = root
    tag(ob, "cat_body")
    root.location = (0.0, 0.9, 0.0)
    return root


# ================================================================== review

def review():
    import time
    sys.path.insert(0, HERE)
    import rigs

    os.makedirs(REVIEW_DIR, exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    sc.render.resolution_percentage = 100
    sc.eevee.taa_render_samples = 32
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"

    world = bpy.data.worlds.new("review")
    world.color = (0.004, 0.004, 0.005)
    sc.world = world
    try:
        world.use_nodes = True
        bg = world.node_tree.nodes.get("Background")
        bg.inputs["Color"].default_value = (0.006, 0.006, 0.008, 1)
        bg.inputs["Strength"].default_value = 1.0
    except Exception:
        pass

    rc = bpy.data.collections.new("REVIEW")
    sc.collection.children.link(rc)
    wood = material("rv_floor", (0.045, 0.028, 0.016, 1), rough=0.6)
    wall = material("rv_wall", (0.030, 0.028, 0.026, 1), rough=0.9)
    fl = make_mesh("rv_floor", single(box((0, 0, -0.01), (8, 8, 0.02))), [wood], rc, subsurf=0,
                   smooth=False)
    wl = make_mesh("rv_wall", single(box((0, 1.4, 1.0), (8, 0.02, 2.0))), [wall], rc, subsurf=0,
                   smooth=False)

    def light(name, kind, loc, energy, color, size=0.3, aim=(0, 0, 0.18)):
        ld = bpy.data.lights.new(name, kind)
        ld.energy = energy
        ld.color = color
        if kind == "AREA":
            ld.size = size
        if kind == "SPOT":
            ld.spot_size = math.radians(50)
            ld.spot_blend = 0.6
        lo = bpy.data.objects.new(name, ld)
        rc.objects.link(lo)
        lo.location = loc
        d = Vector(aim) - Vector(loc)
        lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        return lo

    light("rv_key", "AREA", (-0.9, -1.0, 1.1), 55.0, (1.0, 0.78, 0.55), size=0.6)
    light("rv_rim", "SPOT", (0.7, 0.9, 0.7), 60.0, (0.62, 0.72, 1.0))
    light("rv_rim2", "SPOT", (-0.8, 0.8, 0.6), 30.0, (0.62, 0.72, 1.0))
    light("rv_fill", "AREA", (1.2, -1.2, 0.4), 6.0, (0.7, 0.75, 0.9), size=1.0)

    cam_d = bpy.data.cameras.new("rv_cam")
    cam_d.lens = 50
    cam = bpy.data.objects.new("rv_cam", cam_d)
    rc.objects.link(cam)
    sc.camera = cam

    def aim_cam(loc, target):
        cam.location = loc
        cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()

    raven = bpy.data.objects["RAVEN_ROOT"]
    cat = bpy.data.objects["CAT_ROOT"]
    cat.location = (0, 50, 0)
    times = []

    def shot(path, frame=None):
        if frame is not None:
            sc.frame_set(frame)
        sc.render.filepath = path
        t = time.time()
        bpy.ops.render.render(write_still=True)
        times.append(time.time() - t)
        return path

    # -- raven turnaround (rotate the bird, camera fixed)
    aim_cam((0.0, -1.25, 0.24), (-0.02, 0, 0.19))
    tiles = []
    for i, yaw in enumerate((0, -45, -90, 180 - 35, 30, -135)):
        raven.rotation_euler = (0, 0, math.radians(yaw))
        tiles.append(shot(os.path.join(REVIEW_DIR, "raven_turn_%d.png" % i)))
    raven.rotation_euler = (0, 0, 0)
    sheet(tiles, 3, os.path.join(REVIEW_DIR, "sheet_raven_turnaround.png"))

    # -- close-up hero 3/4
    aim_cam((-0.42, -0.62, 0.32), (-0.07, 0, 0.25))
    shot(os.path.join(REVIEW_DIR, "raven_hero.png"))
    aim_cam((-0.62, -0.22, 0.24), (-0.07, 0, 0.215))
    shot(os.path.join(REVIEW_DIR, "raven_front.png"))

    # -- walk: 6 frames, side view, walking +X like the shot
    sc.frame_start, sc.frame_end = 1, 80
    contacts = rigs.key_raven_walk(raven, 14, 62, (-0.6, 0.0), (0.6, 0.0), step_frames=6)
    tiles = []
    for f in (34, 36, 38, 40, 42, 44):
        sc.frame_set(f)
        x = raven.location.x
        aim_cam((x, -1.25, 0.22), (x, 0, 0.18))
        tiles.append(shot(os.path.join(REVIEW_DIR, "raven_walk_%03d.png" % f)))
    sheet(tiles, 3, os.path.join(REVIEW_DIR, "sheet_raven_walk.png"))

    # -- umbrella open + head turn to camera, after the walk
    aim_cam((0.55, -1.5, 0.30), (0.55, 0, 0.26))
    cam_pos = cam.location.copy()
    yaw = rigs.yaw_to_face(raven, 150, cam_pos)
    rigs.key_head_turn(raven, 150, 158, yaw, pitch_deg=4.0)
    rigs.key_tail_flick(raven, 60, axis="yaw")
    rigs.key_umbrella_open(raven, 162)
    tiles = []
    for f in (150, 156, 162, 164, 165, 168):
        tiles.append(shot(os.path.join(REVIEW_DIR, "raven_umbrella_%03d.png" % f), f))
    sheet(tiles, 3, os.path.join(REVIEW_DIR, "sheet_raven_umbrella.png"))

    # -- cat: both poses side, 3/4, and a bound loop
    raven.location = (0, 50, 0)
    for ob in [raven]:
        ob.animation_data_clear()
    raven.location = (0, 50, 0)
    cat.location = (0, 0, 0)
    tiles = []
    aim_cam((-0.05, -1.7, 0.22), (-0.03, 0, 0.17))
    for b in (0.0, 1.0):
        cat["bound"] = b
        cat.rotation_euler = (0, 0, 0)
        tiles.append(shot(os.path.join(REVIEW_DIR, "cat_pose_%d.png" % int(b))))
    for b, yaw in ((0.0, -40), (1.0, 40)):
        cat["bound"] = b
        cat.rotation_euler = (0, 0, math.radians(yaw))
        tiles.append(shot(os.path.join(REVIEW_DIR, "cat_pose_%d_%d.png" % (int(b), yaw))))
    cat.rotation_euler = (0, 0, 0)
    rigs.key_cat_bound(cat, 128, 146, (0.0, 0.0), (-0.01, 0.0), stride_frames=6)
    for f in (128, 130):
        tiles.append(shot(os.path.join(REVIEW_DIR, "cat_bound_%03d.png" % f), f))
    sheet(tiles, 3, os.path.join(REVIEW_DIR, "sheet_cat.png"))
    print("REVIEW render seconds per frame: mean %.2f max %.2f over %d"
          % (sum(times) / len(times), max(times), len(times)))
    print("REVIEW contacts", contacts)


def sheet(paths, cols, out):
    import numpy as np
    imgs = []
    for p in paths:
        im = bpy.data.images.load(p)
        w, h = im.size
        a = np.empty(w * h * 4, dtype=np.float32)
        im.pixels.foreach_get(a)
        imgs.append(a.reshape(h, w, 4))
        bpy.data.images.remove(im)
    h, w = imgs[0].shape[:2]
    rows = (len(imgs) + cols - 1) // cols
    canvas = np.zeros((rows * h, cols * w, 4), dtype=np.float32)
    canvas[..., 3] = 1.0
    for i, a in enumerate(imgs):
        r, c = divmod(i, cols)
        # pixel rows are bottom-up in Blender
        y0 = (rows - 1 - r) * h
        canvas[y0:y0 + h, c * w:(c + 1) * w] = a
    # 1 px separators
    for c in range(1, cols):
        canvas[:, c * w - 1:c * w + 1, :3] = 0.3
    for r in range(1, rows):
        canvas[r * h - 1:r * h + 1, :, :3] = 0.3
    im = bpy.data.images.new(os.path.basename(out), cols * w, rows * h, alpha=False)
    im.pixels.foreach_set(canvas.ravel())
    im.filepath_raw = out
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


# ==================================================================== main

def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.render.fps = 24
    M = build_materials()
    build_raven(M)
    build_cat(M)
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
    print("SAVED", OUT_BLEND)
    if "--review" in argv:
        review()


main()
