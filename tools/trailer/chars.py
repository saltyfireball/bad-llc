"""Characters for the trailer: the cake-pop heroes, Grandmaster Crumb, the Demon King.

Original designs. A cake-pop is a ball on a stick with no arms and no legs: it
hops. Sprinkles fall off it. Faces look at -Y (the camera). Pivot at the
stick's foot, so root.location.z is the ground.
"""

import math
import random

import bpy
from mathutils import Vector

from common import (FPS, ease, empty, key, lin, link, mat, mesh_obj, point, prim, set_interp, tube,
                    bezier, lava_mat)

R = 0.26            # ball radius
STICK = 0.40        # stick length (ball bottom sits on top of it)
BALL_Z = STICK + R * 0.92

SPRINKLE_COLORS = {
    "vanilla": [(0.85, 0.65, 0.2), (0.9, 0.78, 0.4), (0.7, 0.5, 0.12)],
    "velvet": [(0.9, 0.85, 0.8), (0.95, 0.9, 0.88), (0.6, 0.1, 0.12)],
    "funfetti": [(0.95, 0.15, 0.25), (0.15, 0.55, 0.95), (0.98, 0.8, 0.1), (0.2, 0.8, 0.4),
                 (0.7, 0.2, 0.85), (0.98, 0.45, 0.1)],
    "crumb": [(0.5, 0.35, 0.2), (0.35, 0.22, 0.12)],
}
GLAZE = {
    "vanilla": (0.78, 0.66, 0.46),
    "velvet": (0.42, 0.015, 0.035),
    "funfetti": (0.9, 0.72, 0.8),
    "crumb": (0.3, 0.17, 0.09),
}


class Pop:
    pass


def _feature(pop, name, az, el, depth, scale, m, rot=(0, 0, 0), seg=16, kind="sphere"):
    """A face feature on the ball: a pivot at the ball centre rotated by
    azimuth/elevation, the feature set out on -Y."""
    pv = empty(pop.name + "_" + name + "_pv", (0, 0, 0), pop.pivot)
    pv.rotation_euler = (-math.radians(el), 0, math.radians(az))
    ob = prim(kind, pop.name + "_" + name, (0, -R * depth, 0), scale, m, pv, seg=seg, rot=rot)
    return pv, ob


def make_pop(name, kind, loc=(0, 0, 0), yaw=0.0, scale=1.0, sprinkles=70, seed=1, mood="serious"):
    r = random.Random(seed)
    p = Pop()
    p.name, p.kind, p.r, p.scale = name, kind, r, scale
    p.root = empty(name, loc)
    p.root.rotation_euler[2] = yaw
    p.root.scale = (scale,) * 3
    p.pivot = empty(name + "_ball", (0, 0, BALL_Z), p.root)
    glaze = mat(name + "_glaze", GLAZE[kind], 0.28, coat=0.8, sss=0.25, bump=0.04, bump_scale=140, spec=0.6)
    stick = mat(name + "_stick", (0.9, 0.86, 0.78), 0.7)
    dark = mat(name + "_eye", (0.01, 0.008, 0.01), 0.12, coat=1.0)
    white = mat(name + "_hl", (1, 1, 1), 0.2, emit=(1, 1, 1), estr=2.0)
    p.stick = prim("cyl", name + "_stick", (0, 0, STICK / 2), (0.016, 0.016, STICK / 2), stick, p.root, seg=12)
    p.ball = prim("sphere", name + "_ball", (0, 0, 0), (R, R, R), glaze, p.pivot, seg=48)
    # glaze pool around the stick
    p.skirt = prim("sphere", name + "_skirt", (0, 0, -R * 0.78), (R * 0.62, R * 0.62, R * 0.22),
                   mat(name + "_pool", tuple(c * 0.85 for c in GLAZE[kind]), 0.3, coat=0.6), p.pivot, seg=24)
    # face
    eye_az = 21
    p.eyes, p.eye_pv = [], []
    for s in (-1, 1):
        pv, e = _feature(p, "eye%d" % s, s * eye_az, 6, 0.97, (0.036, 0.011, 0.056), dark)
        _, hl = _feature(p, "hl%d" % s, s * eye_az - s * 3, 12, 1.0, (0.011, 0.005, 0.014), white, seg=8)
        p.eyes.append(e)
        p.eye_pv.append(pv)
        bz = mat(name + "_brow", tuple(c * 0.5 for c in GLAZE[kind]), 0.5)
        ang = 0.28 * s if mood == "serious" else -0.1 * s
        _feature(p, "brow%d" % s, s * (eye_az + 2), 25, 0.985, (0.05, 0.008, 0.01), dark, rot=(0, -ang, 0), kind="cube", seg=4)
    pv, p.mouth = _feature(p, "mouth", 0, -15, 0.985, (0.03, 0.008, 0.007), dark, seg=12)
    # sprinkles
    cols = SPRINKLE_COLORS[kind]
    p.sprinkles = []
    sm = [mat(name + "_spr%d" % i, c, 0.35, coat=0.5) for i, c in enumerate(cols)]
    n = 0
    tries = 0
    while n < sprinkles and tries < sprinkles * 20:
        tries += 1
        z = r.uniform(-0.2, 1.0)
        th = r.uniform(0, 2 * math.pi)
        rad = math.sqrt(1 - z * z)
        d = Vector((rad * math.cos(th), rad * math.sin(th), z))
        # keep the face clear: front is -Y
        if d.y < -0.35 and -0.35 < d.z < 0.55 and abs(d.x) < 0.7:
            continue
        pos = d * R * 1.0
        s = prim("sphere", "%s_sp%d" % (name, n), pos, (0.007, 0.007, 0.022), r.choice(sm), p.pivot, seg=8)
        q = d.to_track_quat("Z", "Y")
        from mathutils import Quaternion
        q = q @ Quaternion((1, 0, 0), math.pi / 2) @ Quaternion((0, 0, 1), r.uniform(0, 6.28))
        s.rotation_euler = q.to_euler()
        p.sprinkles.append(s)
        n += 1
    ACCESSORIES[kind](p)
    return p


def _vanilla(p):
    red = mat("scarf", (0.55, 0.03, 0.05), 0.6)
    sc_ = _torus(p.name + "_scarf", 0.036, 0.016, red)
    sc_.parent = p.pivot
    sc_.location = (0, 0, -R * 1.02)
    p.tails = []
    for i, off in enumerate((0.0, 0.03)):
        t = prim("cube", p.name + "_tail%d" % i, (0.04 + off, 0.03, -R * 1.02 - 0.09), (0.02, 0.006, 0.1), red, p.pivot, seg=4)
        t.rotation_euler = (0, 0, 0)
        p.tails.append(t)
    # a nick in the glaze: she has been in fights
    prim("cube", p.name + "_scar", (R * 0.5, -R * 0.82, R * 0.35), (0.04, 0.004, 0.006), mat("scar", (0.35, 0.28, 0.18), 0.7), p.pivot,
         rot=(0, 0.6, 0.5), seg=4)


def _velvet(p):
    gm = mat("frames", (0.7, 0.55, 0.2), 0.25, metal=1.0)
    lens = mat("lens", (0.4, 0.6, 1.0), 0.05, emit=(0.4, 0.65, 1.0), estr=0.6, alpha=0.35)
    for s in (-1, 1):
        pv = empty(p.name + "_gl%d" % s, (0, 0, 0), p.pivot)
        pv.rotation_euler = (-math.radians(6), 0, math.radians(21) * s)
        ring = _torus(p.name + "_ring%d" % s, 0.062, 0.006, gm)
        ring.parent = pv
        ring.location = (0, -R * 1.02, 0)
        ring.rotation_euler = (math.pi / 2, 0, 0)
        ln = prim("cyl", p.name + "_lens%d" % s, (0, -R * 1.015, 0), (0.058, 0.002, 0.058), lens, pv, seg=24, rot=(math.pi / 2, 0, 0))
    # headset band over the top
    band = _torus(p.name + "_band", R * 1.03, 0.011, mat("band", (0.03, 0.03, 0.035), 0.3, metal=0.8))
    band.parent = p.pivot
    band.rotation_euler = (math.pi / 2, 0, math.radians(8))
    prim("sphere", p.name + "_cup", (R * 1.02, 0, 0.0), (0.04, 0.07, 0.07), mat("cup", (0.03, 0.03, 0.035), 0.3, metal=0.8), p.pivot, seg=16)
    # white drizzle stripes
    wd = mat("drizzle", (0.95, 0.92, 0.9), 0.3, coat=0.5)
    for i in range(5):
        a = math.radians(-70 + i * 28)
        prim("sphere", p.name + "_dz%d" % i, (math.sin(a) * R * 0.99, -math.cos(a) * R * 0.4, R * 0.55), (0.012, 0.012, 0.12), wd, p.pivot,
             rot=(0.4, a * 0.6, a), seg=8)


def _funfetti(p):
    blk = mat("patch", (0.01, 0.01, 0.012), 0.4)
    patch = prim("sphere", p.name + "_patch", (0, 0, 0), (0.05, 0.016, 0.058), blk, empty(p.name + "_pp", (0, 0, 0), p.pivot), seg=16)
    patch.parent.rotation_euler = (-math.radians(6), 0, math.radians(-21))
    patch.location = (0, -R * 1.0, 0)
    strap = _torus(p.name + "_strap", R * 1.0, 0.006, blk)
    strap.parent = p.pivot
    strap.rotation_euler = (math.radians(80), 0, math.radians(-8))
    ban = mat("bandana", (0.05, 0.05, 0.06), 0.8)
    b = _torus(p.name + "_bandana", R * 0.8, 0.028, ban)
    b.parent = p.pivot
    b.location = (0, 0, R * 0.52)
    b.scale = (1, 1, 0.8)
    for i, a in enumerate((0.3, 0.6)):
        prim("cube", p.name + "_knot%d" % i, (R * 0.7, R * 0.5, R * 0.52 - i * 0.03), (0.06, 0.01, 0.014), ban, p.pivot,
             rot=(0, 0.5 + a, 0.8), seg=4)


def _crumb(p):
    p.tails = []
    mus = mat("mustache", (0.92, 0.9, 0.86), 0.7)
    for s in (-1, 1):
        pv = empty(p.name + "_mu%d" % s, (0, 0, 0), p.pivot)
        pv.rotation_euler = (math.radians(14), 0, math.radians(11) * s)
        prim("sphere", p.name + "_must%d" % s, (0.0, -R * 0.99, 0), (0.06, 0.016, 0.02), mus, pv, seg=12, rot=(0, -0.5 * s, 0))
        pv2 = empty(p.name + "_bw%d" % s, (0, 0, 0), p.pivot)
        pv2.rotation_euler = (math.radians(-27), 0, math.radians(21) * s)
        prim("sphere", p.name + "_bush%d" % s, (0, -R * 0.99, 0), (0.07, 0.02, 0.016), mus, pv2, seg=12, rot=(0, -0.3 * s, 0))
    # the bite: a hollow where a chunk of him is gone, floored in crumb
    crumb = mat("crumb_in", (0.42, 0.25, 0.09), 0.98, bump=0.9, bump_scale=70)
    cutpos = (R * 0.78, -R * 0.35, R * 0.32)
    cutscale = (R * 0.62,) * 3
    cut = prim("sphere", p.name + "_cut", cutpos, cutscale, None, p.pivot, seg=32)
    cut.hide_render = True
    inner = prim("sphere", p.name + "_inner", cutpos, tuple(v * 0.99 for v in cutscale), crumb, p.pivot, seg=32)
    clip = prim("sphere", p.name + "_clip", (0, 0, 0), (R * 0.997,) * 3, None, p.pivot, seg=48)
    clip.hide_render = True
    m1 = p.ball.modifiers.new("bite", "BOOLEAN")
    m1.operation = "DIFFERENCE"
    m1.object = cut
    m2 = inner.modifiers.new("clip", "BOOLEAN")
    m2.operation = "INTERSECT"
    m2.object = clip
    # tooth marks: little scallops are not worth the geometry; a crack instead
    prim("cube", p.name + "_crack", (-R * 0.3, -R * 0.9, R * 0.6), (0.07, 0.004, 0.004), mat("crack", (0.02, 0.012, 0.008), 0.9), p.pivot,
         rot=(0, 0.9, 0.3), seg=4)


def _torus(name, major, minor, m, seg=36, ring=8):
    verts, faces = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        for j in range(ring):
            b = 2 * math.pi * j / ring
            verts.append(((major + minor * math.cos(b)) * math.cos(a), (major + minor * math.cos(b)) * math.sin(a), minor * math.sin(b)))
    for i in range(seg):
        for j in range(ring):
            a, b = i * ring + j, i * ring + (j + 1) % ring
            c, d = ((i + 1) % seg) * ring + (j + 1) % ring, ((i + 1) % seg) * ring + j
            faces.append((a, b, c, d))
    return mesh_obj(name, verts, faces, m, True)


ACCESSORIES = {"vanilla": _vanilla, "velvet": _velvet, "funfetti": _funfetti, "crumb": _crumb}


# ------------------------------------------------------------ motion

def squash(p, f, sx, sz):
    p.pivot.scale = (sx, sx, sz)
    p.pivot.keyframe_insert("scale", frame=f)


def idle(p, f0, f1, sway=0.012):
    """A breath: the ball breathes in scale, the whole pop barely sways."""
    for f in range(f0, f1 + 1, 6):
        t = (f - f0) / FPS
        s = 1 + 0.008 * math.sin(t * 2.2)
        p.pivot.scale = (s, s, 1 / s)
        p.pivot.keyframe_insert("scale", frame=f)
        p.pivot.rotation_euler[1] = sway * math.sin(t * 1.3)
        p.pivot.keyframe_insert("rotation_euler", frame=f)
    set_interp(p.pivot, "BEZIER")


def hop(p, f0, targets, air=9, rest=5, height=0.32, lean=0.1, yaw_to=None):
    """Hop through a list of (x, y) ground points. Returns the frame after the last landing.
    Keys the root every frame in the air; squash before takeoff and on landing."""
    f = f0
    cur = Vector(p.root.location)
    cur.z = p.root.location.z
    z0 = cur.z
    p.root.keyframe_insert("location", frame=f)
    squash(p, f, 1, 1)
    for tx, ty in targets:
        dst = Vector((tx, ty, z0))
        d = dst - cur
        p.root.location = cur
        p.root.keyframe_insert("location", frame=f + rest - 2)
        squash(p, f + rest - 2, 1.0, 1.0)
        squash(p, f + rest, 1.12, 0.82)        # crouch
        for k in range(air + 1):
            t = k / air
            pos = cur + d * t
            pos.z = z0 + 4 * height * t * (1 - t)
            p.root.location = pos
            p.root.keyframe_insert("location", frame=f + rest + k)
        p.pivot.rotation_euler[0] = 0
        p.pivot.keyframe_insert("rotation_euler", frame=f + rest)
        p.pivot.rotation_euler[0] = -lean
        p.pivot.keyframe_insert("rotation_euler", frame=f + rest + air // 2)
        p.pivot.rotation_euler[0] = 0
        p.pivot.keyframe_insert("rotation_euler", frame=f + rest + air)
        squash(p, f + rest + 1, 0.92, 1.14)      # stretch in the air
        squash(p, f + rest + air - 1, 0.94, 1.1)
        squash(p, f + rest + air, 1.14, 0.8)    # land
        squash(p, f + rest + air + 3, 1.0, 1.0)
        f = f + rest + air + 3
        cur = dst
    lin(p.root)
    set_interp(p.pivot, "BEZIER")
    return f


def talk(p, f0, f1, seed=0):
    """Mouth flaps while a line plays (a deadpan little mouth)."""
    r = random.Random(seed + f0)
    f = f0
    while f < f1:
        for v in (0.9, 0.2):
            p.mouth.scale = (0.03, 0.008, 0.007 * (1 + 2.2 * v * r.uniform(0.6, 1.2)))
            p.mouth.keyframe_insert("scale", frame=f)
            f += 2 + r.randint(0, 1)
    p.mouth.scale = (0.03, 0.008, 0.007)
    p.mouth.keyframe_insert("scale", frame=f1 + 1)
    set_interp(p.mouth, "CONSTANT")


def eyes_state(p, f, openness):
    for e in p.eyes:
        e.scale = (0.036, 0.011, 0.056 * max(openness, 0.04))
        e.keyframe_insert("scale", frame=f)


def blink(p, f):
    for g, o in ((f - 1, 1), (f + 1, 0.05), (f + 3, 1)):
        eyes_state(p, g, o)


def shed(p, sc, frames, floor_z=0.0, seed=7, per=4, wind=(0, 0, 0), fall_frames=60):
    """At each frame in `frames`, `per` sprinkles come off the ball and fall
    to the floor, bounce and lie there. Call after the pop's motion is keyed."""
    r = random.Random(seed)
    pool = list(p.sprinkles)
    r.shuffle(pool)
    for f in frames:
        for _ in range(per):
            if not pool:
                return
            s = pool.pop()
            sc.frame_set(f)
            bpy.context.view_layer.update()
            wp = s.matrix_world.translation.copy()
            col = s.active_material or s.material_slots[0].material
            loose = prim("sphere", s.name + "_loose", wp, (0.007, 0.007, 0.022), col, None, seg=8)
            loose.rotation_euler = (r.random() * 6, r.random() * 6, r.random() * 6)
            sc_ = p.scale
            loose.scale = tuple(v * sc_ for v in loose.scale)
            # hide the original from f on, show the loose one from f on
            s.hide_render = False
            s.keyframe_insert("hide_render", frame=f - 1)
            s.hide_render = True
            s.keyframe_insert("hide_render", frame=f)
            loose.hide_render = True
            loose.keyframe_insert("hide_render", frame=f - 1)
            loose.hide_render = False
            loose.keyframe_insert("hide_render", frame=f)
            v = Vector((r.uniform(-0.4, 0.4), r.uniform(-0.3, 0.3), r.uniform(0.0, 0.6))) + Vector(wind)
            pos = wp.copy()
            vel = v.copy()
            rest = floor_z + 0.008
            rot = Vector(loose.rotation_euler)
            spin = Vector((r.uniform(-9, 9), r.uniform(-9, 9), r.uniform(-9, 9)))
            for k in range(fall_frames):
                dt = 1.0 / FPS
                vel.z -= 9.8 * dt
                pos += vel * dt
                if pos.z < rest:
                    pos.z = rest
                    if abs(vel.z) > 0.6:
                        vel.z = -vel.z * 0.35
                        vel.x *= 0.6
                        vel.y *= 0.6
                        spin *= 0.5
                    else:
                        vel = Vector((0, 0, 0))
                        spin = Vector((0, 0, 0))
                rot = rot + spin * dt
                loose.location = pos
                loose.rotation_euler = tuple(rot)
                loose.keyframe_insert("location", frame=f + k)
                loose.keyframe_insert("rotation_euler", frame=f + k)
    lin(p.root)


def chunk_falls(p, sc, f, size=0.06, floor_z=0.0):
    """A piece of cake drops off (Crumb)."""
    m = mat("chunk", (0.55, 0.35, 0.14), 0.95, bump=0.5, bump_scale=50)
    sc.frame_set(f)
    wp = p.pivot.matrix_world.translation + Vector((0.12, -0.14, 0.02)) * p.scale
    o = prim("sphere", "Chunk", wp, (size, size * 0.8, size * 0.7), m, None, seg=10)
    o.hide_render = True
    o.keyframe_insert("hide_render", frame=f - 1)
    o.hide_render = False
    o.keyframe_insert("hide_render", frame=f)
    pos, vel, rest = wp.copy(), Vector((0.05, -0.1, 0)), floor_z + size * 0.7
    for k in range(40):
        vel.z -= 9.8 / FPS
        pos += vel / FPS
        if pos.z < rest:
            pos.z = rest
            vel = Vector((0, 0, abs(vel.z) * 0.15 if abs(vel.z) > 1 else 0))
        o.location = pos
        o.keyframe_insert("location", frame=f + k)
        o.rotation_euler = (k * 0.15, k * 0.1, 0)
        o.keyframe_insert("rotation_euler", frame=f + k)
    lin(o)
    return o


# ------------------------------------------------------------ demon

class Demon:
    pass


def make_demon(loc=(0, 0, 0), scale=1.0, yaw=0.0, glow=(1.0, 0.3, 0.05), eye=(1.0, 0.55, 0.15), name="Demon"):
    """The Demon King: 12 m tall, horned, charred skin with glowing cracks.
    Faces -Y. Posable: head, jaw, right arm (shoulder, elbow), fingers."""
    d = Demon()
    d.root = empty(name, loc)
    d.root.rotation_euler[2] = yaw
    d.root.scale = (scale,) * 3
    skin = lava_mat(name + "_skin", (0.018, 0.009, 0.01), glow, scale=0.9, strength=2.0)
    skin2 = lava_mat(name + "_skin2", (0.03, 0.012, 0.012), glow, scale=1.6, strength=2.0)
    bone = mat(name + "_horn", (0.08, 0.06, 0.05), 0.35, coat=0.3, bump=0.2, bump_scale=8)
    tooth = mat(name + "_tooth", (0.55, 0.5, 0.4), 0.3)
    eyem = mat(name + "_eye", (1, 0.6, 0.2), 0.3, emit=eye, estr=60.0)
    d.eye_mat = eyem
    gum = mat(name + "_gum", (0.12, 0.01, 0.01), 0.5, emit=(1, 0.1, 0.02), estr=2.5)
    P = lambda n, loc, sc, m, par=None, **k: prim("sphere", name + n, loc, sc, m, par or d.root, seg=32, **k)
    d.torso = P("_torso", (0, 0, 7.4), (2.3, 1.5, 3.1), skin)
    P("_belly", (0, -0.5, 5.6), (2.0, 1.5, 1.9), skin2)
    P("_pelvis", (0, 0, 4.2), (2.0, 1.5, 1.4), skin2)
    for s in (-1, 1):
        tube(name + "_leg%d" % s, [(s * 1.0, 0, 4.0), (s * 1.3, -0.1, 2.0), (s * 1.3, 0, 0.5)], [1.0, 0.85, 0.7], skin2).parent = d.root
        prim("cube", name + "_foot%d" % s, (s * 1.35, -0.7, 0.3), (0.95, 1.5, 0.35), skin2, d.root, smooth=False)
        P("_shoulder%d" % s, (s * 3.2, 0, 9.3), (1.15, 1.0, 1.1), skin)
        for k in range(3):
            prim("cone", name + "_spk%d%d" % (s + 1, k), (s * (3.0 + k * 0.45), 0.0, 10.3 + k * 0.35), (0.28, 0.28, 1.1 + 0.3 * k), bone, d.root, seg=8, rot=(0, s * (0.5 + k * 0.28), 0))
    # head
    d.head = empty(name + "_head", (0, -0.2, 10.9), d.root)
    P("_skull", (0, 0, 0), (1.6, 1.6, 1.7), skin, d.head)
    P("_snout", (0, -1.2, -0.55), (0.9, 0.9, 0.7), skin, d.head)
    for s in (-1, 1):
        P("_nostril%d" % s, (s * 0.3, -2.0, -0.35), (0.14, 0.2, 0.2), mat(name + "_nos", (0, 0, 0), 1.0), d.head)
        prim("cube", name + "_brow%d" % s, (s * 0.65, -1.25, 0.55), (0.7, 0.28, 0.2), skin, d.head,
             rot=(0.2, -0.45 * s, 0.0), smooth=False)
        P("_eye%d" % s, (s * 0.65, -1.38, 0.28), (0.34, 0.12, 0.15), eyem, d.head, rot=(0, -0.35 * s, 0))
        h = tube(name + "_horn%d" % s, bezier((s * 1.0, 0.1, 1.0), (s * 3.4, -0.2, 2.4), (s * 2.3, -1.0, 5.6), 14),
                 [0.55 - 0.035 * i for i in range(14)], bone)
        h.parent = d.head
        h2 = tube(name + "_horn2%d" % s, bezier((s * 1.5, 0.3, 0.2), (s * 3.0, 0.5, 0.9), (s * 3.3, -0.2, 2.5), 10),
                  [0.3 - 0.026 * i for i in range(10)], bone)
        h2.parent = d.head
    d.eye_lights = [point(name + "_eyeL%d" % i, (0, 0, 0), 300 * scale, eye, radius=0.2) for i in (0, 1)]
    for i, s in enumerate((-1, 1)):
        d.eye_lights[i].parent = d.head
        d.eye_lights[i].location = (s * 0.65, -1.9, 0.3)
    # upper teeth + jaw
    for i in range(9):
        a = -0.78 + i * 0.195
        prim("cone", name + "_ut%d" % i, (a * 1.25, -1.95 + abs(a) * 0.5, -0.95), (0.1, 0.1, 0.34), tooth, d.head, seg=8,
             rot=(math.pi, 0, 0))
    d.jaw = empty(name + "_jaw", (0, -0.2, -0.85), d.head)
    P("_jawbone", (0, -1.0, -0.35), (1.15, 1.25, 0.5), skin2, d.jaw)
    P("_mouth", (0, -1.0, 0.25), (0.95, 1.0, 0.2), gum, d.jaw)
    for i in range(9):
        a = -0.78 + i * 0.195
        prim("cone", name + "_lt%d" % i, (a * 1.2, -1.85 + abs(a) * 0.5, 0.0), (0.1, 0.1, 0.4), tooth, d.jaw, seg=8)
    # arms: shoulder -> elbow -> hand (fingers curl)
    d.arm = {}
    for s, side in ((-1, "L"), (1, "R")):
        sh = empty(name + "_sh" + side, (s * 3.3, 0, 9.3), d.root)
        sh.rotation_euler = (0.1, 0, s * 0.12)
        tube(name + "_ua" + side, [(0, 0, 0), (0, -0.05, -1.5), (0, -0.1, -3.2)], [0.95, 0.85, 0.75], skin).parent = sh
        el = empty(name + "_el" + side, (0, -0.1, -3.2), sh)
        P("_elbow" + side, (0, 0, 0), (0.8, 0.8, 0.8), skin, el)
        tube(name + "_fa" + side, [(0, 0, 0), (0, -0.2, -1.6), (0, -0.4, -3.2)], [0.8, 0.8, 0.75], skin2).parent = el
        for k in range(3):
            prim("cone", name + "_fspk%s%d" % (side, k), (s * 0.7, -0.15, -0.8 - k * 0.95), (0.16, 0.16, 0.7 - 0.12 * k), bone, el, seg=6, rot=(0, s * 1.25, 0))
        hand = empty(name + "_hand" + side, (0, -0.4, -3.2), el)
        P("_palm" + side, (0, -0.1, -0.2), (0.9, 0.45, 0.8), skin2, hand)
        fingers = []
        for i, fx in enumerate((-0.6, -0.2, 0.2, 0.6)):
            fp = empty(name + "_fp%s%d" % (side, i), (fx, -0.1, -0.8), hand)
            tube(name + "_fg%s%d" % (side, i), [(0, 0, 0), (0, 0, -0.5), (0, 0, -1.0)], [0.2, 0.17, 0.12], skin2, ring=6).parent = fp
            prim("cone", name + "_claw%s%d" % (side, i), (0, 0, -1.2), (0.09, 0.09, 0.32), bone, fp, seg=6, rot=(math.pi, 0, 0))
            fingers.append(fp)
        th = empty(name + "_th" + side, (s * 0.85, -0.2, -0.3), hand)
        tube(name + "_thm" + side, [(0, 0, 0), (s * 0.3, -0.1, -0.4), (s * 0.5, -0.2, -0.8)], [0.24, 0.2, 0.14], skin2, ring=6).parent = th
        d.arm[side] = {"sh": sh, "el": el, "hand": hand, "fingers": fingers, "thumb": th}
    # tail-less, but a spine ridge of horns down the back is for the back side; skip
    return d


def curl(arm, f, amount):
    """Fingers curl toward the palm (0 open, 1 fist)."""
    for fp in arm["fingers"]:
        fp.rotation_euler[0] = -1.5 * amount
        fp.keyframe_insert("rotation_euler", frame=f)
    arm["thumb"].rotation_euler[0] = -1.0 * amount
    arm["thumb"].keyframe_insert("rotation_euler", frame=f)


def eye_glow(d, f, strength, lights=None):
    """Key the demon's eyes (emission strength and the two lights)."""
    b = d.eye_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    b.default_value = strength
    b.keyframe_insert("default_value", frame=f)
    for L in d.eye_lights:
        L.data.energy = (lights if lights is not None else strength * 5) * d.root.scale[0]
        L.data.keyframe_insert("energy", frame=f)


def jaw_talk(d, f0, f1, amp=0.2, seed=0):
    r = random.Random(seed + f0)
    f = f0
    while f < f1:
        d.jaw.rotation_euler[0] = amp * r.uniform(0.5, 1.2)
        d.jaw.keyframe_insert("rotation_euler", frame=f)
        d.jaw.rotation_euler[0] = amp * 0.15
        d.jaw.keyframe_insert("rotation_euler", frame=f + 3)
        f += 6 + r.randint(0, 3)
    d.jaw.rotation_euler[0] = 0
    d.jaw.keyframe_insert("rotation_euler", frame=f1 + 2)
