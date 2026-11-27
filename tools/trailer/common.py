"""Shared Blender helpers for the Cake-Pop Demon Hunters trailer (BAD-857).

Same look as the bad.llc ident (tools/ident/scene.py): EEVEE with screen-space
raytracing, AgX Medium High Contrast, a thin haze with a fog glow on the bright
bits, one warm practical key and a cool rim, mostly dark. World units are
metres; X right, Y away from camera, Z up; a hero is about 0.95 m tall.
"""

import math
import os
import random

import bpy
from mathutils import Euler, Vector

FPS = 24
WARM = (1.0, 0.58, 0.28)
COOL = (0.55, 0.7, 1.0)
HELL = (1.0, 0.22, 0.05)


# ------------------------------------------------------------ scene

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    return sc


def look(frames, preview=False, haze=0.012, world=(0.004, 0.0045, 0.006), glare=0.35,
         exposure=0.0, samples=None, aniso=0.35):
    """The ident's render look. frames = (first, last)."""
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.frame_start, sc.frame_end = frames
    sc.render.resolution_percentage = 50 if preview else 100
    e = sc.eevee
    e.taa_render_samples = samples or (16 if preview else 64)
    e.use_raytracing = True
    e.ray_tracing_method = "SCREEN"
    try:
        e.ray_tracing_options.resolution_scale = "2" if preview else "1"
        e.ray_tracing_options.trace_max_roughness = 0.4
    except Exception:
        pass
    e.use_shadows = True
    try:
        e.shadow_pool_size = "4096"
    except Exception:
        pass
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
    vs.exposure = exposure
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.color_depth = "8"
    w = bpy.data.worlds.new("World")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (world[0], world[1], world[2], 1)
    bg.inputs["Strength"].default_value = 1.0
    if haze > 0:
        vol = w.node_tree.nodes.new("ShaderNodeVolumePrincipled")
        vol.inputs["Density"].default_value = haze
        vol.inputs["Anisotropy"].default_value = aniso
        w.node_tree.links.new(vol.outputs[0], w.node_tree.nodes["World Output"].inputs["Volume"])
    glow(sc, glare)
    return sc


def glow(sc, strength=0.35):
    """Soft fog glow on the bright bits, as in the ident."""
    try:
        ng = bpy.data.node_groups.new("TrailerComp", "CompositorNodeTree")
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
        for nm, v in (("Threshold", 1.0), ("Strength", strength), ("Size", 0.6)):
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
        print("[trailer] glow skipped: %s" % exc)


# ------------------------------------------------------------ objects

def link(ob, coll=None):
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def empty(name, loc=(0, 0, 0), parent=None):
    ob = bpy.data.objects.new(name, None)
    link(ob)
    ob.location = loc
    if parent:
        ob.parent = parent
    return ob


def mesh_obj(name, verts, faces, mat=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    link(ob)
    if mat:
        me.materials.append(mat)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return ob


_proto = {}


def prim(kind, name, loc=(0, 0, 0), scale=(1, 1, 1), mat=None, parent=None, seg=24, rot=(0, 0, 0), smooth=True):
    """A primitive as its own object: sphere, cube, cyl, cone, plane."""
    key = (kind, seg)
    if key not in _proto:
        import bmesh
        bm = bmesh.new()
        if kind == "sphere":
            bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=max(8, seg // 2), radius=1.0)
        elif kind == "cube":
            bmesh.ops.create_cube(bm, size=2.0)
        elif kind == "cyl":
            bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=1.0, radius2=1.0, depth=2.0)
        elif kind == "cone":
            bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=1.0, radius2=0.0, depth=2.0)
        elif kind == "plane":
            bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.0)
        me = bpy.data.meshes.new("proto_%s_%d" % key)
        me.materials.append(None)
        bm.to_mesh(me)
        bm.free()
        if smooth and kind in ("sphere", "cyl", "cone"):
            for p in me.polygons:
                p.use_smooth = True
        _proto[key] = me
    ob = bpy.data.objects.new(name, _proto[key])
    link(ob)
    ob.location = loc
    ob.scale = scale
    ob.rotation_euler = rot
    if mat:
        ob.material_slots[0].link = "OBJECT"
        ob.material_slots[0].material = mat
    if parent:
        ob.parent = parent
    return ob


def tube(name, pts, radii, mat, ring=10, smooth=True):
    """A tapered tube along a polyline: horns, tails, fingers."""
    verts, faces = [], []
    n = len(pts)
    for i, p in enumerate(pts):
        p = Vector(p)
        t = (Vector(pts[min(i + 1, n - 1)]) - Vector(pts[max(i - 1, 0)])).normalized()
        a = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        u = t.cross(a).normalized()
        v = t.cross(u).normalized()
        for k in range(ring):
            th = 2 * math.pi * k / ring
            verts.append(p + (u * math.cos(th) + v * math.sin(th)) * radii[i])
    for i in range(n - 1):
        for k in range(ring):
            a, b = i * ring + k, i * ring + (k + 1) % ring
            faces.append((a, b, b + ring, a + ring))
    tip = len(verts)
    verts.append(Vector(pts[-1]) + (Vector(pts[-1]) - Vector(pts[-2])).normalized() * radii[-1] * 0.5)
    for k in range(ring):
        faces.append(((n - 1) * ring + k, (n - 1) * ring + (k + 1) % ring, tip))
    return mesh_obj(name, verts, faces, mat, smooth)


def bezier(p0, p1, p2, n=12):
    out = []
    for i in range(n):
        t = i / (n - 1)
        out.append(tuple((1 - t) ** 2 * a + 2 * (1 - t) * t * b + t * t * c for a, b, c in zip(p0, p1, p2)))
    return out


# ------------------------------------------------------------ materials

def mat(name, color, rough=0.5, metal=0.0, emit=None, estr=0.0, coat=0.0, sss=0.0, alpha=1.0,
        bump=0.0, bump_scale=60.0, spec=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    try:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.06
        b.inputs["Subsurface Weight"].default_value = sss
        b.inputs["Subsurface Radius"].default_value = (0.5, 0.25, 0.2)
        b.inputs["Specular IOR Level"].default_value = spec
    except Exception:
        pass
    if emit is not None:
        b.inputs["Emission Color"].default_value = (emit[0], emit[1], emit[2], 1)
        b.inputs["Emission Strength"].default_value = estr
    if alpha < 1.0:
        b.inputs["Alpha"].default_value = alpha
    if bump > 0:
        n = nt.nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = bump_scale
        n.inputs["Detail"].default_value = 6.0
        bp = nt.nodes.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = bump
        nt.links.new(n.outputs["Fac"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def lava_mat(name, base=(0.02, 0.012, 0.012), glow=(1.0, 0.25, 0.04), scale=2.0, strength=6.0, rough=0.7):
    """Charred rock with glowing cracks (voronoi edges)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (base[0], base[1], base[2], 1)
    b.inputs["Roughness"].default_value = rough
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale * 1.7
    nz.inputs["Detail"].default_value = 4.0
    vo = nt.nodes.new("ShaderNodeTexVoronoi")
    vo.feature = "DISTANCE_TO_EDGE"
    vo.inputs["Scale"].default_value = scale
    vo.inputs["Randomness"].default_value = 1.0
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "VECTOR"
    mix.inputs[0].default_value = 0.35
    nt.links.new(tc.outputs["Object"], mix.inputs[4])
    nt.links.new(nz.outputs["Color"], mix.inputs[5])
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    nt.links.new(mix.outputs[1], vo.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (1, 1, 1, 1)
    ramp.color_ramp.elements[1].position = 0.07
    ramp.color_ramp.elements[1].color = (0, 0, 0, 1)
    nt.links.new(vo.outputs["Distance"], ramp.inputs["Fac"])
    gc = nt.nodes.new("ShaderNodeMix")
    gc.data_type = "RGBA"
    gc.inputs[6].default_value = (0, 0, 0, 1)
    gc.inputs[7].default_value = (glow[0], glow[1], glow[2], 1)
    nt.links.new(ramp.outputs["Color"], gc.inputs[0])
    nt.links.new(gc.outputs[2], b.inputs["Emission Color"])
    sm = nt.nodes.new("ShaderNodeMath")
    sm.operation = "MULTIPLY"
    sm.inputs[1].default_value = strength
    nt.links.new(ramp.outputs["Color"], sm.inputs[0])
    nt.links.new(sm.outputs[0], b.inputs["Emission Strength"])
    return m


def volume_smoke(name, density=0.4, color=(0.05, 0.04, 0.04), scale=1.2, emit=0.0, ecolor=(1, 0.3, 0.05)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type not in ("OUTPUT_MATERIAL",):
            nt.nodes.remove(n)
    out = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"][0]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 5.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    mp = nt.nodes.new("ShaderNodeMapRange")
    mp.inputs["From Min"].default_value = 0.35
    mp.inputs["From Max"].default_value = 0.75
    mp.inputs["To Max"].default_value = density
    nt.links.new(nz.outputs["Fac"], mp.inputs["Value"])
    vp = nt.nodes.new("ShaderNodeVolumePrincipled")
    vp.inputs["Color"].default_value = (color[0], color[1], color[2], 1)
    vp.inputs["Anisotropy"].default_value = 0.3
    if emit > 0:
        vp.inputs["Emission Strength"].default_value = emit
        vp.inputs["Emission Color"].default_value = (ecolor[0], ecolor[1], ecolor[2], 1)
    nt.links.new(mp.outputs[0], vp.inputs["Density"])
    nt.links.new(vp.outputs[0], out.inputs["Volume"])
    return m


# ------------------------------------------------------------ lights & camera

def aim(ob, target):
    d = Vector(target) - Vector(ob.location)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def area(name, loc, target, energy, color=COOL, size=1.0, size_y=None):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.color = color
    if size_y:
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = size, size_y
    else:
        ld.size = size
    ob = link(bpy.data.objects.new(name, ld))
    ob.location = loc
    aim(ob, target)
    return ob


def spot(name, loc, target, energy, color=WARM, angle=40, blend=0.5, radius=0.05):
    ld = bpy.data.lights.new(name, "SPOT")
    ld.energy = energy
    ld.color = color
    ld.spot_size = math.radians(angle)
    ld.spot_blend = blend
    ld.shadow_soft_size = radius
    ob = link(bpy.data.objects.new(name, ld))
    ob.location = loc
    aim(ob, target)
    return ob


def point(name, loc, energy, color=WARM, radius=0.08, shadow=True):
    ld = bpy.data.lights.new(name, "POINT")
    ld.energy = energy
    ld.color = color
    ld.shadow_soft_size = radius
    ld.use_shadow = shadow
    ob = link(bpy.data.objects.new(name, ld))
    ob.location = loc
    return ob


def flicker(light, f0, f1, base, amp=0.3, step=2, seed=1):
    """Keyframed candle / fire flicker on a light's energy."""
    r = random.Random(seed)
    for f in range(f0, f1 + 1, step):
        light.data.energy = base * (1 + amp * (r.random() * 2 - 1))
        light.data.keyframe_insert("energy", frame=f)
    set_interp(light.data, "LINEAR")


class Cam:
    """A tracked camera with keyed moves. move([(frame, loc, target), ...])."""

    def __init__(self, lens=35, fstop=2.8, dof=True, name="Camera", shift=(0, 0)):
        cd = bpy.data.cameras.new(name)
        cd.lens = lens
        cd.sensor_width = 36.0
        cd.clip_start = 0.02
        cd.clip_end = 400.0
        cd.shift_x, cd.shift_y = shift
        self.ob = link(bpy.data.objects.new(name, cd))
        self.tgt = empty(name + "Target")
        c = self.ob.constraints.new("TRACK_TO")
        c.target = self.tgt
        c.track_axis = "TRACK_NEGATIVE_Z"
        c.up_axis = "UP_Y"
        cd.dof.use_dof = dof
        cd.dof.focus_object = self.tgt
        cd.dof.aperture_fstop = fstop
        bpy.context.scene.camera = self.ob

    def move(self, keys, interp="BEZIER"):
        for f, loc, tgt in keys:
            self.ob.location = loc
            self.tgt.location = tgt
            self.ob.keyframe_insert("location", frame=f)
            self.tgt.keyframe_insert("location", frame=f)
        set_interp(self.ob, interp)
        set_interp(self.tgt, interp)

    def cut(self, keys):
        self.move(keys, "CONSTANT")

    def shots(self, segs, interp="BEZIER"):
        """segs = [(f0, f1, loc0, tgt0, loc1, tgt1)]: each a little move, hard cut to the next."""
        ends = set()
        for f0, f1, l0, t0, l1, t1 in segs:
            for f, l, t in ((f0, l0, t0), (f1, l1, t1)):
                self.ob.location = l
                self.tgt.location = t
                self.ob.keyframe_insert("location", frame=f)
                self.tgt.keyframe_insert("location", frame=f)
            ends.add(f1)
        for o in (self.ob, self.tgt):
            for fc in _fcurves(o):
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT" if int(round(kp.co.x)) in ends else interp

    def roll(self, f, deg):
        self.ob.rotation_euler[1] = math.radians(deg)


def _fcurves(ob):
    ad = ob.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    try:
        return list(act.fcurves)
    except Exception:
        out = []
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    out += list(cb.fcurves)
        return out


def set_interp(ob, interp):
    for fc in _fcurves(ob):
        for kp in fc.keyframe_points:
            kp.interpolation = interp


def key(ob, prop, frame, value, interp=None, index=-1):
    setattr(ob, prop, value)
    ob.keyframe_insert(prop, frame=frame, index=index)
    if interp:
        set_interp(ob, interp) if False else None


def lin(ob):
    set_interp(ob, "LINEAR")


def ease(f, a, b):
    t = max(0.0, min(1.0, (f - a) / float(b - a)))
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------ fx

def ash(f0, f1, n=120, box=(-6, 6, -1, 8, 0, 6), seed=3, drift=(0.6, 0.2, -0.5), size=0.012,
        color=(0.9, 0.35, 0.1), glow=2.0, step=6):
    """Drifting ash and embers: n tiny specks, keyed straight lines."""
    r = random.Random(seed)
    m = mat("Ash", (0.05, 0.04, 0.04), 0.9, emit=color, estr=glow)
    cold = mat("AshCold", (0.06, 0.05, 0.05), 0.9)
    for i in range(n):
        p = Vector((r.uniform(box[0], box[1]), r.uniform(box[2], box[3]), r.uniform(box[4], box[5])))
        s = size * r.uniform(0.5, 1.8)
        ob = prim("sphere", "Ash%d" % i, p, (s, s, s * 0.4), m if r.random() < 0.3 else cold, seg=8)
        v = Vector(drift) * r.uniform(0.6, 1.4) + Vector((r.uniform(-.2, .2), r.uniform(-.2, .2), 0))
        ob.rotation_euler = (r.random() * 3, r.random() * 3, r.random() * 3)
        for f in range(f0, f1 + 1, step):
            ob.location = p + v * ((f - f0) / FPS) + Vector((math.sin(f * 0.07 + i) * 0.15, 0, math.cos(f * 0.05 + i) * 0.1))
            ob.keyframe_insert("location", frame=f)
        lin(ob)


def rain(f0, f1, n=260, box=(-5, 5, -2, 6, 0, 7), seed=11, length=0.55, speed=14.0, mat_=None, thick=0.004,
         slant=0.08):
    """Rain streaks falling at speed m/s, looping within the shot."""
    r = random.Random(seed)
    m = mat_ or mat("Rain", (0.6, 0.7, 0.85), 0.1, emit=(0.6, 0.7, 0.9), estr=0.8)
    height = box[5] - box[4]
    period = max(2, int(height / speed * FPS))
    for i in range(n):
        x, y = r.uniform(box[0], box[1]), r.uniform(box[2], box[3])
        z0 = r.uniform(box[4], box[5])
        ob = prim("cyl", "Rain%d" % i, (x, y, z0), (thick, thick, length / 2), m, seg=6)
        ob.rotation_euler = (0, slant, 0)
        # one keyed fall that wraps: key a few cycles
        f = f0
        z = z0
        while f <= f1:
            ob.location = (x + slant * (z0 - z), y, z)
            ob.keyframe_insert("location", frame=f)
            dt = int(max(1, min((z - box[4]) / speed * FPS, f1 - f))) if z > box[4] else 1
            f2 = f + dt
            z2 = z - speed * dt / FPS
            if z2 <= box[4] or f2 >= f1:
                ob.location = (x + slant * (z0 - z2), y, z2)
                ob.keyframe_insert("location", frame=min(f2, f1))
                if f2 >= f1:
                    break
                f = f2 + 1
                z = box[5]
                z0 = box[5]
                continue
            f, z = f2, z2
        lin(ob)


def floor(size=60, color=(0.02, 0.018, 0.018), rough=0.6, z=0.0, m=None):
    return prim("plane", "Floor", (0, 0, z), (size, size, 1), m or mat("Floor", color, rough), smooth=False)


def fire_mat(name, strength=5.0, scale=3.0):
    """Billowing fire: noise through a dark-red -> orange -> hot-yellow ramp, emitted."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"][0]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 8.0
    nz.inputs["Roughness"].default_value = 0.65
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].position = 0.35
    cr.elements[0].color = (0.25, 0.015, 0.0, 1)
    cr.elements[1].position = 0.72
    cr.elements[1].color = (1.0, 0.55, 0.08, 1)
    e = cr.elements.new(0.9)
    e.color = (1.0, 0.9, 0.5, 1)
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def explosion(f0, loc, size=4.0, dur=26, seed=5, strength=40):
    """A fireball: billowing noisy fire that blooms and fades, dark smoke, a flash light, debris."""
    r = random.Random(seed)
    core = fire_mat("FireCore%d" % seed, max(2.0, strength * 0.12), 2.2)
    smoke = mat("FireSmoke", (0.012, 0.01, 0.01), 0.95)
    parts = []
    for i in range(9):
        d = Vector((r.uniform(-1, 1), r.uniform(-.6, .6), r.uniform(0.1, 1.0))) * size * 0.3
        o = prim("sphere", "Fire%d" % i, loc + d, (0.01,) * 3, core if i < 6 else smoke, seg=24)
        o.rotation_euler = (r.random() * 6, r.random() * 6, r.random() * 6)
        parts.append((o, d))
    for o, d in parts:
        for f, s, p in ((f0 - 1, 0.01, 0.0), (f0 + 4, size * r.uniform(0.5, 0.8), 0.6), (f0 + dur, size * r.uniform(0.7, 1.1), 1.0), (f0 + dur + 16, 0.01, 1.2)):
            o.scale = (s, s, s)
            o.location = Vector(loc) + d * (1 + p * 1.6)
            o.keyframe_insert("scale", frame=f)
            o.keyframe_insert("location", frame=f)
    fl = point("FireFlash", Vector(loc) + Vector((0, -1, 1)), 0.0, (1, 0.55, 0.2), radius=0.6, shadow=False)
    for f, e in ((f0 - 1, 0), (f0 + 1, 40000), (f0 + 10, 12000), (f0 + dur + 20, 0)):
        fl.data.energy = e
        fl.data.keyframe_insert("energy", frame=f)
    # debris
    for i in range(34):
        s = r.uniform(0.04, 0.14)
        o = prim("cube", "Debris%d" % i, loc, (0.0,) * 3, mat("Debris%d" % i, (0.03, 0.025, 0.02), 0.8), seg=4)
        v = Vector((r.uniform(-1, 1), r.uniform(-0.7, 0.7), r.uniform(0.6, 1.4))) * r.uniform(3, 8)
        for k in range(0, 40, 3):
            t = k / FPS
            p = Vector(loc) + v * t + Vector((0, 0, -4.9 * t * t))
            p.z = max(p.z, s)
            o.location = p
            o.scale = (s, s, s) if k else (0.001,) * 3
            o.rotation_euler = (t * 7 * (i % 3 + 1), t * 5, t * 3)
            o.keyframe_insert("location", frame=f0 + k)
            o.keyframe_insert("scale", frame=f0 + k)
            o.keyframe_insert("rotation_euler", frame=f0 + k)
        lin(o)
    return fl


def sparks_text(*a, **k):
    pass


def sky(horizon=(1.0, 0.25, 0.06), zenith=(0.004, 0.003, 0.005), strength=1.0, power=0.5):
    """World gradient: a glow on the horizon fading to a dark sky."""
    w = bpy.context.scene.world
    nt = w.node_tree
    bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sp = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sp.inputs[0])
    mp = nt.nodes.new("ShaderNodeMapRange")
    mp.inputs["From Min"].default_value = 0.0
    mp.inputs["From Max"].default_value = 0.75
    mp.inputs["Value"].default_value = 0.0
    nt.links.new(sp.outputs["Z"], mp.inputs["Value"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (horizon[0], horizon[1], horizon[2], 1)
    ramp.color_ramp.elements[1].color = (zenith[0], zenith[1], zenith[2], 1)
    ramp.color_ramp.elements[1].position = 1.0
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = power
    nt.links.new(mp.outputs[0], pw.inputs[0])
    nt.links.new(pw.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength


def backdrop(dist=90, width=400, height=90, horizon=(1.0, 0.13, 0.025), strength=3.0, falloff=0.6):
    """A big emissive wall at the far end: hell glowing up from the horizon."""
    m = bpy.data.materials.new("Backdrop")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"][0]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sp = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sp.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (horizon[0], horizon[1], horizon[2], 1)
    ramp.color_ramp.elements[1].position = falloff
    ramp.color_ramp.elements[1].color = (0.01, 0.004, 0.006, 1)
    nt.links.new(sp.outputs["Y"], ramp.inputs["Fac"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    ob = prim("plane", "Backdrop", (0, dist, height / 2 - 2), (width / 2, height / 2, 1), m, rot=(math.pi / 2, 0, 0), smooth=False)
    ob.data = ob.data.copy() if False else ob.data
    return ob


def skyline(seed=1, y0=45, depth=50, width=120, n=46, fires=14, windows=True, flick=(1, 200), hmax=34):
    """A burning city in silhouette: dark towers, a few lit windows, fires."""
    r = random.Random(seed)
    dark = mat("Tower", (0.006, 0.005, 0.006), 0.9)
    win = mat("Window", (1, 0.6, 0.25), 0.5, emit=(1.0, 0.55, 0.2), estr=1.6)
    fire = mat("FireBlaze", (1, 0.4, 0.1), 0.5, emit=(1.0, 0.16, 0.025), estr=1.8)
    for i in range(n):
        x = r.uniform(-width / 2, width / 2)
        y = y0 + r.uniform(0, depth)
        w, h = r.uniform(3, 9), r.uniform(hmax * 0.2, hmax)
        prim("cube", "Tower%d" % i, (x, y, h / 2), (w / 2, w / 2, h / 2), dark, smooth=False)
        if windows:
            for k in range(r.randint(0, 6)):
                prim("cube", "Win", (x + r.uniform(-w / 2, w / 2), y - w / 2 - 0.05, r.uniform(2, h - 1)), (0.35, 0.05, 0.5), win, smooth=False)
    flames = []
    for i in range(fires):
        x = r.uniform(-width / 2, width / 2)
        y = y0 + r.uniform(-4, depth * 0.8)
        h = r.uniform(5, 14)
        f = prim("cone", "Blaze%d" % i, (x, y - 3, h * 0.5), (r.uniform(2, 4), r.uniform(2, 4), h * 0.5), fire, seg=7)
        for fr in range(flick[0], flick[1] + 1, 4):
            s = 1 + 0.18 * math.sin(fr * 0.4 + i) + 0.1 * r.random()
            f.scale = (f.scale[0], f.scale[1], h * 0.5 * s)
            f.keyframe_insert("scale", frame=fr)
        flames.append(f)
    return flames


def avenue(seed=2, y0=8, y1=90, half=9.0, hmax=28, fires=16, flick=(1, 200)):
    """A burning street: dark towers either side, fires on the roofs, lit windows."""
    r = random.Random(seed)
    dark = mat("Tower", (0.008, 0.006, 0.007), 0.85, bump=0.1, bump_scale=4)
    win = mat("Window", (1, 0.55, 0.2), 0.5, emit=(1.0, 0.5, 0.18), estr=1.4)
    fire = mat("FireBlaze", (1, 0.4, 0.1), 0.5, emit=(1.0, 0.16, 0.025), estr=1.8)
    y = y0
    i = 0
    while y < y1:
        for side in (-1, 1):
            w = r.uniform(6, 12)
            h = r.uniform(hmax * 0.25, hmax)
            x = side * (half + w / 2 + r.uniform(0, 3))
            prim("cube", "AveT%d" % i, (x, y + w / 2, h / 2), (w / 2, w / 2, h / 2), dark, smooth=False)
            for k in range(r.randint(2, 8)):
                zz = r.uniform(2, h - 1)
                prim("cube", "AveW", (x - side * (w / 2 + 0.02), y + r.uniform(0.5, w - 0.5), zz), (0.05, 0.4, 0.55), win, smooth=False)
            i += 1
        y += r.uniform(6, 11)
    flames = []
    for k in range(fires):
        side = r.choice((-1, 1))
        yy = r.uniform(y0 + 10, y1)
        h = r.uniform(4, 11)
        f = prim("cone", "AveF%d" % k, (side * r.uniform(half + 1, half + 9), yy, r.uniform(10, 22)), (r.uniform(1.2, 2.5), r.uniform(1.2, 2.5), h / 2), fire, seg=7)
        zc = f.location.z
        for fr in range(flick[0], flick[1] + 1, 4):
            sc_ = 1 + 0.2 * math.sin(fr * 0.5 + k) + 0.12 * r.random()
            f.scale.z = h / 2 * sc_
            f.keyframe_insert("scale", frame=fr)
        lt = point("AveL%d" % k, f.location + Vector((0, -3, 2)), 3000, (1.0, 0.3, 0.07), radius=1.0, shadow=False)
        flicker(lt, flick[0], flick[1], 3000, 0.35, 3, seed=k)
        flames.append(f)
    return flames
