"""Volumetric fire, smoke, fireballs and camera shake (BAD-891).

EEVEE volumes with animated 4D noise: a flame is a box whose Principled Volume
density is noise eroded by a tapering column, scrolling upward, with the noise W
axis driven by the frame so it boils. Emission comes from a heat ramp.
"""
import math
import random

import bpy
from mathutils import Vector

import common as C


def _val(nt, name, v):
    n = nt.nodes.new("ShaderNodeValue")
    n.name = n.label = name
    n.outputs[0].default_value = v
    return n


def _math(nt, op, a=None, b=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for i, x in ((0, a), (1, b)):
        if x is None:
            continue
        if isinstance(x, (int, float)):
            n.inputs[i].default_value = x
        else:
            nt.links.new(x, n.inputs[i])
    return n.outputs[0]


def _driver(sock, expr):
    d = sock.driver_add("default_value").driver
    d.type = "SCRIPTED"
    d.expression = expr


def _new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"][0]
    return m, nt, out


def _ramp(nt, stops):
    r = nt.nodes.new("ShaderNodeValToRGB")
    cr = r.color_ramp
    while len(cr.elements) < len(stops):
        cr.elements.new(0.5)
    for el, (p, c) in zip(cr.elements, stops):
        el.position = p
        el.color = (c[0], c[1], c[2], 1)
    return r


HEAT = [(0.0, (0.0, 0.0, 0.0)), (0.18, (0.30, 0.02, 0.0)), (0.45, (1.0, 0.28, 0.03)),
        (0.75, (1.0, 0.65, 0.16)), (1.0, (1.0, 0.95, 0.7))]


def flame_mat(name, seed=0, speed=0.09, rise=1.6, scale=3.2, dens=4.0, emit=9.0, smoke=0.35):
    """Flame column in a unit box (Generated coords: z up 0..1)."""
    m, nt, out = _new_mat(name)
    g = nt.nodes.new("ShaderNodeTexCoord").outputs["Generated"]
    sp = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(g, sp.inputs[0])
    x = _math(nt, "SUBTRACT", sp.outputs[0], 0.5)
    y = _math(nt, "SUBTRACT", sp.outputs[1], 0.5)
    z = sp.outputs[2]
    r = _math(nt, "MULTIPLY", _math(nt, "SQRT", _math(nt, "ADD", _math(nt, "MULTIPLY", x, x), _math(nt, "MULTIPLY", y, y))), 2.0)
    # column narrows with height
    width = _math(nt, "SUBTRACT", 1.0, _math(nt, "MULTIPLY", z, 0.6))
    taper = _math(nt, "SUBTRACT", 1.0, _math(nt, "DIVIDE", r, width), clamp=True)
    t = _val(nt, "T", 0.0)
    _driver(t.outputs[0], "frame*%f" % speed)
    zs = _math(nt, "SUBTRACT", _math(nt, "MULTIPLY", z, scale), _math(nt, "MULTIPLY", t.outputs[0], rise))
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(_math(nt, "MULTIPLY", sp.outputs[0], scale), comb.inputs[0])
    nt.links.new(_math(nt, "MULTIPLY", sp.outputs[1], scale), comb.inputs[1])
    nt.links.new(zs, comb.inputs[2])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "4D"
    nz.inputs["Detail"].default_value = 6.0
    nz.inputs["Roughness"].default_value = 0.62
    nz.inputs["W"].default_value = seed * 7.3
    wnode = _val(nt, "W", 0.0)
    _driver(wnode.outputs[0], "frame*%f+%f" % (speed * 0.9, seed * 7.3))
    nt.links.new(wnode.outputs[0], nz.inputs["W"])
    nt.links.new(comb.outputs[0], nz.inputs["Vector"])
    n = nz.outputs["Fac"]
    # eroded by height: tips break up into wisps
    fd = _math(nt, "SUBTRACT", _math(nt, "ADD", n, _math(nt, "MULTIPLY", taper, 0.95)), _math(nt, "ADD", 0.78, _math(nt, "MULTIPLY", z, 0.25)))
    fd = _math(nt, "MULTIPLY", fd, 3.0, clamp=True)
    heat = _math(nt, "MULTIPLY", fd, _math(nt, "SUBTRACT", 1.2, _math(nt, "MULTIPLY", z, 0.7)), clamp=True)
    ramp = _ramp(nt, HEAT)
    nt.links.new(heat, ramp.inputs["Fac"])
    vp = nt.nodes.new("ShaderNodeVolumePrincipled")
    vp.inputs["Color"].default_value = (0.03, 0.012, 0.006, 1)
    vp.inputs["Density"].default_value = 1.0
    nt.links.new(_math(nt, "MULTIPLY", fd, dens), vp.inputs["Density"])
    nt.links.new(ramp.outputs["Color"], vp.inputs["Emission Color"])
    nt.links.new(_math(nt, "MULTIPLY", heat, emit), vp.inputs["Emission Strength"])
    nt.links.new(vp.outputs[0], out.inputs["Volume"])
    return m


def smoke_mat(name, seed=0, speed=0.05, rise=0.8, scale=1.6, dens=1.1, color=(0.02, 0.016, 0.014), glow=0.0):
    m, nt, out = _new_mat(name)
    g = nt.nodes.new("ShaderNodeTexCoord").outputs["Generated"]
    sp = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(g, sp.inputs[0])
    x = _math(nt, "SUBTRACT", sp.outputs[0], 0.5)
    y = _math(nt, "SUBTRACT", sp.outputs[1], 0.5)
    z = sp.outputs[2]
    r = _math(nt, "MULTIPLY", _math(nt, "SQRT", _math(nt, "ADD", _math(nt, "MULTIPLY", x, x), _math(nt, "MULTIPLY", y, y))), 2.0)
    width = _math(nt, "ADD", 0.45, _math(nt, "MULTIPLY", z, 0.55))
    taper = _math(nt, "SUBTRACT", 1.0, _math(nt, "DIVIDE", r, width), clamp=True)
    t = _val(nt, "T", 0.0)
    _driver(t.outputs[0], "frame*%f" % speed)
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(_math(nt, "MULTIPLY", sp.outputs[0], scale), comb.inputs[0])
    nt.links.new(_math(nt, "MULTIPLY", sp.outputs[1], scale), comb.inputs[1])
    nt.links.new(_math(nt, "SUBTRACT", _math(nt, "MULTIPLY", z, scale), _math(nt, "MULTIPLY", t.outputs[0], rise)), comb.inputs[2])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "4D"
    nz.inputs["Detail"].default_value = 5.0
    w = _val(nt, "W", 0.0)
    _driver(w.outputs[0], "frame*%f+%f" % (speed * 0.6, seed * 3.1))
    nt.links.new(w.outputs[0], nz.inputs["W"])
    nt.links.new(comb.outputs[0], nz.inputs["Vector"])
    fd = _math(nt, "SUBTRACT", _math(nt, "ADD", nz.outputs["Fac"], _math(nt, "MULTIPLY", taper, 0.8)), 0.8)
    fd = _math(nt, "MULTIPLY", fd, 2.5, clamp=True)
    vp = nt.nodes.new("ShaderNodeVolumePrincipled")
    vp.inputs["Color"].default_value = (color[0], color[1], color[2], 1)
    vp.inputs["Anisotropy"].default_value = 0.4
    nt.links.new(_math(nt, "MULTIPLY", fd, dens), vp.inputs["Density"])
    if glow > 0:
        vp.inputs["Emission Color"].default_value = (1.0, 0.3, 0.05, 1)
        nt.links.new(_math(nt, "MULTIPLY", _math(nt, "MULTIPLY", fd, _math(nt, "SUBTRACT", 1.0, z, clamp=True)), glow), vp.inputs["Emission Strength"])
    nt.links.new(vp.outputs[0], out.inputs["Volume"])
    return m


def _box(name, loc, size, m):
    """A unit-cube volume object (Generated 0..1 across it), base at loc.z."""
    ob = C.prim("cube", name, (loc[0], loc[1], loc[2] + size[2] / 2), (size[0] / 2, size[1] / 2, size[2] / 2), m, smooth=False)
    ob.visible_shadow = False
    return ob


def flame(loc, h=3.0, w=None, seed=0, light=True, lamp_energy=None, smoke=True, haze=True, name="Flame", speed=0.09):
    """A burning column: flame box, a smoke plume above it, a warm shimmer, and a flickering light."""
    w = w or h * 0.55
    loc = Vector(loc)
    _box("%s%d" % (name, seed), loc, (w * 1.5, w * 1.5, h), flame_mat("%sM%d" % (name, seed), seed, speed=speed, dens=4.5 / max(h, 1.0) * 3.0, emit=9.0))
    if smoke:
        _box("%sSmoke%d" % (name, seed), loc + Vector((0, 0, h * 0.7)), (w * 3.5, w * 3.5, h * 3.2),
             smoke_mat("%sSM%d" % (name, seed), seed, dens=1.4 / max(h, 1.0) * 3.0, glow=0.0))
    if haze:
        _box("%sHaze%d" % (name, seed), loc + Vector((0, 0, h * 0.5)), (w * 2.2, w * 2.2, h * 2.2),
             smoke_mat("%sHM%d" % (name, seed), seed + 5, speed=0.22, rise=2.4, scale=4.0, dens=0.12 / max(h, 1.0) * 3.0, color=(0.5, 0.25, 0.1)))
    if light:
        e = lamp_energy if lamp_energy is not None else 900 * h
        lt = C.point("%sLight%d" % (name, seed), loc + Vector((0, -w * 0.8, h * 0.45)), e, (1.0, 0.33, 0.07), radius=h * 0.15, shadow=False)
        return lt
    return None


def fireball(f0, loc, size=4.0, dur=26, seed=5, flash=40000):
    """An explosion: a rolling fireball that blooms and turns to a rising smoke column, with a flash and debris."""
    loc = Vector(loc)
    m, nt, out = _new_mat("Boom%d" % seed)
    g = nt.nodes.new("ShaderNodeTexCoord").outputs["Generated"]
    sp = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(g, sp.inputs[0])
    px = _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", sp.outputs[0], 0.5), 2.0)
    py = _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", sp.outputs[1], 0.5), 2.0)
    pz = _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", sp.outputs[2], 0.5), 2.0)
    pz = _math(nt, "SUBTRACT", pz, _math(nt, "MULTIPLY", _math(nt, "ADD", pz, 0.0), 0.0))
    r = _math(nt, "SQRT", _math(nt, "ADD", _math(nt, "ADD", _math(nt, "MULTIPLY", px, px), _math(nt, "MULTIPLY", py, py)), _math(nt, "MULTIPLY", pz, pz)))
    grow = _val(nt, "Grow", 0.1)
    burn = _val(nt, "Burn", 0.0)
    smk = _val(nt, "Smoke", 0.0)
    for f, gv, bv, sv in ((f0 - 1, 0.05, 0.0, 0.0), (f0 + 3, 0.55, 1.0, 0.3), (f0 + dur, 1.0, 0.7, 1.0), (f0 + dur + 36, 1.0, 0.0, 0.8), (f0 + dur + 70, 1.0, 0.0, 0.0)):
        grow.outputs[0].default_value = gv
        grow.outputs[0].keyframe_insert("default_value", frame=f)
        burn.outputs[0].default_value = bv
        burn.outputs[0].keyframe_insert("default_value", frame=f)
        smk.outputs[0].default_value = sv
        smk.outputs[0].keyframe_insert("default_value", frame=f)
    shape = _math(nt, "SUBTRACT", 1.0, _math(nt, "DIVIDE", r, grow.outputs[0]), clamp=True)
    t = _val(nt, "T", 0.0)
    _driver(t.outputs[0], "frame*0.11")
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(_math(nt, "MULTIPLY", px, 2.4), comb.inputs[0])
    nt.links.new(_math(nt, "MULTIPLY", py, 2.4), comb.inputs[1])
    nt.links.new(_math(nt, "SUBTRACT", _math(nt, "MULTIPLY", pz, 2.4), _math(nt, "MULTIPLY", t.outputs[0], 1.4)), comb.inputs[2])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "4D"
    nz.inputs["Detail"].default_value = 7.0
    nz.inputs["Roughness"].default_value = 0.6
    w = _val(nt, "W", 0.0)
    _driver(w.outputs[0], "frame*0.1+%f" % (seed * 5.0))
    nt.links.new(w.outputs[0], nz.inputs["W"])
    nt.links.new(comb.outputs[0], nz.inputs["Vector"])
    fd = _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", _math(nt, "ADD", _math(nt, "MULTIPLY", nz.outputs["Fac"], 1.5), _math(nt, "MULTIPLY", shape, 0.85)), 1.05), 2.0, clamp=True)
    heat = _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", fd, burn.outputs[0]), 0.8, clamp=True)
    ramp = _ramp(nt, HEAT)
    nt.links.new(heat, ramp.inputs["Fac"])
    vp = nt.nodes.new("ShaderNodeVolumePrincipled")
    vp.inputs["Color"].default_value = (0.02, 0.015, 0.012, 1)
    nt.links.new(_math(nt, "MULTIPLY", fd, _math(nt, "MULTIPLY", _math(nt, "ADD", 1.0, smk.outputs[0]), 3.0 / max(size, 1.0))), vp.inputs["Density"])
    nt.links.new(ramp.outputs["Color"], vp.inputs["Emission Color"])
    nt.links.new(_math(nt, "MULTIPLY", heat, 7.0), vp.inputs["Emission Strength"])
    nt.links.new(vp.outputs[0], out.inputs["Volume"])
    # the cloud: a big cube centred above the blast point
    ob = C.prim("cube", "Boom%d" % seed, (loc.x, loc.y, loc.z + size * 0.3), (size * 0.5,) * 3, m, smooth=False)
    ob.visible_shadow = False
    ob.scale = (0.01,) * 3
    for f, s in ((f0 - 2, 0.01), (f0 - 1, size * 0.5), (f0 + dur + 70, size * 0.9)):
        ob.scale = (s, s, s)
        ob.keyframe_insert("scale", frame=f)
    # smoke column that outlives it
    sm = _box("BoomSmoke%d" % seed, loc, (size * 1.6, size * 1.6, size * 3.2), smoke_mat("BoomSM%d" % seed, seed, dens=2.0 / max(size, 1.0) * 3.0, glow=1.5))
    sm.hide_render = True
    sm.keyframe_insert("hide_render", frame=f0 - 1)
    sm.hide_render = False
    sm.keyframe_insert("hide_render", frame=f0 + 2)
    set_c = lambda o: [setattr(k, "interpolation", "CONSTANT") for fc in C._fcurves(o) for k in fc.keyframe_points if fc.data_path == "hide_render"]
    set_c(sm)
    fl = C.point("BoomFlash%d" % seed, loc + Vector((0, -1.5, 1.0)), 0.0, (1, 0.55, 0.2), radius=0.6, shadow=False)
    for f, e in ((f0 - 1, 0), (f0 + 1, flash), (f0 + 10, flash * 0.3), (f0 + dur + 30, flash * 0.04), (f0 + dur + 60, 0)):
        fl.data.energy = e
        fl.data.keyframe_insert("energy", frame=f)
    # debris, shockwave dust ring omitted; debris as before
    r2 = random.Random(seed)
    for i in range(30):
        s = r2.uniform(0.04, 0.14)
        o = C.prim("cube", "Debris%d_%d" % (seed, i), loc, (0.0,) * 3, C.mat("Debris", (0.03, 0.025, 0.02), 0.8), seg=4)
        v = Vector((r2.uniform(-1, 1), r2.uniform(-0.7, 0.7), r2.uniform(0.6, 1.4))) * r2.uniform(3, 8)
        for k in range(0, 40, 3):
            tt = k / C.FPS
            p = loc + v * tt + Vector((0, 0, -4.9 * tt * tt))
            p.z = max(p.z, s)
            o.location = p
            o.scale = (s, s, s) if k else (0.001,) * 3
            o.rotation_euler = (tt * 7 * (i % 3 + 1), tt * 5, tt * 3)
            for prop in ("location", "scale", "rotation_euler"):
                o.keyframe_insert(prop, frame=f0 + k)
        C.lin(o)
    embers(f0, loc, 60, size)
    return fl


def embers(f0, loc, n=60, size=3.0, seed=1, life=70):
    """Embers thrown up by a blast or fire: glowing specks rising on a curve, cooling out."""
    r = random.Random(seed)
    glow = C.mat("Ember", (0.1, 0.03, 0.01), 0.7, emit=(1.0, 0.4, 0.08), estr=14.0)
    loc = Vector(loc)
    for i in range(n):
        s = 0.012 * r.uniform(0.6, 1.8) * max(size / 3.0, 0.6)
        o = C.prim("sphere", "EmberB%d" % i, loc, (0.001,) * 3, glow, seg=6)
        v = Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(0.8, 2.0))) * r.uniform(0.8, 2.4) * size * 0.35
        for k in range(0, life, 4):
            tt = k / C.FPS
            p = loc + v * tt + Vector((math.sin(tt * 6 + i) * 0.1, math.cos(tt * 5 + i) * 0.1, -0.6 * tt * tt))
            o.location = p
            sc = s * (1 - k / life) if k else 0.001
            o.scale = (sc,) * 3
            o.keyframe_insert("location", frame=f0 + k)
            o.keyframe_insert("scale", frame=f0 + k)
        C.lin(o)


def shake(cam, f0, f1, amp=0.05, freq=0.9, seed=0):
    """Hand-held rumble: noise F-curve modifiers on the camera target and body between f0 and f1."""
    for ob, a in ((cam.tgt, amp), (cam.ob, amp * 0.3)):
        for fc in C._fcurves(ob):
            if fc.data_path != "location":
                continue
            md = fc.modifiers.new("NOISE")
            md.scale = max(2.0, 24.0 / freq) * (1 + 0.37 * fc.array_index)
            md.strength = a
            md.phase = seed * 3.7 + fc.array_index * 11
            md.use_restricted_range = True
            md.frame_start = f0
            md.frame_end = f1
            md.blend_in = 4
            md.blend_out = 6
