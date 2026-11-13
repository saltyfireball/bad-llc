"""Bad Omen studio ident (SLRM-1922): set, animation, lights, camera, render.

Builds tools/ident/ident.blend from nothing and renders PNG frames to
tools/ident/out/frames/. Follows tools/ident/BEATS.md frame by frame.

Run (headless):
  blender -b --factory-startup -P tools/ident/scene.py -- --render
  blender -b --factory-startup -P tools/ident/scene.py -- --render --preview
  blender -b --factory-startup -P tools/ident/scene.py -- --render --frames 110-150
  blender -b --factory-startup -P tools/ident/scene.py -- --render --preview --list 1,60,120,200

Options:
  --render        render after building (without it: build and save only)
  --preview       half resolution, low samples
  --frames A-B    render only frames A..B (1-based, inclusive)
  --list a,b,c    render only these frames (review stills)
  --out DIR       frame output dir (default tools/ident/out/frames)
  --proxies       ignore characters.blend and use the stand-in proxies

World layout (metres): X right, Y away from camera, Z up. The wall is the
plane y = WALL_Y facing the camera, the floor is z = 0. Left to right: the
ladder leans on the wall, the side table, the standing mirror.

Characters: if tools/ident/characters.blend exists, RAVEN_ROOT and CAT_ROOT
(with everything parented under them) are appended from it and keyed through
tools/ident/rigs.py. Otherwise simple proxies with the same root names are
built here, so the shot is blocked and timed either way.
"""

import math
import os
import random
import subprocess
import sys
import time

import bpy
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "out")
FPS = 24
F_START, F_END = 1, 216

WALL_Y = 1.25

# Palette (tokens.css), linear-ish values used for shading.
def srgb(hexstr):
    hexstr = hexstr.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(hexstr[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (out[0], out[1], out[2], 1.0)


BONE = srgb("#e8e2d6")
INK = srgb("#0b0b0c")
WARM = (1.0, 0.58, 0.28, 1.0)
COOL = (0.55, 0.7, 1.0, 1.0)

RNG = random.Random(1922)


# ----------------------------------------------------------------- args

def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    a = {"render": False, "preview": False, "frames": None, "list": None,
         "out": os.path.join(OUT, "frames"), "proxies": False}
    i = 0
    while i < len(argv):
        k = argv[i]
        if k == "--render":
            a["render"] = True
        elif k == "--preview":
            a["preview"] = True
        elif k == "--proxies":
            a["proxies"] = True
        elif k == "--frames":
            lo, hi = argv[i + 1].split("-")
            a["frames"] = (int(lo), int(hi))
            i += 1
        elif k == "--list":
            a["list"] = [int(x) for x in argv[i + 1].split(",") if x]
            i += 1
        elif k == "--out":
            a["out"] = os.path.abspath(argv[i + 1])
            i += 1
        i += 1
    return a


# ----------------------------------------------------------------- helpers

def set_interp(kind):
    bpy.context.preferences.edit.keyframe_new_interpolation_type = kind


def key(idb, path, frame, value=None, index=-1, interp="BEZIER"):
    """Key idb.path at frame; value (scalar or sequence) is set first."""
    set_interp(interp)
    if value is not None:
        cur = idb.path_resolve(path)
        if index >= 0:
            cur[index] = value
        elif hasattr(cur, "__len__") and not isinstance(cur, str):
            for j, v in enumerate(value):
                cur[j] = v
        else:
            setattr_path(idb, path, value)
    idb.keyframe_insert(path, frame=frame, index=index)


def setattr_path(idb, path, value):
    if "." in path or "[" in path:
        head, _, tail = path.rpartition(".")
        obj = idb.path_resolve(head) if head else idb
        setattr(obj, tail, value)
    else:
        setattr(idb, path, value)


def key_socket(sock, frame, value, interp="BEZIER"):
    set_interp(interp)
    sock.default_value = value
    sock.keyframe_insert("default_value", frame=frame)


def link_obj(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


def new_coll(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def mesh_obj(name, verts, faces, coll=None, mat=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    link_obj(ob, coll)
    if mat:
        me.materials.append(mat)
    return ob


def box(name, size, loc=(0, 0, 0), coll=None, mat=None, bevel=0.0, rot=None):
    sx, sy, sz = (s / 2.0 for s in size)
    v = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
         (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6),
         (3, 0, 4, 7)]
    ob = mesh_obj(name, v, f, coll, mat)
    ob.location = loc
    if rot:
        ob.rotation_euler = rot
    if bevel > 0:
        m = ob.modifiers.new("bevel", "BEVEL")
        m.width = bevel
        m.segments = 2
        m.limit_method = "ANGLE"
    return ob


def prim(kind, name, coll=None, mat=None, **kw):
    """Primitive via operator, moved into coll, smooth shaded if asked."""
    smooth = kw.pop("smooth", True)
    getattr(bpy.ops.mesh, "primitive_%s_add" % kind)(**kw)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.name = name
    if coll is not None:
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        coll.objects.link(ob)
    if mat:
        ob.data.materials.append(mat)
    if smooth:
        ob.data.shade_smooth()
    return ob


def empty(name, loc=(0, 0, 0), coll=None, parent=None, size=0.1):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = size
    link_obj(ob, coll)
    ob.location = loc
    if parent:
        ob.parent = parent
    return ob


def parent_keep(child, parent):
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()
    child.matrix_world = mw


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ----------------------------------------------------------------- materials

class NT:
    """Tiny node-tree builder for shader materials."""

    def __init__(self, mat):
        self.nt = mat.node_tree
        self.nodes = self.nt.nodes
        self.links = self.nt.links
        self.x = -1200

    def n(self, kind, **props):
        node = self.nodes.new(kind)
        node.location = (self.x, RNG.uniform(-300, 300))
        self.x += 160
        for k, v in props.items():
            if k.startswith("in_"):
                node.inputs[k[3:].replace("_", " ")].default_value = v
            else:
                setattr(node, k, v)
        return node

    def l(self, a, b):
        self.links.new(a, b)

    def math(self, op, a, b=None, clamp=False):
        m = self.n("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                m.inputs[i].default_value = v
            else:
                self.l(v, m.inputs[i])
        return m.outputs[0]

    def frame(self):
        node = self.n("ShaderNodeValue")
        node.label = "frame"
        fc = node.outputs[0].driver_add("default_value")
        fc.driver.type = "SCRIPTED"
        fc.driver.expression = "frame"
        return node.outputs[0]


def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, NT(m), m.node_tree.nodes["Principled BSDF"]


def set_in(node, name, v):
    node.inputs[name].default_value = v


def mat_plaster():
    m, t, p = new_mat("M_Plaster")
    tc = t.n("ShaderNodeTexCoord")
    nz = t.n("ShaderNodeTexNoise", in_Scale=3.0, in_Detail=8.0, in_Roughness=0.62)
    t.l(tc.outputs["Object"], nz.inputs["Vector"])
    nz2 = t.n("ShaderNodeTexNoise", in_Scale=38.0, in_Detail=4.0)
    t.l(tc.outputs["Object"], nz2.inputs["Vector"])
    ramp = t.n("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.016, 0.015, 0.014, 1)
    ramp.color_ramp.elements[1].color = (0.05, 0.045, 0.04, 1)
    t.l(nz.outputs["Fac"], ramp.inputs["Fac"])
    t.l(ramp.outputs["Color"], p.inputs["Base Color"])
    set_in(p, "Roughness", 0.93)
    bump = t.n("ShaderNodeBump", in_Strength=0.35, in_Distance=0.01)
    mix = t.math("ADD", nz.outputs["Fac"], t.math("MULTIPLY", nz2.outputs["Fac"], 0.6))
    t.l(mix, bump.inputs["Height"])
    t.l(bump.outputs["Normal"], p.inputs["Normal"])
    return m


def mat_wood(name, base, dark, scale=(1.0, 1.0, 1.0), planks=False, rough=0.55):
    m, t, p = new_mat(name)
    tc = t.n("ShaderNodeTexCoord")
    mp = t.n("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = scale
    t.l(tc.outputs["Object"], mp.inputs["Vector"])
    wave = t.n("ShaderNodeTexWave", wave_type="BANDS", bands_direction="X",
               in_Scale=6.0, in_Distortion=7.0, in_Detail=3.0, in_Detail_Scale=1.5)
    t.l(mp.outputs["Vector"], wave.inputs["Vector"])
    nz = t.n("ShaderNodeTexNoise", in_Scale=14.0, in_Detail=6.0)
    t.l(mp.outputs["Vector"], nz.inputs["Vector"])
    grain = t.math("MULTIPLY", t.math("ADD", wave.outputs["Fac"], nz.outputs["Fac"]), 0.5)
    ramp = t.n("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = dark
    ramp.color_ramp.elements[1].color = base
    seam = None
    if planks:
        br = t.n("ShaderNodeTexBrick", offset=0.5, squash=1.0,
                 in_Scale=1.0, in_Mortar_Size=0.004, in_Brick_Width=1.6,
                 in_Row_Height=0.14, in_Bias=0.0)
        br.inputs["Color1"].default_value = (1, 1, 1, 1)
        br.inputs["Color2"].default_value = (0.7, 0.7, 0.7, 1)
        br.inputs["Mortar"].default_value = (0, 0, 0, 1)
        bm = t.n("ShaderNodeMapping")
        bm.inputs["Rotation"].default_value = (0, 0, math.radians(90))
        t.l(tc.outputs["Object"], bm.inputs["Vector"])
        t.l(bm.outputs["Vector"], br.inputs["Vector"])
        seam = br.outputs["Fac"]
        tone = t.math("MULTIPLY", grain, br.outputs["Color"])
        t.l(tone, ramp.inputs["Fac"])
    else:
        t.l(grain, ramp.inputs["Fac"])
    t.l(ramp.outputs["Color"], p.inputs["Base Color"])
    rr = t.math("ADD", t.math("MULTIPLY", nz.outputs["Fac"], 0.25), rough - 0.1)
    t.l(rr, p.inputs["Roughness"])
    bump = t.n("ShaderNodeBump", in_Strength=0.15, in_Distance=0.004)
    h = grain if seam is None else t.math("SUBTRACT", grain, t.math("MULTIPLY", seam, 2.0))
    t.l(h, bump.inputs["Height"])
    t.l(bump.outputs["Normal"], p.inputs["Normal"])
    return m


def mat_simple(name, color, rough=0.5, metal=0.0, emit=None, estr=0.0):
    m, t, p = new_mat(name)
    set_in(p, "Base Color", color)
    set_in(p, "Roughness", rough)
    set_in(p, "Metallic", metal)
    if emit:
        set_in(p, "Emission Color", emit)
        set_in(p, "Emission Strength", estr)
    return m


def mat_glass(name, tint=(0.95, 0.97, 0.98, 1), rough=0.04):
    m, t, p = new_mat(name)
    set_in(p, "Base Color", tint)
    set_in(p, "Roughness", rough)
    set_in(p, "Transmission Weight", 1.0)
    set_in(p, "IOR", 1.5)
    return m


def mat_mirror():
    m, t, p = new_mat("M_MirrorGlass")
    set_in(p, "Base Color", (0.62, 0.64, 0.66, 1))
    set_in(p, "Metallic", 1.0)
    tc = t.n("ShaderNodeTexCoord")
    nz = t.n("ShaderNodeTexNoise", in_Scale=9.0, in_Detail=5.0)
    t.l(tc.outputs["Object"], nz.inputs["Vector"])
    r = t.math("ADD", t.math("MULTIPLY", nz.outputs["Fac"], 0.05), 0.0)
    t.l(r, p.inputs["Roughness"])
    return m


def mat_reveal(name, color, strength, flash, width_alpha=False, alpha=1.0,
               speed=0.8, craze=0.0):
    """Emission that appears per point once frame >= attribute 'rev'.

    width_alpha: soften across the ribbon (UV v) for a glow halo.
    craze: Voronoi cell scale (1/m) for crazed glass; cell edges glow
    brighter than the cell faces, so a fill reads as shattered, not flat.
    """
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.surface_render_method = "DITHERED"
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    t = NT(m)
    out = t.n("ShaderNodeOutputMaterial")
    attr = t.n("ShaderNodeAttribute", attribute_name="rev")
    fr = t.frame()
    age = t.math("SUBTRACT", fr, attr.outputs["Fac"])
    mask = t.math("MULTIPLY", age, speed, clamp=True)
    # flash: bright at the crack tip, decays over ~6 frames
    dec = t.math("EXPONENT", t.math("MULTIPLY", t.math("MAXIMUM", age, 0.0), -0.35))
    st = t.math("ADD", strength, t.math("MULTIPLY", dec, flash))
    bri = t.n("ShaderNodeAttribute", attribute_name="bri")
    st = t.math("MULTIPLY", st, bri.outputs["Fac"])
    a_craze = None
    if craze:
        tc = t.n("ShaderNodeTexCoord")
        vor = t.n("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
        vor.inputs["Scale"].default_value = craze
        vor.inputs["Randomness"].default_value = 0.9
        t.l(tc.outputs["Object"], vor.inputs["Vector"])
        # 1 on a crack between cells, falling to 0 a few mm in
        edge = t.math("SUBTRACT", 1.0, t.math("MULTIPLY", vor.outputs["Distance"], 9.0),
                      clamp=True)
        st = t.math("MULTIPLY", st, t.math("ADD", 0.55, t.math("MULTIPLY", edge, 1.6)))
        a_craze = t.math("ADD", 0.6, t.math("MULTIPLY", edge, 0.8))
    em = t.n("ShaderNodeEmission")
    em.inputs["Color"].default_value = color
    t.l(st, em.inputs["Strength"])
    a = mask
    if width_alpha:
        uv = t.n("ShaderNodeUVMap")
        sep = t.n("ShaderNodeSeparateXYZ")
        t.l(uv.outputs["UV"], sep.inputs["Vector"])
        prof = t.math("SUBTRACT", 1.0, t.math("ABSOLUTE", t.math(
            "SUBTRACT", t.math("MULTIPLY", sep.outputs["Y"], 2.0), 1.0)))
        prof = t.math("POWER", prof, 2.2)
        a = t.math("MULTIPLY", a, prof)
    a = t.math("MULTIPLY", a, alpha)
    if a_craze is not None:
        a = t.math("MULTIPLY", a, a_craze, clamp=True)
    tr = t.n("ShaderNodeBsdfTransparent")
    mix = t.n("ShaderNodeMixShader")
    t.l(a, mix.inputs["Fac"])
    t.l(tr.outputs[0], mix.inputs[1])
    t.l(em.outputs[0], mix.inputs[2])
    t.l(mix.outputs[0], out.inputs["Surface"])
    return m


def mat_fade_emit(name, color, alpha_key, strength=1.0):
    """Emission + transparency whose Mix factor is keyed (list of (f, a))."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.surface_render_method = "DITHERED"
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    t = NT(m)
    out = t.n("ShaderNodeOutputMaterial")
    em = t.n("ShaderNodeEmission")
    em.inputs["Color"].default_value = color
    em.inputs["Strength"].default_value = strength
    tr = t.n("ShaderNodeBsdfTransparent")
    mix = t.n("ShaderNodeMixShader")
    mix.name = "FADE"
    t.l(tr.outputs[0], mix.inputs[1])
    t.l(em.outputs[0], mix.inputs[2])
    t.l(mix.outputs[0], out.inputs["Surface"])
    for f, a in alpha_key:
        key_socket(mix.inputs["Fac"], f, a)
    return m, em


# ----------------------------------------------------------------- set

BACK_Y = -3.6
DOOR_X = (1.6, 2.3)


def mat_backwall():
    """The wall behind the camera, only ever seen in the mirror: plaster
    with a faint warm wash as if the bulb reached it."""
    m, t, p = new_mat("M_BackWall")
    set_in(p, "Base Color", (0.03, 0.026, 0.022, 1))
    set_in(p, "Roughness", 0.9)
    tc = t.n("ShaderNodeTexCoord")
    sep = t.n("ShaderNodeSeparateXYZ")
    t.l(tc.outputs["Object"], sep.inputs["Vector"])
    # brightest up and to the left (toward the bulb), falling off outward
    dx = t.math("SUBTRACT", sep.outputs["X"], -0.4)
    dz = t.math("SUBTRACT", sep.outputs["Z"], 1.5)
    r2 = t.math("ADD", t.math("MULTIPLY", dx, dx), t.math("MULTIPLY", dz, dz))
    wash = t.math("EXPONENT", t.math("MULTIPLY", r2, -0.35))
    nz = t.n("ShaderNodeTexNoise", in_Scale=6.0, in_Detail=6.0)
    t.l(tc.outputs["Object"], nz.inputs["Vector"])
    grain = t.math("ADD", 0.75, t.math("MULTIPLY", nz.outputs["Fac"], 0.5))
    st = t.math("MULTIPLY", t.math("MULTIPLY", wash, grain), BACK_GLOW)
    set_in(p, "Emission Color", (1.0, 0.6, 0.32, 1))
    t.l(st, p.inputs["Emission Strength"])
    return m


BACK_GLOW = 0.1


def build_room(coll):
    plaster = mat_plaster()
    floor_m = mat_wood("M_Floor", (0.09, 0.05, 0.028, 1), (0.02, 0.011, 0.007, 1),
                       scale=(5.0, 0.6, 1.0), planks=True, rough=0.5)
    floor = mesh_obj("Floor", [(-6, -7, 0), (6, -7, 0), (6, WALL_Y, 0), (-6, WALL_Y, 0)],
                     [(0, 1, 2, 3)], coll, floor_m)
    wall = mesh_obj("Wall", [(-6, WALL_Y, 0), (6, WALL_Y, 0), (6, WALL_Y, 5), (-6, WALL_Y, 5)],
                    [(0, 1, 2, 3)], coll, plaster)
    # The rest of the room (behind and beside the camera) for the mirror to
    # reflect: plain plaster, a dim doorway of cool light behind the camera.
    BY = BACK_Y
    back = mat_backwall()
    mesh_obj("WallBack", [(6, BY, 0), (-6, BY, 0), (-6, BY, 5), (6, BY, 5)],
             [(0, 1, 2, 3)], coll, back)
    mesh_obj("WallL", [(-4, BY, 0), (-4, WALL_Y, 0), (-4, WALL_Y, 5), (-4, BY, 5)],
             [(0, 1, 2, 3)], coll, plaster)
    mesh_obj("WallR", [(4, WALL_Y, 0), (4, BY, 0), (4, BY, 5), (4, WALL_Y, 5)],
             [(0, 1, 2, 3)], coll, plaster)
    mesh_obj("Ceiling", [(-6, BY, 3.2), (-6, WALL_Y, 3.2), (6, WALL_Y, 3.2), (6, BY, 3.2)],
             [(0, 1, 2, 3)], coll, plaster)
    door = mat_simple("M_Doorway", (0, 0, 0, 1), 1.0, emit=(0.5, 0.62, 0.9, 1), estr=0.12)
    mesh_obj("Doorway", [(DOOR_X[0], BY + 0.02, 0), (DOOR_X[1], BY + 0.02, 0),
                         (DOOR_X[1], BY + 0.02, 2.0), (DOOR_X[0], BY + 0.02, 2.0)],
             [(0, 3, 2, 1)], coll, door)
    # skirting board
    box("Skirting", (12, 0.02, 0.09), (0, WALL_Y - 0.01, 0.045), coll,
        mat_simple("M_Skirt", (0.018, 0.016, 0.014, 1), 0.6))
    return floor, wall


LADDER = {
    "foot_y": 0.45, "top_z": 1.35, "x_left": -0.95, "x_right": -0.60,
}


def build_ladder(coll):
    wood = mat_wood("M_Ladder", (0.17, 0.105, 0.055, 1), (0.05, 0.03, 0.015, 1),
                    scale=(8.0, 8.0, 0.6))
    L = LADDER
    foot_y, top_z = L["foot_y"], L["top_z"]
    run = WALL_Y - 0.03 - foot_y
    length = math.hypot(run, top_z)
    lean = math.atan2(run, top_z)  # from vertical, toward +Y
    # Pivot at the right foot so it tips right around it.
    root = empty("LADDER_ROOT", (L["x_right"], foot_y, 0.0), coll, size=0.2)
    frame = empty("LADDER_FRAME", (0, 0, 0), coll, parent=root, size=0.1)
    frame.rotation_euler = (-lean, 0, 0)
    w = L["x_right"] - L["x_left"]
    parts = []
    for side, x in (("L", -w), ("R", 0.0)):
        r = box("Ladder_Rail_" + side, (0.045, 0.028, length), (x, 0, length / 2), coll,
                wood, bevel=0.004)
        r.parent = frame
        parts.append(r)
    n_rungs = 6
    for i in range(n_rungs):
        z = 0.28 + i * (length - 0.4) / (n_rungs - 1)
        r = box("Ladder_Rung_%d" % i, (w, 0.05, 0.022), (-w / 2, 0, z), coll, wood,
                bevel=0.003)
        r.parent = frame
        parts.append(r)
    L["length"] = length
    L["lean"] = lean
    L["width"] = w
    return root, parts


TABLE = {"x": 0.15, "y": 0.98, "w": 0.42, "d": 0.36, "h": 0.55}


def build_table(coll):
    wood = mat_wood("M_Table", (0.11, 0.06, 0.035, 1), (0.03, 0.016, 0.01, 1),
                    scale=(3.0, 3.0, 3.0), rough=0.4)
    T = TABLE
    root = empty("TABLE_ROOT", (T["x"], T["y"], 0.0), coll, size=0.2)
    top = box("Table_Top", (T["w"], T["d"], 0.03), (0, 0, T["h"] - 0.015), coll, wood,
              bevel=0.006)
    top.parent = root
    apron = box("Table_Apron", (T["w"] - 0.06, T["d"] - 0.06, 0.08), (0, 0, T["h"] - 0.07),
                coll, wood, bevel=0.003)
    apron.parent = root
    for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
        lg = box("Table_Leg_%d" % i, (0.035, 0.035, T["h"] - 0.03),
                 (sx * (T["w"] / 2 - 0.04), sy * (T["d"] / 2 - 0.04), (T["h"] - 0.03) / 2),
                 coll, wood, bevel=0.003)
        lg.parent = root
    return root


SHAKER = {"r": 0.034, "h": 0.12}


def build_shaker(coll, table_root):
    T, S = TABLE, SHAKER
    glass = mat_glass("M_ShakerGlass")
    metal = mat_simple("M_ShakerCap", (0.85, 0.83, 0.78, 1), 0.18, 1.0)
    salt = mat_simple("M_Salt", (0.9, 0.89, 0.86, 1), 0.6)
    # Near the left edge, pivot at its bottom left edge: when the ladder
    # shoves the table right, the shaker tips left and its cap hangs over the
    # edge, so the salt pours down between the table and the ladder, in the
    # light and clear of the raven.
    x0 = -T["w"] / 2 + 0.115
    root = empty("SHAKER_ROOT", (x0 - S["r"], -0.07, T["h"]), coll, parent=table_root,
                 size=0.05)
    body = prim("cylinder", "Shaker_Glass", coll, glass, vertices=32, radius=S["r"],
                depth=S["h"] * 0.82, location=(0, 0, 0))
    body.location = (S["r"], 0, S["h"] * 0.41)
    body.parent = root
    sol = body.modifiers.new("solid", "SOLIDIFY")
    sol.thickness = 0.0025
    fill = prim("cylinder", "Shaker_Salt", coll, salt, vertices=24, radius=S["r"] * 0.86,
                depth=S["h"] * 0.4)
    fill.location = (S["r"], 0, S["h"] * 0.22)
    fill.parent = root
    cap = prim("cylinder", "Shaker_Cap", coll, metal, vertices=32, radius=S["r"] * 1.02,
               depth=S["h"] * 0.2)
    cap.location = (S["r"], 0, S["h"] * 0.9)
    cap.parent = root
    top = prim("uv_sphere", "Shaker_CapTop", coll, metal, segments=24, ring_count=8,
               radius=S["r"] * 1.02)
    top.scale = (1, 1, 0.35)
    top.location = (S["r"], 0, S["h"])
    top.parent = root
    mouth = empty("SHAKER_MOUTH", (S["r"], 0, S["h"] + 0.006), coll, parent=root, size=0.01)
    return root, mouth


MIRROR = {"x": 0.95, "y": 0.92, "gw": 0.8, "gh": 1.08, "gz": 0.32, "yaw": -6.0}


def build_mirror(coll):
    M = MIRROR
    wood = mat_wood("M_MirrorFrame", (0.06, 0.035, 0.02, 1), (0.015, 0.009, 0.006, 1),
                    scale=(4.0, 4.0, 1.0), rough=0.35)
    feet_d = 0.36
    # Root pivots at the front feet edge (so it tips toward camera on it).
    root = empty("MIRROR_ROOT", (M["x"], M["y"] - feet_d / 2, 0.0), coll, size=0.3)
    root.rotation_euler = (0, 0, math.radians(M["yaw"]))
    body = empty("MIRROR_BODY", (0, 0, 0), coll, parent=root, size=0.2)
    off = feet_d / 2  # glass plane sits at root y + off
    gw, gh, gz = M["gw"], M["gh"], M["gz"]
    fw = 0.055
    # frame pieces
    parts = [
        ("Mirror_FrameL", (fw, 0.04, gh + 2 * fw), (-gw / 2 - fw / 2, off, gz + gh / 2)),
        ("Mirror_FrameR", (fw, 0.04, gh + 2 * fw), (gw / 2 + fw / 2, off, gz + gh / 2)),
        ("Mirror_FrameT", (gw, 0.04, fw), (0, off, gz + gh + fw / 2)),
        ("Mirror_FrameB", (gw, 0.04, fw), (0, off, gz - fw / 2)),
        ("Mirror_Back", (gw, 0.012, gh), (0, off + 0.016, gz + gh / 2)),
    ]
    for nm, size, loc in parts:
        b = box(nm, size, loc, coll, wood, bevel=0.006)
        b.parent = body
    # stand: two posts and feet
    for side in (-1, 1):
        x = side * (gw / 2 + fw + 0.03)
        post = box("Mirror_Post_%d" % side, (0.04, 0.04, gz + gh * 0.62), (x, off, (gz + gh * 0.62) / 2),
                   coll, wood, bevel=0.006)
        post.parent = body
        foot = box("Mirror_Foot_%d" % side, (0.05, feet_d, 0.035), (x, off, 0.0175), coll, wood,
                   bevel=0.008)
        foot.parent = body
        pin = prim("cylinder", "Mirror_Pin_%d" % side, coll,
                   mat_simple("M_Brass", (0.5, 0.36, 0.16, 1), 0.3, 1.0),
                   vertices=16, radius=0.012, depth=0.03)
        pin.rotation_euler = (0, math.radians(90), 0)
        pin.location = (side * (gw / 2 + fw + 0.0), off, gz + gh * 0.55)
        pin.parent = body
    glass = mesh_obj("Mirror_Glass",
                     [(-gw / 2, 0, 0), (gw / 2, 0, 0), (gw / 2, 0, gh), (-gw / 2, 0, gh)],
                     [(0, 1, 2, 3)], coll, mat_mirror())
    glass.location = (0, off - 0.006, gz)
    glass.parent = body
    # Planar probe for exact mirror reflections in EEVEE.
    pd = bpy.data.lightprobes.new("MirrorProbe", "PLANE")
    probe = bpy.data.objects.new("MirrorProbe", pd)
    link_obj(probe, coll)
    probe.parent = glass
    probe.location = (0, 0, gh / 2)
    probe.rotation_euler = (math.radians(90), 0, 0)
    probe.scale = (gw / 2, gh / 2, 1)
    try:
        pd.show_data = False
    except AttributeError:
        pass
    return root, body, glass


def build_bulb(coll):
    pos = Vector((-0.22, 0.55, 1.36))
    glass = mat_simple("M_Bulb", (1, 0.9, 0.7, 1), 0.1, emit=WARM, estr=60.0)
    bulb = prim("uv_sphere", "Bulb", coll, glass, segments=24, ring_count=16, radius=0.032,
                location=pos)
    bulb.scale = (1, 1, 1.25)
    bulb.visible_shadow = False  # the light sits inside it
    sock = prim("cylinder", "Bulb_Socket", coll,
                mat_simple("M_Socket", (0.02, 0.02, 0.02, 1), 0.4),
                vertices=16, radius=0.018, depth=0.05, location=pos + Vector((0, 0, 0.06)))
    cord = prim("cylinder", "Bulb_Cord", coll,
                mat_simple("M_Cord", (0.01, 0.01, 0.01, 1), 0.6),
                vertices=8, radius=0.003, depth=2.0, location=pos + Vector((0, 0, 1.08)))
    ld = bpy.data.lights.new("BulbLight", "POINT")
    ld.energy = 90.0
    ld.color = WARM[:3]
    ld.shadow_soft_size = 0.03
    lo = bpy.data.objects.new("BulbLight", ld)
    link_obj(lo, coll)
    lo.location = pos
    return lo, bulb


def build_lights(coll):
    # Cool rim from behind right, high.
    rd = bpy.data.lights.new("RimLight", "AREA")
    rd.energy = 70.0
    rd.color = COOL[:3]
    rd.shape = "RECTANGLE"
    rd.size, rd.size_y = 0.6, 1.4
    rim = bpy.data.objects.new("RimLight", rd)
    link_obj(rim, coll)
    rim.location = (3.0, 1.05, 1.5)
    aim(rim, Vector((0.6, 0.4, 0.45)))
    # Second cool rim from the far left for the ladder and raven edges.
    rd2 = bpy.data.lights.new("RimLightL", "AREA")
    rd2.energy = 30.0
    rd2.color = COOL[:3]
    rd2.size = 0.8
    rim2 = bpy.data.objects.new("RimLightL", rd2)
    link_obj(rim2, coll)
    rim2.location = (-2.8, 1.0, 1.2)
    aim(rim2, Vector((-0.6, 0.5, 0.3)))
    # Very low fill from the camera side so blacks keep their shape.
    fd = bpy.data.lights.new("Fill", "AREA")
    fd.energy = 6.0
    fd.color = (0.75, 0.8, 0.95)
    fd.size = 3.0
    fill = bpy.data.objects.new("Fill", fd)
    link_obj(fill, coll)
    fill.location = (0.4, BACK_Y + 0.3, 1.6)
    aim(fill, Vector((0.4, 0.8, 0.5)))
    return rim, rim2, fill


def aim(ob, target):
    d = target - Vector(ob.location)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


# ----------------------------------------------------------------- wordmark cracks

def parse_svg_path(d):
    """Return list of closed subpaths, each a list of (x, y) in SVG units."""
    import re
    toks = re.findall(r"[MQVHLZ]|-?\d*\.?\d+(?:e-?\d+)?", d)
    subs, cur = [], []
    x = y = 0.0
    i = 0
    cmd = None

    def num():
        nonlocal i
        v = float(toks[i])
        i += 1
        return v

    while i < len(toks):
        t = toks[i]
        if t in "MQVHLZ":
            cmd = t
            i += 1
            if cmd == "Z":
                if cur:
                    subs.append(cur)
                cur = []
                continue
        if cmd == "M":
            x, y = num(), num()
            if cur:
                subs.append(cur)
            cur = [(x, y)]
            cmd = "L"
        elif cmd == "L":
            x, y = num(), num()
            cur.append((x, y))
        elif cmd == "V":
            y = num()
            cur.append((x, y))
        elif cmd == "H":
            x = num()
            cur.append((x, y))
        elif cmd == "Q":
            cx, cy, ex, ey = num(), num(), num(), num()
            for k in range(1, 7):
                s = k / 6.0
                px = (1 - s) ** 2 * x + 2 * (1 - s) * s * cx + s * s * ex
                py = (1 - s) ** 2 * y + 2 * (1 - s) * s * cy + s * s * ey
                cur.append((px, py))
            x, y = ex, ey
    if cur:
        subs.append(cur)
    return subs


def load_wordmark():
    import re
    with open(os.path.join(REPO, "public", "img", "wordmark.svg")) as fh:
        svg = fh.read()
    d = re.search(r' d="([^"]+)"', svg).group(1)
    return parse_svg_path(d)


def resample(pts, step, closed=True):
    pts = list(pts)
    if closed:
        pts = pts + [pts[0]]
    out = [Vector(pts[0])]
    carry = 0.0
    for a, b in zip(pts, pts[1:]):
        a, b = Vector(a), Vector(b)
        seg = (b - a).length
        if seg == 0:
            continue
        d = step - carry
        while d <= seg:
            out.append(a + (b - a) * (d / seg))
            d += step
        carry = seg - (d - step)
    return out


def jag(pts, amp, rng, closed=True):
    """Jitter points sideways into a jagged crack line."""
    out = []
    n = len(pts)
    for i, p in enumerate(pts):
        a = pts[(i - 1) % n] if (closed or i > 0) else p
        b = pts[(i + 1) % n] if (closed or i < n - 1) else p
        t = (b - a)
        nrm = Vector((-t.y, t.x)).normalized() if t.length > 0 else Vector((0, 0))
        out.append(p + nrm * rng.uniform(-amp, amp))
    return out


class Ribbons:
    """Accumulates flat ribbons (polyline strips) and small triangles on the
    glass plane.

    Points are 2D (u, v) in metres on the glass, u right, v up from the
    glass bottom. Each point carries 'rev', the frame it appears, and 'bri',
    a brightness multiplier (fracture lines are never evenly lit).
    """

    def __init__(self):
        self.verts, self.faces, self.rev, self.uv, self.bri = [], [], [], [], []

    def add(self, pts, revs, width, closed=False, taper=True, bri=1.0):
        n = len(pts)
        if n < 2:
            return
        base = len(self.verts)
        for i, p in enumerate(pts):
            a = pts[i - 1] if i > 0 else (pts[-1] if closed else p)
            b = pts[i + 1] if i < n - 1 else (pts[0] if closed else p)
            t = (b - a)
            if t.length == 0:
                t = Vector((1, 0))
            nrm = Vector((-t.y, t.x)).normalized()
            w = width * RNG.uniform(0.7, 1.2)
            if taper and not closed:
                w *= 0.2 + 0.8 * min(1.0, 3.0 * min(i, n - 1 - i) / max(1, n - 1))
            for s, vv in ((-0.5, 0.0), (0.5, 1.0)):
                q = p + nrm * (w * s)
                self.verts.append((q.x, q.y))
                self.rev.append(revs[i])
                self.bri.append(bri)
                self.uv.append((i / max(1, n - 1), vv))
        segs = n if closed else n - 1
        for i in range(segs):
            j = (i + 1) % n
            self.faces.append((base + 2 * i, base + 2 * i + 1, base + 2 * j + 1, base + 2 * j))

    def add_tri(self, a, b, c, rev, bri=1.0):
        base = len(self.verts)
        for p, uv in ((a, (0, 0)), (b, (1, 0)), (c, (0.5, 1))):
            self.verts.append((p.x, p.y))
            self.rev.append(rev)
            self.bri.append(bri)
            self.uv.append(uv)
        self.faces.append((base, base + 1, base + 2))

    def build(self, name, coll, mat, parent, gw, depth):
        verts = [(u - gw / 2, -depth, v) for u, v in self.verts]
        ob = mesh_obj(name, verts, self.faces, coll, mat)
        me = ob.data
        for nm, data in (("rev", self.rev), ("bri", self.bri)):
            at = me.attributes.new(nm, "FLOAT", "POINT")
            at.data.foreach_set("value", data)
        uvl = me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            for li in poly.loop_indices:
                vi = me.loops[li].vertex_index
                uvl.data[li].uv = self.uv[vi]
        ob.parent = parent
        ob.visible_shadow = False
        return ob


def crack_line(a, b, rng, seg=0.012, amp=0.004):
    """Jagged line from a to b."""
    a, b = Vector(a), Vector(b)
    n = max(2, int((b - a).length / seg))
    d = (b - a)
    nrm = Vector((-d.y, d.x)).normalized()
    pts = []
    off = 0.0
    for i in range(n + 1):
        t = i / n
        if 0 < i < n:
            off = off * 0.4 + rng.uniform(-amp, amp)
        else:
            off = 0.0
        pts.append(a + d * t + nrm * off)
    return pts


def inside_loops(p, loops):
    """Even-odd point-in-polygon over all glyph loops (holes included)."""
    c = False
    for lp in loops:
        n = len(lp)
        for i in range(n):
            a, b = lp[i], lp[i - 1]
            if (a.y > p.y) != (b.y > p.y):
                x = a.x + (p.y - a.y) * (b.x - a.x) / (b.y - a.y)
                if p.x < x:
                    c = not c
    return c


def loop_normal(pts, i):
    n = len(pts)
    t = pts[(i + 1) % n] - pts[i - 1]
    if t.length == 0:
        return Vector((0, 1))
    return Vector((-t.y, t.x)).normalized()


def build_cracks(coll, glass):
    """Fracture lines on the mirror glass that happen to form BAD OMEN.

    The impact sits in the gap between the two words; a web of radial
    cracks and broken rings races out from it at f120, and connector cracks
    run into every letter. Each letter edge then fractures: the outline is
    re-cut into short straight runs with kinks, small sideways steps and
    gaps (never a clean continuous outline), with radial spurs and a few
    loose shards catching the light. There is no fill: the letters exist
    only as fracture lines, lit faintly from within.
    """
    M = MIRROR
    gw, gh = M["gw"], M["gh"]
    rng = random.Random(120)
    subs = load_wordmark()
    # SVG bounds: x -1.1..353.7, y -79.1..5.2. Map to glass (u, v).
    word_w = gw * 0.92
    s = word_w / 354.8
    word_h = 84.3 * s
    cx, cy = (-1.1 + 353.7) / 2, (-79.1 + 5.2) / 2
    wc = Vector((gw / 2, gh * 0.6))  # wordmark centre on the glass

    def to_glass(p):
        return Vector((wc.x + (p[0] - cx) * s, wc.y - (p[1] - cy) * s))

    loops = [[to_glass(p) for p in sp] for sp in subs]
    # Impact: in the widest gap between letters near the middle (the word
    # space), a little above the centre line.
    spans = sorted((min(p.x for p in lp), max(p.x for p in lp)) for lp in loops)
    merged = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    gaps = [((merged[i][1] + merged[i + 1][0]) / 2, merged[i + 1][0] - merged[i][1])
            for i in range(len(merged) - 1)]
    gx = max(gaps, key=lambda g: g[1] - 0.5 * abs(g[0] - wc.x))[0] if gaps else wc.x
    impact = Vector((gx, wc.y + word_h * 0.12))
    F0 = 120.0
    word = Ribbons()    # the letter fractures (bright)
    glow = Ribbons()    # faint halo along the letter fractures
    glassr = Ribbons()  # the web: rays, rings, connectors
    shards = Ribbons()  # loose facets inside the strokes

    # Radial web from the impact, fast (f120-127). Rays aimed along the
    # word line would scribble across the letters, so they go up and down.
    n_rays = 11
    for k in range(n_rays):
        ang = 2 * math.pi * (k + rng.uniform(-0.3, 0.3)) / n_rays
        if abs(math.sin(ang)) < 0.45:
            lim = math.asin(0.45) * (1.0 if math.sin(ang) >= 0 else -1.0)
            ang = lim if math.cos(ang) > 0 else math.pi - lim
        d = Vector((math.cos(ang), math.sin(ang)))
        ts = []
        for comp, lim in ((0, gw), (1, gh)):
            if d[comp] > 1e-6:
                ts.append((lim - impact[comp]) / d[comp])
            elif d[comp] < -1e-6:
                ts.append(-impact[comp] / d[comp])
        L = min(ts) * rng.uniform(0.45, 1.0)
        end = impact + d * L
        pts = crack_line(impact, end, rng, seg=0.012, amp=0.005)
        revs = [F0 + (p - impact).length / 0.11 for p in pts]
        glassr.add(pts, revs, 0.0015, bri=rng.uniform(0.7, 1.3))
        for _ in range(rng.randint(1, 3)):
            t = rng.uniform(0.2, 0.8)
            o = impact + d * (L * t)
            bang = ang + rng.choice((-1, 1)) * rng.uniform(0.4, 0.9)
            bl = rng.uniform(0.03, 0.12)
            b_end = o + Vector((math.cos(bang), math.sin(bang))) * bl
            bp = crack_line(o, b_end, rng, seg=0.009, amp=0.003)
            r0 = F0 + (o - impact).length / 0.11
            glassr.add(bp, [r0 + (p - o).length / 0.08 for p in bp], 0.0011,
                       bri=rng.uniform(0.6, 1.1))
    # Broken rings around the impact.
    for rad, f in ((0.016, 120.5), (0.034, 121.5), (0.06, 123.0)):
        a0 = rng.uniform(0, 2 * math.pi)
        n = max(8, int(rad * 300))
        pieces = rng.randint(2, 4)
        for pc in range(pieces):
            a_s = a0 + pc * 2 * math.pi / pieces
            a_l = rng.uniform(0.45, 0.8) * 2 * math.pi / pieces
            arc = []
            for k in range(n // pieces + 2):
                a = a_s + a_l * k / (n // pieces + 1)
                arc.append(impact + Vector((math.cos(a), math.sin(a))) *
                           (rad + rng.uniform(-0.0025, 0.0025)))
            glassr.add(arc, [f + i * 0.1 for i in range(len(arc))], 0.0012,
                       bri=rng.uniform(0.7, 1.2))

    # Letter fractures. Letters break in order of distance from the impact;
    # each is reached by a connector crack from the nearest crack already
    # there (the impact, or a letter that broke before it). Each glyph edge
    # is ONE crack line, only lightly jagged so the Pirata One silhouette
    # survives, and the glass inside the glyph is crazed and faintly lit so
    # every letter reads as a solid shape even at 350 px.
    known = [(impact, F0)]  # (point, frame it cracked)
    fill_loops = []         # (pts, revs) per glyph loop, for the crazed fill
    order = sorted(loops, key=lambda g: min((p - impact).length for p in g))
    for g in order:
        pts = resample(g, 0.0025)
        if len(pts) > 3 and (pts[-1] - pts[0]).length < 0.0012:
            pts = pts[:-1]
        n = len(pts)
        if n < 6:
            continue
        best = None
        for kp_, kr_ in known:
            i = min(range(0, n, 2), key=lambda i: (pts[i] - kp_).length)
            d_ = (pts[i] - kp_).length
            if best is None or d_ < best[0]:
                best = (d_, i, kp_, kr_)
        dist, i0, src, src_rev = best
        start = pts[i0]
        t_start = min(src_rev + 1.5 + dist / 0.03, 135.0)
        # arc length both ways from i0 -> reveal frame per point
        acc = [0.0] * n
        for direction in (1, -1):
            run = 0.0
            for k in range(1, n // 2 + 1):
                i = (i0 + direction * k) % n
                j = (i0 + direction * (k - 1)) % n
                run += (pts[i] - pts[j]).length
                if acc[i] == 0.0 or run < acc[i]:
                    acc[i] = run
        total = max(acc) or 1.0
        span = max(4.0, min(11.0, 146.0 - t_start))
        revs = [t_start + span * (a / total) ** 0.9 for a in acc]
        fill_loops.append((pts, revs))
        # one edge crack: kinks every 2-4 samples, jittered a fraction of
        # the stroke width, a closed line with only rare hairline breaks
        kinks = []
        i = 0
        while i < n:
            kinks.append(i)
            i += rng.randint(2, 4)
        kp = [pts[i] + loop_normal(pts, i) * rng.uniform(-0.0005, 0.0005) for i in kinks]
        kr = [revs[i] for i in kinks]
        m = len(kp)
        j = 0
        while j < m:
            L = rng.randint(10, 24)
            idx = [(j + q) % m for q in range(min(L, m) + 1)]
            word.add([kp[q] for q in idx], [kr[q] for q in idx],
                     rng.uniform(0.0013, 0.0017), taper=False,
                     bri=rng.uniform(0.85, 1.15))
            j += L + (1 if rng.random() < 0.12 else 0)
        # a few short spurs, outward only, off the letter edge
        for q in range(m):
            if rng.random() > 0.035:
                continue
            p = kp[q]
            nrm = loop_normal(pts, kinks[q])
            # pick the side that leaves the glyph
            if inside_loops(p + nrm * 0.002, loops):
                nrm = -nrm
            ang = math.atan2(nrm.y, nrm.x) + rng.uniform(-0.5, 0.5)
            ln = rng.uniform(0.003, 0.007)
            e = p + Vector((math.cos(ang), math.sin(ang))) * ln
            sp_pts = crack_line(p, e, rng, seg=0.0025, amp=0.0006)
            sr = [kr[q] + 0.8 + (x - p).length / 0.008 for x in sp_pts]
            word.add(sp_pts, sr, 0.0009, bri=rng.uniform(0.5, 0.8))
        # connector crack from the nearest earlier crack into this letter
        if dist > 0.006:
            cp = crack_line(src, start, rng, seg=0.006, amp=0.0025)
            nc = max(1, len(cp) - 1)
            c_revs = [src_rev + (t_start - src_rev) * (i / nc) for i in range(len(cp))]
            glassr.add(cp, c_revs, 0.0011, bri=0.8)
        known += [(pts[i], revs[i]) for i in range(0, n, 6)]

    # Crazed fill: the glass inside every glyph, triangulated with its holes,
    # each vertex revealed with the edge crack it sits on.
    from mathutils.geometry import tessellate_polygon
    # One glyph at a time (outer loop plus the holes inside it): scanfill
    # over the whole word bridges the word space. Triangles whose centre is
    # not inside the glyph are dropped as a guard.
    def contains(outer, q):
        return inside_loops(q, [outer])
    groups = []
    for k, (pts, revs) in enumerate(fill_loops):
        host = [h for h, (op, _) in enumerate(fill_loops)
                if h != k and contains(op, pts[0])]
        if not host:
            groups.append([k])
    for k, (pts, revs) in enumerate(fill_loops):
        for grp in groups:
            if k != grp[0] and contains(fill_loops[grp[0]][0], pts[0]):
                grp.append(k)
    tris = []
    flat, frev = [], []
    for grp in groups:
        base = len(flat)
        for k in grp:
            flat += fill_loops[k][0]
            frev += fill_loops[k][1]
        gl = [fill_loops[k][0] for k in grp]
        for a, b, c in tessellate_polygon([[p.to_3d() for p in q] for q in gl]):
            if inside_loops((flat[base + a] + flat[base + b] + flat[base + c]) / 3, gl):
                tris.append((base + a, base + b, base + c))
    for a, b, c in tris:
        # fill lights a beat after its edge
        shards.add_tri(flat[a], flat[b], flat[c], 0.0, 1.0)
        for k, vi in enumerate((a, b, c)):
            shards.rev[-3 + k] = frev[vi] + 2.0
    # keep the glow halo very faint and narrow: just a bloom at the edges
    for pts, revs in fill_loops:
        glow.add(pts + [pts[0]], revs + [revs[0]], 0.006, taper=False, bri=1.0)

    m_word = mat_reveal("M_CrackWord", BONE, 4.5, 16.0, speed=0.9)
    m_glow = mat_reveal("M_CrackGlow", BONE, 0.8, 1.0, width_alpha=True, alpha=0.12,
                        speed=0.25)
    # the web outside the letters stays dimmer than the word
    m_glass = mat_reveal("M_CrackGlass", (0.88, 0.9, 0.94, 1), 0.45, 5.0, speed=1.0)
    m_shard = mat_reveal("M_CrackFill", BONE, 0.5, 2.0, alpha=0.3, speed=0.3,
                         craze=160.0)
    word.build("Crack_Word", coll, m_word, glass, gw, 0.0016)
    glow.build("Crack_Glow", coll, m_glow, glass, gw, 0.0012)
    glassr.build("Crack_Glass", coll, m_glass, glass, gw, 0.0014)
    shards.build("Crack_Fill", coll, m_shard, glass, gw, 0.0010)

    # A light behind the glass so the wordmark lights its surroundings a touch.
    ld = bpy.data.lights.new("WordGlow", "AREA")
    ld.color = BONE[:3]
    ld.size, ld.shape = word_w, "RECTANGLE"
    ld.size_y = 0.2
    ld.energy = 0.0
    wl = bpy.data.objects.new("WordGlow", ld)
    link_obj(wl, coll)
    wl.parent = glass
    wl.location = (wc.x - gw / 2, -0.03, wc.y)
    wl.rotation_euler = (math.radians(-90), 0, 0)
    ld.use_shadow = False
    for f, e in ((120, 0.0), (126, 1.5), (150, 4.0), (216, 4.0)):
        key(ld, "energy", f, e, interp="LINEAR")
    return impact, wc, word_w


# ----------------------------------------------------------------- salt

def build_salt(coll, mouth_world, table_h):
    """Salt stream: points with per-grain emit frame, velocity, landing spot.

    Geometry nodes do the ballistic flight per frame; the grain count is
    constant (unborn grains are scaled to zero) so motion blur works.
    """
    rng = random.Random(86)
    N = 6000
    f0, f1 = 87.0, 110.0
    g = 9.81
    verts, emit, vel, land, tl = [], [], [], [], []
    for i in range(N):
        u = i / N
        # thinning stream: denser early, trickle at the end
        e = f0 + (f1 - f0) * (u ** 1.35) + rng.uniform(0, 0.8)
        p0 = mouth_world + Vector((rng.gauss(0, 0.002), rng.gauss(0, 0.002), rng.gauss(0, 0.001)))
        v = Vector((-0.12 + rng.gauss(0, 0.035), rng.gauss(0, 0.015), rng.uniform(-0.08, 0.02)))
        # time to fall to the floor
        h = p0.z
        t = (v.z + math.sqrt(v.z * v.z + 2 * g * h)) / g
        lp = p0 + v * t + Vector((0, 0, -0.5 * g * t * t))
        # pile: scatter on landing, heap grows over time
        r = abs(rng.gauss(0, 0.022))
        a = rng.uniform(0, 2 * math.pi)
        lp = Vector((lp.x + math.cos(a) * r, lp.y + math.sin(a) * r * 0.8,
                     0.002 + max(0.0, 0.022 * (1 - r / 0.04)) * (0.3 + 0.7 * u)))
        verts.append(tuple(p0))
        emit.append(e)
        vel.append(tuple(v))
        land.append(tuple(lp))
        tl.append(t)
    me = bpy.data.meshes.new("SaltPts")
    me.from_pydata(verts, [], [])
    for name, typ, data in (("emit", "FLOAT", emit), ("tland", "FLOAT", tl)):
        at = me.attributes.new(name, typ, "POINT")
        at.data.foreach_set("value", data)
    for name, data in (("vel", vel), ("land", land)):
        at = me.attributes.new(name, "FLOAT_VECTOR", "POINT")
        flat = [c for v in data for c in v]
        at.data.foreach_set("vector", flat)
    ob = bpy.data.objects.new("Salt", me)
    link_obj(ob, coll)
    salt_m = mat_simple("M_SaltGrain", (0.95, 0.94, 0.9, 1), 0.3,
                        emit=(1, 0.9, 0.78, 1), estr=0.22)

    ng = bpy.data.node_groups.new("SaltStream", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N_ = ng.nodes
    Lk = ng.links
    gin = N_.new("NodeGroupInput")
    gout = N_.new("NodeGroupOutput")

    def named(name, dtype):
        nd = N_.new("GeometryNodeInputNamedAttribute")
        nd.data_type = dtype
        nd.inputs["Name"].default_value = name
        return nd.outputs["Attribute"]

    def m(op, a, b=None):
        nd = N_.new("ShaderNodeMath")
        nd.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                nd.inputs[i].default_value = v
            else:
                Lk.new(v, nd.inputs[i])
        return nd.outputs[0]

    def vm(op, a, b=None, scale=None):
        nd = N_.new("ShaderNodeVectorMath")
        nd.operation = op
        if a is not None:
            Lk.new(a, nd.inputs[0])
        if b is not None:
            if isinstance(b, (tuple, list)):
                nd.inputs[1].default_value = b
            else:
                Lk.new(b, nd.inputs[1])
        if scale is not None:
            Lk.new(scale, nd.inputs["Scale"])
        return nd.outputs["Vector"]

    st = N_.new("GeometryNodeInputSceneTime")
    pos = N_.new("GeometryNodeInputPosition").outputs[0]
    age = m("DIVIDE", m("SUBTRACT", st.outputs["Frame"], named("emit", "FLOAT")), float(FPS))
    tland = named("tland", "FLOAT")
    a = m("MINIMUM", m("MAXIMUM", age, 0.0), tland)
    flight = vm("ADD", pos, vm("SCALE", named("vel", "FLOAT_VECTOR"), scale=a))
    grav = m("MULTIPLY", m("MULTIPLY", a, a), -0.5 * g)
    comb = N_.new("ShaderNodeCombineXYZ")
    Lk.new(grav, comb.inputs["Z"])
    flight = vm("ADD", flight, comb.outputs[0])
    landed = m("GREATER_THAN", age, tland)
    mix = N_.new("ShaderNodeMix")
    mix.data_type = "VECTOR"
    Lk.new(landed, mix.inputs["Factor"])
    Lk.new(flight, mix.inputs[4])
    Lk.new(named("land", "FLOAT_VECTOR"), mix.inputs[5])
    setp = N_.new("GeometryNodeSetPosition")
    Lk.new(gin.outputs[0], setp.inputs["Geometry"])
    Lk.new(mix.outputs[1], setp.inputs["Position"])
    born = m("GREATER_THAN", age, 0.0)
    ico = N_.new("GeometryNodeMeshIcoSphere")
    ico.inputs["Radius"].default_value = 0.0034
    ico.inputs["Subdivisions"].default_value = 1
    inst = N_.new("GeometryNodeInstanceOnPoints")
    Lk.new(setp.outputs[0], inst.inputs["Points"])
    Lk.new(ico.outputs["Mesh"], inst.inputs["Instance"])
    rv = N_.new("FunctionNodeRandomValue")
    rv.data_type = "FLOAT"
    rv.inputs["Min"].default_value = 0.5
    rv.inputs["Max"].default_value = 1.3
    Lk.new(m("MULTIPLY", born, rv.outputs[0]), inst.inputs["Scale"])
    real = N_.new("GeometryNodeRealizeInstances")
    Lk.new(inst.outputs[0], real.inputs[0])
    sm = N_.new("GeometryNodeSetMaterial")
    sm.inputs["Material"].default_value = salt_m
    Lk.new(real.outputs[0], sm.inputs["Geometry"])
    Lk.new(sm.outputs[0], gout.inputs[0])
    mod = ob.modifiers.new("SaltStream", "NODES")
    mod.node_group = ng
    return ob


# ----------------------------------------------------------------- characters

# Raven: one straight, unhurried walk from frame left, under the ladder, to
# front-right of the mirror. Steps every 6 frames from f16.
RAVEN_START = (14, (-1.62, 1.0))
RAVEN_END = (140, (1.4, 0.15))
CAT_RUN = (128, 146, (2.4, 0.0), (-1.7, 0.0))


def mat_feather():
    m, t, p = new_mat("M_RavenFeather")
    set_in(p, "Base Color", (0.012, 0.012, 0.016, 1))
    set_in(p, "Roughness", 0.32)
    set_in(p, "Coat Weight", 0.4)
    set_in(p, "Coat Roughness", 0.18)
    return m


def build_raven_proxy(coll):
    """Stand-in raven: forward -X at rest, origin at the feet, ~0.35 m tall."""
    feather = mat_feather()
    beak_m = mat_simple("M_Beak", (0.02, 0.02, 0.02, 1), 0.25)
    bone_m = mat_simple("M_Badge", BONE, 0.4)
    root = empty("RAVEN_ROOT", (0, 0, 0), coll, size=0.2)
    body_e = empty("RAVEN_BODY", (0, 0, 0.0), coll, parent=root, size=0.1)
    body = prim("uv_sphere", "Raven_Body", coll, feather, segments=24, ring_count=14, radius=0.1)
    body.scale = (1.3, 0.75, 0.85)
    body.location = (0.0, 0, 0.16)
    body.rotation_euler = (0, math.radians(-22), 0)
    body.parent = body_e
    head = empty("RAVEN_HEAD", (-0.1, 0, 0.27), coll, parent=body_e, size=0.06)
    hm = prim("uv_sphere", "Raven_HeadMesh", coll, feather, segments=20, ring_count=12,
              radius=0.052)
    hm.parent = head
    beak = prim("cone", "Raven_Beak", coll, beak_m, vertices=12, radius1=0.022, radius2=0.0,
                depth=0.08)
    beak.rotation_euler = (0, math.radians(-90), 0)
    beak.location = (-0.07, 0, -0.008)
    beak.parent = head
    badge = prim("cylinder", "Raven_Badge", coll, bone_m, vertices=16, radius=0.016, depth=0.005)
    badge.rotation_euler = (0, math.radians(90), math.radians(10))
    badge.location = (-0.115, -0.03, 0.17)
    badge.parent = body_e
    tail = empty("RAVEN_TAIL", (0.1, 0, 0.13), coll, parent=body_e, size=0.05)
    tm = box("Raven_TailMesh", (0.15, 0.07, 0.012), (0.07, 0, 0), coll, feather)
    tm.parent = tail
    umb = empty("RAVEN_UMBRELLA", (-0.12, 0, 0.27), coll, parent=head, size=0.05)
    shaft = prim("cylinder", "Umb_Shaft", coll, beak_m, vertices=8, radius=0.004, depth=0.34)
    shaft.location = (0, 0, 0.12)
    shaft.parent = umb
    canopy = prim("cone", "RAVEN_UMBRELLA_CANOPY", coll,
                  mat_simple("M_Umbrella", (0.01, 0.01, 0.012, 1), 0.45),
                  vertices=8, radius1=0.12, radius2=0.0, depth=0.1, smooth=False)
    canopy.location = (0, 0, 0.26)
    canopy.parent = umb
    canopy.scale = (0.12, 0.12, 2.2)
    return root


def build_cat_proxy(coll):
    """Stand-in cat: forward -X, origin at the feet, ~0.25 m at the shoulder."""
    fur = mat_simple("M_CatFur", (0.008, 0.008, 0.009, 1), 0.55)
    root = empty("CAT_ROOT", (0, 0, 0), coll, size=0.2)
    body = prim("uv_sphere", "Cat_Body", coll, fur, segments=20, ring_count=12, radius=0.1)
    body.scale = (2.3, 0.75, 0.75)
    body.location = (0, 0, 0.2)
    body.parent = root
    head = prim("uv_sphere", "Cat_Head", coll, fur, segments=16, ring_count=10, radius=0.06)
    head.location = (-0.25, 0, 0.27)
    head.parent = root
    tail = prim("cylinder", "Cat_Tail", coll, fur, vertices=8, radius=0.014, depth=0.32)
    tail.location = (0.34, 0, 0.28)
    tail.rotation_euler = (0, math.radians(70), 0)
    tail.parent = root
    return root


class ProxyRaven:
    """Keys the proxy raven with the same verbs as RigRaven."""

    def __init__(self, root):
        self.root = root
        self.body = bpy.data.objects["RAVEN_BODY"]
        self.head = bpy.data.objects["RAVEN_HEAD"]
        self.tail = bpy.data.objects["RAVEN_TAIL"]

    def walk(self, f0, f1, a, b, step_frames, first_step):
        yaw = math.atan2(-(b[1] - a[1]), -(b[0] - a[0]))
        for f in range(f0 - 1, f1 + 1):
            t = min(1.0, max(0.0, (f - f0) / float(f1 - f0)))
            key(self.root, "location", f, (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, 0))
            key(self.root, "rotation_euler", f, (0, 0, yaw))
        for s in range(first_step, f1, step_frames):
            for df, z in ((0, 0.0), (3, 0.012)):
                key(self.body, "location", s + df, (0, 0, z))
        return list(range(first_step, f1, step_frames))

    def tail_flick(self, f):
        key(self.tail, "rotation_euler", f - 3, (0, 0, 0))
        key(self.tail, "rotation_euler", f, (0, math.radians(-30), math.radians(35)))
        key(self.tail, "rotation_euler", f + 5, (0, 0, 0))

    def head_turn(self, f0, f1, cam_pos):
        key(self.head, "rotation_euler", f0, (0, 0, 0))
        key(self.head, "rotation_euler", f1, (0, 0, math.radians(80)))

    def umbrella(self, f):
        c = bpy.data.objects["RAVEN_UMBRELLA_CANOPY"]
        key(c, "scale", f - 2, (0.12, 0.12, 2.2))
        key(c, "scale", f + 1, (1.1, 1.1, 0.85))
        key(c, "scale", f + 3, (1, 1, 1))


class ProxyCat:
    def __init__(self, root):
        self.root = root

    def run(self, f0, f1, a, b):
        for f in range(f0 - 1, f1 + 2):
            t = (f - f0) / float(f1 - f0)
            ph = (f - f0) / 6.0
            z = 0.035 * (0.5 - 0.5 * math.cos(2 * math.pi * ph))
            key(self.root, "location", f, (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, z),
                interp="LINEAR")


UMB_SCALE = 1.9  # open umbrella about 0.47 m across, over the head


class RigRaven:
    """The real raven from characters.blend, keyed through rigs.py."""

    def __init__(self, root, rigs):
        self.root, self.rigs = root, rigs

    def walk(self, f0, f1, a, b, step_frames, first_step):
        self.root.location = (a[0], a[1], 0.0)
        return self.rigs.key_raven_walk(self.root, f0, f1, a, b, step_frames=step_frames,
                                        first_step=first_step)

    def tail_flick(self, f):
        # sideways toward the camera (the raven's right), the leg is there
        self.rigs.key_tail_flick(self.root, f, angle_deg=40.0, axis="yaw", frames=8)

    def head_turn(self, f0, f1, cam_pos):
        yaw = self.rigs.yaw_to_face(self.root, f1, cam_pos)
        self.rigs.key_head_turn(self.root, f0, f1, yaw, pitch_deg=4.0)

    def umbrella(self, f):
        """Hidden for the walk (closed in the beak it read as ears). It is
        produced at f-1, grows to full size and pops open at f, held up over
        the raven's head on the beak grip."""
        rigs = self.rigs
        rigs.key_umbrella_visible(self.root, 1, False)
        rigs.key_umbrella_visible(self.root, f - 1, True)
        pb = rigs.raven_rig(self.root).pose.bones["umbrella"]
        for ff, sc in ((f - 1, 0.55), (f, UMB_SCALE * 1.06), (f + 2, UMB_SCALE)):
            pb.scale = (sc, sc, sc)
            pb.keyframe_insert("scale", frame=ff)
        # rigs: closed at frame, 0.8 at +2, overshoot 1.08 at +3 -> pop at f
        rigs.key_umbrella_open(self.root, f - 3, frames=5)


class RigCat:
    def __init__(self, root, rigs):
        self.root, self.rigs = root, rigs

    def run(self, f0, f1, a, b):
        self.root.location = (a[0], a[1], 0.0)
        self.rigs.key_cat_bound(self.root, f0, f1, a, b, stride_frames=6)


def make_rig_adapters(coll, use_proxies):
    """Real characters from characters.blend + rigs.py, else proxies."""
    path = os.path.join(HERE, "characters.blend")
    if not use_proxies and os.path.exists(path) and os.path.exists(os.path.join(HERE, "rigs.py")):
        sys.path.insert(0, HERE)
        import rigs
        roots = rigs.append_characters(path)
        if "raven" in roots and "cat" in roots:
            for c in [c for c in bpy.context.scene.collection.children if c.name in ("RAVEN", "CAT")]:
                bpy.context.scene.collection.children.unlink(c)
                coll.children.link(c)
            return RigRaven(roots["raven"], rigs), RigCat(roots["cat"], rigs), True
        print("[ident] characters.blend incomplete, using proxies")
    return ProxyRaven(build_raven_proxy(coll)), ProxyCat(build_cat_proxy(coll)), False



# ----------------------------------------------------------------- camera, overlay

CAM = {"x": 0.5, "y0": -2.55, "y1": -2.25, "z": 0.72, "lens": 32.0, "tilt": -3.0}


def build_camera(coll):
    cd = bpy.data.cameras.new("Camera")
    cd.lens = CAM["lens"]
    cd.sensor_width = 36.0
    cd.clip_start = 0.05
    cd.clip_end = 40.0
    cam = bpy.data.objects.new("Camera", cd)
    link_obj(cam, coll)
    cam.rotation_euler = (math.radians(90 + CAM["tilt"]), 0, 0)
    # slow push-in over the whole shot, gentle ease
    for f, y in ((1, CAM["y0"]), (216, CAM["y1"])):
        key(cam, "location", f, (CAM["x"], y, CAM["z"]), interp="BEZIER")
    bpy.context.scene.camera = cam
    # No depth of field: the end card is camera-locked and must stay sharp.
    cd.dof.use_dof = False
    return cam


def cam_plane_size(cam, dist):
    sc = bpy.context.scene
    w = dist * cam.data.sensor_width / cam.data.lens
    h = w * sc.render.resolution_y / sc.render.resolution_x
    return w, h


def build_overlay(coll, cam):
    """Camera-locked black plane: fade up f1-24, vignette tighten f204-216."""
    d = 0.2
    w, h = cam_plane_size(cam, d)
    ob = mesh_obj("Overlay", [(-w, -h, -d), (w, -h, -d), (w, h, -d), (-w, h, -d)],
                  [(0, 1, 2, 3)], coll)
    me = ob.data
    uvl = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uvl.data[li].uv = ((co.x / w + 1) / 2, (co.y / h + 1) / 2)
    ob.parent = cam
    ob.visible_shadow = False
    m = bpy.data.materials.new("M_Overlay")
    m.use_nodes = True
    m.surface_render_method = "DITHERED"
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    t = NT(m)
    out = t.n("ShaderNodeOutputMaterial")
    uv = t.n("ShaderNodeUVMap")
    sep = t.n("ShaderNodeSeparateXYZ")
    t.l(uv.outputs["UV"], sep.inputs["Vector"])
    # elliptical radius, aspect corrected
    dx = t.math("MULTIPLY", t.math("SUBTRACT", sep.outputs["X"], 0.5), 2.0 * 16 / 9)
    dy = t.math("MULTIPLY", t.math("SUBTRACT", sep.outputs["Y"], 0.5), 2.0)
    r = t.math("SQRT", t.math("ADD", t.math("MULTIPLY", dx, dx), t.math("MULTIPLY", dy, dy)))
    vig_in = t.n("ShaderNodeValue")
    vig_in.name = "VIG_START"
    key_socket(vig_in.outputs[0], 1, 1.55)
    key_socket(vig_in.outputs[0], 204, 1.55)
    key_socket(vig_in.outputs[0], 216, 1.2)
    vig = t.math("POWER", t.math("MAXIMUM", t.math("SUBTRACT", r, vig_in.outputs[0]), 0.0), 1.0)
    vig = t.math("MULTIPLY", vig, 0.55, clamp=True)
    fade = t.n("ShaderNodeValue")
    fade.name = "FADE"
    key_socket(fade.outputs[0], 1, 1.0, "LINEAR")
    key_socket(fade.outputs[0], 2, 1.0, "BEZIER")
    key_socket(fade.outputs[0], 24, 0.0, "BEZIER")
    a = t.math("MAXIMUM", vig, fade.outputs[0], clamp=True)
    tr = t.n("ShaderNodeBsdfTransparent")
    em = t.n("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0, 0, 0, 1)
    mix = t.n("ShaderNodeMixShader")
    t.l(a, mix.inputs["Fac"])
    t.l(tr.outputs[0], mix.inputs[1])
    t.l(em.outputs[0], mix.inputs[2])
    t.l(mix.outputs[0], out.inputs["Surface"])
    me.materials.append(m)
    return ob


def ensure_font():
    ttf = os.path.join(OUT, "fonts", "spectral-300.ttf")
    if not os.path.exists(ttf):
        os.makedirs(os.path.dirname(ttf), exist_ok=True)
        src = os.path.join(REPO, "public", "kit", "v1", "fonts", "spectral-latin-300-normal.woff2")
        subprocess.run(["uv", "run", "--with", "fonttools", "--with", "brotli", "python",
                        os.path.join(HERE, "woff2ttf.py"), src, ttf], check=True)
    return bpy.data.fonts.load(ttf)


def build_card(coll, cam, glass):
    """End card under the mirror: camera-locked text, fades in f176-196."""
    font = ensure_font()
    cu = bpy.data.curves.new("CardText", "FONT")
    cu.body = "A Bad Omen project."
    cu.font = font
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    d = 1.0
    w, h = cam_plane_size(cam, d)
    cu.size = h * 0.06
    ob = bpy.data.objects.new("CardText", cu)
    link_obj(ob, coll)
    # place under the mirror's screen position at the poster frame
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene
    sc.frame_set(200)
    gw, gh = MIRROR["gw"], MIRROR["gh"]
    bottom = glass.matrix_world @ Vector((0, 0, 0))
    sx = world_to_camera_view(sc, cam, bottom).x
    ob.parent = cam
    ob.location = ((sx - 0.5) * w, -h * 0.385, -d)
    # keep the card clear of the raven (and its umbrella) on the poster frame
    rav = [o for o in bpy.data.objects
           if o.type == "MESH" and (o.name.startswith("RAVEN") or o.name.startswith("Raven"))]
    dg = bpy.context.evaluated_depsgraph_get()

    def screen_x(objs):
        xs = []
        for o in objs:
            if o.hide_render:
                continue
            e = o.evaluated_get(dg)
            xs += [world_to_camera_view(sc, cam, e.matrix_world @ Vector(v)).x
                   for v in e.bound_box]
        return (min(xs), max(xs)) if xs else None
    rx = screen_x(rav)
    cx = screen_x([ob])
    if rx and cx and cx[1] > rx[0] - 0.025:
        ob.location.x -= (cx[1] - (rx[0] - 0.025)) * w
    sc.frame_set(1)
    mat, _ = mat_fade_emit("M_Card", BONE, [(176, 0.0), (196, 1.0), (216, 1.0)], strength=1.0)
    cu.materials.append(mat)
    ob.visible_shadow = False
    return ob


# ----------------------------------------------------------------- animation

def animate(rig_raven, rig_cat, ladder_root, ladder_parts, table_root, shaker_root,
            mirror_body, bulb_light, bulb_obj):
    sc = bpy.context.scene

    # Bulb flicker f6-10 then steady.
    E = bulb_light.data.energy
    em = bulb_obj.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    for f, k in ((1, 1.0), (5, 1.0), (6, 0.15), (7, 0.9), (8, 0.05), (9, 0.6), (10, 1.0)):
        key(bulb_light.data, "energy", f, E * k, interp="CONSTANT")
        key_socket(em, f, 60.0 * k, "CONSTANT")

    # Raven walk f14-146, steps every 6 frames from 16.
    (f0, a), (f1, b) = RAVEN_START, RAVEN_END
    contacts = rig_raven.walk(f0, f1, a, b, 6, 16)
    print("[ident] raven contacts: %s" % contacts)
    rig_raven.tail_flick(60)
    cam = sc.camera
    sc.frame_set(158)
    cam_pos = cam.matrix_world.translation.copy()
    sc.frame_set(1)
    rig_raven.head_turn(150, 158, cam_pos)
    rig_raven.umbrella(162)

    # Ladder: wobble f62-70, tip right f70-82, hit table at 82, small rebound.
    theta_hit = ladder_hit_angle(ladder_root, table_root)
    lr = ladder_root
    seq = [
        (61, 0.0, "BEZIER"), (64, 1.2, "BEZIER"), (67, -0.6, "BEZIER"), (70, 1.8, "BEZIER"),
    ]
    for f, deg, it in seq:
        key(lr, "rotation_euler", f, (0, math.radians(deg), 0), interp=it)
    # accelerating fall: hand-placed keys on t^2
    for i in range(1, 13):
        f = 70 + i
        frac = (i / 12.0) ** 2.1
        key(lr, "rotation_euler", f, (0, math.radians(1.8 + (theta_hit - 1.8) * frac), 0),
            interp="LINEAR")
    key(lr, "rotation_euler", 84, (0, math.radians(theta_hit - 2.2), 0), interp="BEZIER")
    key(lr, "rotation_euler", 86, (0, math.radians(theta_hit), 0), interp="BEZIER")
    key(lr, "rotation_euler", 88, (0, math.radians(theta_hit - 0.5), 0), interp="BEZIER")
    key(lr, "rotation_euler", 90, (0, math.radians(theta_hit), 0), interp="BEZIER")
    # the ladder top slides a touch along the wall as it falls
    key(lr, "location", 70, tuple(lr.location), interp="BEZIER")
    key(lr, "location", 82, tuple(Vector(lr.location) + Vector((0.03, -0.02, 0))), interp="BEZIER")

    # Table jolt at 82.
    T0 = Vector(table_root.location)
    for f, dx, rz, ry in ((81, 0, 0, 0), (83, 0.018, 2.0, 1.2), (86, 0.012, 1.2, -0.4),
                          (90, 0.014, 1.5, 0.0)):
        key(table_root, "location", f, tuple(T0 + Vector((dx, 0, 0))))
        key(table_root, "rotation_euler", f, (0, math.radians(ry), math.radians(rz)))

    # Shaker: topple right on its bottom edge (84-88), rolls/rocks (88-104).
    sr = shaker_root
    key(sr, "rotation_euler", 83, (0, 0, 0))
    for f, ry in ((84, 6), (85, 22), (86, 50), (87, 80), (88, 94), (89, 87), (90, 91)):
        key(sr, "rotation_euler", f, (0, -math.radians(ry), 0))
    # rolling: rotate about its own long axis while rocking back and forth
    S = SHAKER
    p0 = Vector(sr.location)
    for f, roll, dy in ((90, 0, 0.0), (94, 140, -0.012), (98, 230, -0.019), (102, 205, -0.017),
                        (106, 222, -0.018), (112, 215, -0.0178)):
        key(sr, "rotation_euler", f, (math.radians(roll), -math.radians(91), 0))
        key(sr, "location", f, tuple(p0 + Vector((0, dy, 0))))
    key(sr, "location", 89, tuple(p0))

    # Mirror rock: forward 88-96, back 100 (thud), forward 100-111, catch,
    # slam back upright at 118, tiny settle.
    mb = mirror_body
    for f, deg in ((87, 0.0), (92, 5.5), (96, 8.0), (100, 0.0), (106, 11.5), (111, 13.0),
                   (113, 12.6)):
        key(mb, "rotation_euler", f, (math.radians(deg), 0, 0))
    # fall back: accelerate into the slam
    for i in range(1, 6):
        f = 113 + i
        frac = (i / 5.0) ** 2.2
        key(mb, "rotation_euler", f, (math.radians(12.6 * (1 - frac)), 0, 0), interp="LINEAR")
    for f, deg in ((119, -1.1), (121, 0.35), (123, 0.0)):
        key(mb, "rotation_euler", f, (math.radians(deg), 0, 0))

    # Cat bolts across the foreground, right to left, 128-146.
    rig_cat.run(*CAT_RUN)


def ladder_hit_angle(ladder_root, table_root):
    """Angle (deg) about Y where the ladder first touches the table top."""
    sc = bpy.context.scene
    T = TABLE
    top_z = T["h"]
    tx0, tx1 = T["x"] - T["w"] / 2, T["x"] + T["w"] / 2
    ty0, ty1 = T["y"] - T["d"] / 2, T["y"] + T["d"] / 2
    rails = [o for o in bpy.data.objects if o.name.startswith("Ladder_Rail")]
    hit = 75.0
    for deg10 in range(0, 900):
        deg = deg10 / 10.0
        ladder_root.rotation_euler = (0, math.radians(deg), 0)
        bpy.context.view_layer.update()
        touched = False
        for r in rails:
            vs = [v.co for v in r.data.vertices]
            lo = [c for c in vs if c.z < 0]
            hi = [c for c in vs if c.z > 0]
            samples = [a.lerp(b, k / 60.0) for a, b in zip(lo, hi) for k in range(61)]
            for c in samples:
                w = r.matrix_world @ c
                if tx0 <= w.x <= tx1 and ty0 - 0.05 <= w.y <= ty1 + 0.05 and w.z <= top_z + 0.012:
                    touched = True
                    break
            if touched:
                break
        if touched:
            hit = deg
            break
    ladder_root.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()
    print("[ident] ladder hits table at %.1f deg" % hit)
    return hit


# ----------------------------------------------------------------- render setup

def setup_render(preview):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = F_START, F_END
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    sc.render.resolution_percentage = 50 if preview else 100
    e = sc.eevee
    e.taa_render_samples = 24 if preview else 96
    e.use_raytracing = True
    e.ray_tracing_method = "SCREEN"
    try:
        e.ray_tracing_options.resolution_scale = "2" if preview else "1"
        e.ray_tracing_options.trace_max_roughness = 0.4
    except Exception:
        pass
    e.use_shadows = True
    e.shadow_ray_count = 2
    e.shadow_step_count = 8
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    e.motion_blur_steps = 1 if preview else 3
    try:
        e.fast_gi_method = "GLOBAL_ILLUMINATION"
    except Exception:
        pass
    e.use_volumetric_shadows = True
    e.volumetric_tile_size = "8" if preview else "4"
    sc.render.film_transparent = False
    vs = sc.view_settings
    vs.view_transform = "AgX"
    try:
        vs.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    vs.exposure = 0.0
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.color_depth = "8"
    # World: near black, faint cool so the dark has a hue.
    w = bpy.data.worlds.new("World")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.004, 0.0045, 0.006, 1)
    bg.inputs["Strength"].default_value = 1.0
    # Thin haze so the bulb has air around it.
    vol = w.node_tree.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = 0.012
    vol.inputs["Anisotropy"].default_value = 0.35
    w.node_tree.links.new(vol.outputs[0], w.node_tree.nodes["World Output"].inputs["Volume"])
    setup_compositor(sc)


def setup_compositor(sc):
    """Soft glow on the bright bits (bulb, cracks)."""
    try:
        ng = bpy.data.node_groups.new("IdentComp", "CompositorNodeTree")
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        ng.interface.new_socket("Image", in_out="INPUT", socket_type="NodeSocketColor")
        rl = ng.nodes.new("CompositorNodeRLayers")
        gl = ng.nodes.new("CompositorNodeGlare")
        out = ng.nodes.new("NodeGroupOutput")
        for k, v in (("glare_type", "FOG_GLOW"), ("quality", "HIGH")):
            try:
                setattr(gl, k, v)
            except Exception:
                pass
        for nm, v in (("Threshold", 1.0), ("Strength", 0.35), ("Size", 0.6)):
            try:
                gl.inputs[nm].default_value = v
            except Exception:
                pass
        try:
            gl.inputs["Type"].default_value = "Fog Glow"
        except Exception:
            pass
        ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
        ng.links.new(gl.outputs["Image"], out.inputs[0])
        sc.compositing_node_group = ng
        sc.render.use_compositing = True
    except Exception as exc:
        print("[ident] compositor glow skipped: %s" % exc)


# ----------------------------------------------------------------- main

def build(args):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = F_START, F_END
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080

    c_set = new_coll("Set")
    c_light = new_coll("Lights")
    c_fx = new_coll("FX")
    c_chars = new_coll("Characters")
    c_cam = new_coll("Camera")

    build_room(c_set)
    ladder_root, ladder_parts = build_ladder(c_set)
    table_root = build_table(c_set)
    shaker_root, mouth = build_shaker(c_set, table_root)
    mirror_root, mirror_body, glass = build_mirror(c_set)
    bulb_light, bulb_obj = build_bulb(c_light)
    build_lights(c_light)
    cam = build_camera(c_cam)
    build_cracks(c_fx, glass)
    rig_raven, rig_cat, real = make_rig_adapters(c_chars, args["proxies"])

    animate(rig_raven, rig_cat, ladder_root, ladder_parts, table_root, shaker_root,
            mirror_body, bulb_light, bulb_obj)

    # salt mouth position once the shaker has settled on its side (f90)
    sc.frame_set(96)
    mouth_w = mouth.matrix_world.translation.copy()
    sc.frame_set(1)
    build_salt(c_fx, mouth_w, TABLE["h"])

    build_overlay(c_cam, cam)
    build_card(c_cam, cam, glass)
    # The plane probe sits on the glass: keep the glass, its cracks and the
    # mirror back out of its capture, and the camera-locked overlay/card out
    # of every probe.
    for ob in [glass] + list(glass.children_recursive) + [bpy.data.objects["Mirror_Back"]]:
        ob.hide_probe_plane = True
    for ob in c_cam.objects:
        ob.hide_probe_plane = ob.hide_probe_sphere = ob.hide_probe_volume = True
    setup_render(args["preview"])
    sc.frame_set(1)
    path = os.path.join(HERE, "ident.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    print("[ident] saved %s (real characters: %s)" % (path, real))
    return real


def render(args):
    sc = bpy.context.scene
    os.makedirs(args["out"], exist_ok=True)
    if args["list"]:
        frames = args["list"]
    elif args["frames"]:
        frames = list(range(args["frames"][0], args["frames"][1] + 1))
    else:
        frames = list(range(F_START, F_END + 1))
    times = []
    for f in frames:
        sc.frame_set(f)
        sc.render.filepath = os.path.join(args["out"], "frame_%04d.png" % f)
        t = time.time()
        bpy.ops.render.render(write_still=True)
        times.append(time.time() - t)
        print("[ident] frame %d %.2fs" % (f, times[-1]), flush=True)
    if times:
        print("[ident] rendered %d frames, mean %.2fs, max %.2fs" %
              (len(times), sum(times) / len(times), max(times)))


def main():
    args = parse_args()
    build(args)
    if args["render"]:
        render(args)


if __name__ == "__main__":
    main()
