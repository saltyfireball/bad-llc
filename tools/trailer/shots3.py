"""Shots, part three: Crumb, the Demon King, the montage, the finale, the stinger (BAD-857)."""

import math
import random

import bpy
from mathutils import Matrix, Vector

import chars
import common as C
import timeline as T
from common import COOL, FPS, HELL, WARM, Cam, area, ash, aim, empty, explosion, flicker, lin, mat, point, prim, rain, spot
from chars import (blink, curl, eye_glow, eyes_state, hop, idle, jaw_talk, make_demon, make_pop, shed, squash, talk,
                   chunk_falls)
from shots import SHOTS, dust_floor, label, secs, shot
from shots2 import _talk_lines, control_room


def hell_floor(size=300, scale=0.35, strength=3.0):
    return C.floor(size, (0.02, 0.012, 0.012), 0.6, m=C.lava_mat("HellFloor", (0.02, 0.011, 0.011), (1.0, 0.22, 0.04), scale, strength))


def sprinkle_rain(a, b, n=200, box=(-6, 6, 2, 12, 0, 8), seed=3, fall=1.6):
    r = random.Random(seed)
    cols = [(0.95, 0.15, 0.3), (0.2, 0.55, 0.98), (0.98, 0.8, 0.1), (0.25, 0.85, 0.45), (0.75, 0.25, 0.9), (1.0, 0.5, 0.15)]
    ms = [mat("RS%d" % i, c, 0.35, emit=c, estr=0.6) for i, c in enumerate(cols)]
    for i in range(n):
        p = Vector((r.uniform(box[0], box[1]), r.uniform(box[2], box[3]), r.uniform(box[4], box[5])))
        s = r.uniform(0.9, 1.6)
        o = prim("sphere", "RainSpr%d" % i, p, (0.012 * s, 0.012 * s, 0.04 * s), r.choice(ms), seg=8)
        rot = Vector((r.random() * 6, r.random() * 6, r.random() * 6))
        spin = Vector((r.uniform(-4, 4), r.uniform(-4, 4), r.uniform(-4, 4)))
        for f in range(a, b + 1, 6):
            t = (f - a) / FPS
            o.location = p + Vector((math.sin(t + i) * 0.1, 0, -fall * t * r.uniform(0.8, 1.2)))
            o.rotation_euler = tuple(rot + spin * t)
            o.keyframe_insert("location", frame=f)
            o.keyframe_insert("rotation_euler", frame=f)
        lin(o)


# ------------------------------------------------------------ stakes

@shot("crumb")
def crumb(sc, preview):
    """0:55 Grandmaster Crumb, half-eaten, one candle in a dusty pantry."""
    a, b = 1, T.frames("crumb")
    C.look((a, b), preview, haze=0.03, world=(0.002, 0.0015, 0.001), glare=0.6, aniso=0.6)
    wood = mat("PantryWood", (0.06, 0.03, 0.015), 0.6, bump=0.2, bump_scale=14)
    C.floor(40, (0.03, 0.02, 0.012), 0.5, m=wood)
    prim("plane", "PWall", (0, 3.2, 2.0), (9, 2.4, 1), mat("PWallM", (0.045, 0.03, 0.022), 0.9, bump=0.3, bump_scale=10), rot=(math.pi / 2, 0, 0), smooth=False)
    r = random.Random(4)
    glass = mat("Jar", (0.08, 0.04, 0.015), 0.15, coat=0.6)
    lid = mat("Lid", (0.1, 0.08, 0.06), 0.4, metal=0.8)
    sack = mat("Sack", (0.22, 0.18, 0.12), 0.95, bump=0.5, bump_scale=30)
    for si, z in enumerate((0.9, 1.7, 2.5)):
        prim("cube", "Shelf%d" % si, (0, 2.8, z), (4.5, 0.4, 0.03), wood, smooth=False)
        for k in range(14):
            x = -4.0 + k * 0.6 + r.uniform(-0.1, 0.1)
            if r.random() < 0.7:
                h = r.uniform(0.18, 0.34)
                prim("cyl", "Jar", (x, 2.8, z + 0.03 + h / 2), (0.1, 0.1, h / 2), glass, seg=14)
                prim("cyl", "JarLid", (x, 2.8, z + 0.03 + h + 0.01), (0.105, 0.105, 0.02), lid, seg=14)
            else:
                prim("sphere", "SackB", (x, 2.8, z + 0.18), (0.22, 0.14, 0.17), sack, seg=12)
    barrel = mat("Barrel", (0.07, 0.04, 0.02), 0.55, bump=0.2, bump_scale=10)
    prim("cyl", "Barrel", (0, 0, 0.275), (0.55, 0.55, 0.275), barrel, seg=24)
    prim("cyl", "BarrelTop", (0, 0, 0.552), (0.5, 0.5, 0.004), mat("BTop", (0.1, 0.06, 0.03), 0.5), seg=24)
    p = make_pop("crumb", "crumb", (0, 0, 0.555), yaw=0.0, seed=6, sprinkles=40)
    eyes_state(p, a, 0.55)
    idle(p, a, b, 0.01)
    p.pivot.rotation_euler[2] = 0
    blink(p, secs(1.2)); blink(p, secs(6.4))
    _talk_lines("crumb", {"c01": p})
    chunk_falls(p, sc, secs(5.6), floor_z=0.555)
    # one candle
    prim("cyl", "Candle", (0.6, -0.35, 0.67), (0.035, 0.035, 0.12), mat("Wax", (0.8, 0.75, 0.6), 0.5, sss=0.4), seg=12)
    fl = prim("sphere", "Flame", (0.6, -0.35, 0.82), (0.016, 0.016, 0.04), mat("Flame", (1, 0.6, 0.2), 0.5, emit=(1.0, 0.55, 0.15), estr=40), seg=10)
    L = point("CandleL", (0.6, -0.4, 0.84), 14, (1.0, 0.6, 0.25), radius=0.03)
    flicker(L, a, b, 14, 0.25, 2, seed=2)
    area("Moon", (-3, -2, 3), (0, 0, 0.8), 6, (0.4, 0.5, 0.8), 2)
    area("Face", (1.4, -2.2, 1.0), (0, 0, 0.8), 10.0, (1.0, 0.6, 0.3), 1)
    ash(a, b, n=90, box=(-2, 2, -1, 2.5, 0.4, 2.4), seed=5, drift=(0.02, 0.0, 0.05), size=0.006, color=(1, 0.7, 0.4), glow=4.0, step=10)
    cam = Cam(lens=55, fstop=2.2)
    cam.move([(a, (1.1, -3.4, 1.2), (0.1, 0, 1.15)), (b, (0.55, -1.75, 1.2), (0.05, 0, 1.15))])
    return (a, b)


@shot("demon")
def demon_shot(sc, preview):
    """1:04 The Demon King: 'I have waited ten thousand years.'"""
    a, b = 1, T.frames("demon")
    C.look((a, b), preview, haze=0.01, world=(0.003, 0.0015, 0.0015), glare=0.6, aniso=0.55)
    C.sky((1.0, 0.12, 0.02), (0.003, 0.002, 0.003), 0.8, 0.5)
    hell_floor()
    C.backdrop(150, width=800, height=170, strength=1.8, falloff=0.3)
    C.backdrop(-150, width=800, height=170, strength=1.4, falloff=0.3)
    r = random.Random(3)
    rock = mat("HellRock", (0.015, 0.01, 0.01), 0.8, bump=0.6, bump_scale=2)
    for i in range(16):
        x = r.choice((-1, 1)) * r.uniform(12, 40)
        prim("cone", "Spire%d" % i, (x, r.uniform(0, 60), 0), (r.uniform(2, 5), r.uniform(2, 5), r.uniform(8, 26)), rock, seg=7)
    d = make_demon((0, 20, 0), 1.0, 0.0)
    d.root.rotation_euler[2] = 0
    eye_glow(d, a, 30)
    # heroes below him, facing him
    ps = []
    for k, x, yy in (("velvet", -0.7, 3.4), ("vanilla", 0.0, 3.0), ("funfetti", 0.7, 3.3)):
        p = make_pop(k, k, (x, yy, 0), yaw=math.pi, seed=3 + int(x * 3), sprinkles=60)
        eyes_state(p, a, 1.0)
        idle(p, a, b, 0.0)
        ps.append(p)
    va = ps[1]
    # he looks down at them at 4.4 s
    for f, rx in ((a, -0.05), (secs(4.2), -0.05), (secs(5.0), 0.42), (b, 0.38)):
        d.head.rotation_euler[0] = rx
        d.head.keyframe_insert("rotation_euler", frame=f)
    _talk_lines("demon", {"d01": d, "d02": d, "d03": d, "v03": None} if False else {"d01": d, "d02": d, "d03": d, "v03": va})
    area("Fire", (0, 12, 1.5), (0, 3.5, 0.6), 90, (1.0, 0.3, 0.08), 6, 2)
    area("RimC", (6, 20, 12), (0, 20, 6), 900, COOL, 8, 4)
    area("Under", (0, 6, 0.3), (0, 20, 6), 350, (1.0, 0.35, 0.1), 6)
    area("HeroKey", (-2.5, 6.0, 2.0), (0, 3, 0.6), 45, (1.0, 0.55, 0.3), 1.5)
    ash(a, b, n=220, box=(-12, 12, -2, 30, 0.3, 16), seed=9, drift=(0.5, 0.4, 0.9), size=0.06, glow=3.0, step=4)
    cam = Cam(lens=26, fstop=4.0)
    t1, t2, t3, t4 = secs(1.0), secs(5.0), secs(6.6), secs(9.0)
    cam.shots([
        (a, t1, (0.0, -1.6, 0.45), (0, 20, 5.5), (0.0, -1.2, 0.55), (0, 20, 6.0)),
        (t1 + 1, t2, (-4.0, 9.5, 1.0), (0, 20, 10.0), (-3.4, 10.5, 1.2), (0, 20, 10.5)),
        (t2 + 1, t3, (1.6, 12.5, 6.6), (0, 18.8, 9.4), (1.3, 13.2, 6.7), (0, 18.8, 9.2)),
        (t3 + 1, t4, (0.5, 5.4, 0.5), (0.0, 3.0, 0.62), (0.45, 5.0, 0.52), (0.0, 3.0, 0.62)),
        (t4 + 1, b, (2.4, 12.2, 6.2), (0, 19.0, 8.8), (2.0, 12.8, 6.3), (0, 19.0, 8.6)),
    ])
    return (a, b)


# ------------------------------------------------------------ montage

def _dusty(a, b, seed=1, strength=2.6, hmax=24):
    C.sky((1.0, 0.2, 0.04), (0.006, 0.004, 0.005), 1.4, 0.45)
    dust_floor(200)
    C.backdrop(150, width=700, height=160, strength=strength, falloff=0.3)
    C.skyline(seed, 70, 40, 180, 50, 8, flick=(a, b), hmax=hmax)


@shot("walk")
def walk(sc, preview):
    """1:14 a slow-motion hopping hero walk, in sync."""
    a, b = 1, T.frames("walk")
    C.look((a, b), preview, haze=0.008, world=(0.008, 0.004, 0.004), glare=0.6, aniso=0.5)
    _dusty(a, b, 11, 3.2)
    ps = []
    for k, x, y in (("velvet", -1.0, 12.0), ("vanilla", 0.0, 11.0), ("funfetti", 1.0, 12.0)):
        p = make_pop(k, k, (x, y, 0), yaw=0.0, seed=7, sprinkles=70)
        eyes_state(p, a, 1.0)
        hop(p, a, [(x, y - 2.8), (x, y - 5.6), (x, y - 8.4)], air=17, rest=7, height=0.4)
        ps.append(p)
    sc.frame_set(a)
    for i, p in enumerate(ps):
        shed(p, sc, [secs(0.9), secs(1.9), secs(2.8)], per=6, wind=(0, -0.4, 0), fall_frames=34, seed=i)
    area("Back", (0, 30, 3), (0, 6, 0.8), 1500, (1.0, 0.3, 0.07), 10, 3)
    area("Rim", (4, 8, 2.5), (0, 6, 0.8), 170, COOL, 1.5, 3)
    area("Face", (-1.5, -1.5, 1.2), (0, 6, 0.7), 260, (1.0, 0.6, 0.35), 1.5)
    ash(a, b, n=150, box=(-6, 6, 0, 14, 0.1, 4), seed=3, drift=(-1.5, 0.5, 0.3), size=0.03, glow=3.0, step=4)
    cam = Cam(lens=32, fstop=2.2)
    cam.move([(a, (0.2, 3.0, 0.22), (0, 12, 0.7)), (b, (0.0, 1.0, 0.25), (0, 8, 0.8))])
    return (a, b)


def _sword(x, base_z, lean):
    steel = mat("Steel", (0.8, 0.82, 0.9), 0.15, metal=1.0)
    gold = mat("Hilt", (0.8, 0.6, 0.2), 0.3, metal=1.0)
    root = empty("Sword", (x, 0, base_z))
    prim("cube", "Blade", (0, 0, 0.55), (0.018, 0.004, 0.5), steel, root, smooth=False)
    prim("cone", "Tip", (0, 0, 1.08), (0.018, 0.004, 0.06), steel, root, seg=4, rot=(0, 0, 0))
    prim("cube", "Guard", (0, 0, 0.04), (0.09, 0.012, 0.012), gold, root, smooth=False)
    prim("cyl", "Grip", (0, 0, -0.08), (0.012, 0.012, 0.08), mat("Grip", (0.05, 0.02, 0.02), 0.6), root, seg=8)
    root.rotation_euler[1] = lean
    return root


@shot("sword")
def sword(sc, preview):
    """Funfetti 'draws' a sword that is only propped next to her, and it falls over."""
    a, b = 1, T.frames("sword")
    C.look((a, b), preview, haze=0.008, world=(0.008, 0.004, 0.004), glare=0.55, aniso=0.5)
    _dusty(a, b, 21, 3.0)
    p = make_pop("funfetti", "funfetti", (0.0, 4.0, 0), yaw=0.0, seed=4, sprinkles=70)
    eyes_state(p, a, 1.0)
    rockm = mat("Rock", (0.03, 0.025, 0.022), 0.85, bump=0.5, bump_scale=5)
    prim("sphere", "PropRock", (-0.95, 4.9, 0.16), (0.26, 0.2, 0.18), rockm, seg=12)
    sw = _sword(-0.6, 0.05, 0.34)
    # she lunges for it, 'draws', and the sword wobbles and falls over behind her
    f_l, f_d, f_fall = secs(0.5), secs(0.8), secs(1.05)
    hop(p, a, [(-0.2, 4.0)], air=6, rest=f_l - 2, height=0.12)
    for f, v in ((f_d - 6, 0.0), (f_d, -0.55), (f_d + 5, 0.15), (f_d + 10, 0.0)):
        p.pivot.rotation_euler[1] = v
        p.pivot.keyframe_insert("rotation_euler", frame=f)
    for f, ang in ((a, 0.34), (f_fall - 4, 0.34), (f_fall, 0.55), (f_fall + 8, 1.2), (f_fall + 11, 1.50), (f_fall + 13, 1.42), (f_fall + 16, 1.5)):
        sw.rotation_euler[1] = ang
        sw.keyframe_insert("rotation_euler", frame=f)
    for f, z in ((f_fall + 10, 0.05), (f_fall + 11, 0.02)):
        sw.location.z = z
        sw.keyframe_insert("location", frame=f)
    sc.frame_set(a)
    shed(p, sc, [f_d + 2, f_fall + 6], per=6, fall_frames=30, seed=2)
    area("Back", (-1, 22, 3), (0, 5, 0.8), 900, (1.0, 0.3, 0.07), 8, 3)
    area("Rim", (3, 7, 2.5), (0, 4, 0.8), 150, COOL, 1.5, 3)
    area("Key", (-1.8, 0.2, 1.4), (0, 4, 0.7), 110, (1.0, 0.6, 0.35), 1.2)
    ash(a, b, n=100, box=(-5, 5, 1, 10, 0.1, 3), seed=4, drift=(-1.0, 0.3, 0.3), size=0.025, glow=3.0, step=4)
    cam = Cam(lens=48, fstop=2.4)
    cam.move([(a, (0.5, 1.3, 0.42), (-0.2, 4.0, 0.6)), (b, (0.25, 1.9, 0.45), (-0.3, 4.0, 0.58))])
    return (a, b)


@shot("fly")
def fly(sc, preview):
    """A cake-pop flies through an explosion and lands stick-first in the dirt, quivering."""
    a, b = 1, T.frames("fly")
    C.look((a, b), preview, haze=0.008, world=(0.008, 0.004, 0.004), glare=0.7, aniso=0.5)
    _dusty(a, b, 31, 3.0)
    p = make_pop("vanilla", "vanilla", (0, 10, 0), yaw=0.0, seed=2, sprinkles=90)
    eyes_state(p, a, 1.0)
    x0, x1, N = -7.0, 2.0, 38
    for k in range(N + 1):
        t = k / N
        x = x0 + (x1 - x0) * t
        z = 0.4 + 4 * 2.6 * t * (1 - t) * 1.0 - (0.0 if k < N else 0.0)
        if k == N:
            z = 0.0
        p.root.location = (x, 10, z + 0.35 * (1 - t))
        p.root.rotation_euler = (0, -2 * math.pi * t * 1.15 - 0.4 * (1 - t), 0)
        p.root.keyframe_insert("location", frame=a + k)
        p.root.keyframe_insert("rotation_euler", frame=a + k)
    # lands stick-first: root sinks 0.22 m, rocks like a struck wire
    for k in range(1, 26):
        decay = math.exp(-k * 0.14)
        p.root.location = (x1, 10, -0.22 if k > 1 else -0.12)
        p.root.rotation_euler = (0, -2 * math.pi * 1.15 + 0.4 * 0 + 0.30 * decay * math.sin(k * 1.35), 0)
        p.root.keyframe_insert("location", frame=a + N + k)
        p.root.keyframe_insert("rotation_euler", frame=a + N + k)
    lin(p.root)
    sc.frame_set(a)
    shed(p, sc, [a + 9, a + 15, a + 22, a + N + 1, a + N + 2], per=8, wind=(1.0, 0, 0.5), fall_frames=30, seed=4)
    explosion(secs(0.35), Vector((-2.6, 12.6, 1.6)), 4.2, 30, strength=9)
    explosion(secs(0.55), Vector((-3.6, 13.0, 0.8)), 2.4, 22, seed=9, strength=7)
    area("Fill", (-2, 2, 1.8), (0, 10, 0.8), 90, (1.0, 0.5, 0.2), 2)
    area("Rim", (6, 14, 3), (0, 10, 0.8), 400, COOL, 2)
    cam = Cam(lens=36, fstop=3.2)
    ks = []
    for f in range(a, b + 1, 4):
        k = min(f - a, N)
        x = x0 + (x1 - x0) * k / N
        ks.append((f, (x * 0.55 + 0.5, 3.0, 0.9 + 0.9 * math.sin(math.pi * k / N)), (x * 0.9, 10, 0.7 + 1.0 * math.sin(math.pi * k / N))))
    cam.move(ks)
    return (a, b)


@shot("headbutt")
def headbutt(sc, preview):
    """Red Velvet hacks by headbutting the keyboard."""
    a, b = 1, T.frames("headbutt")
    C.look((a, b), preview, haze=0.012, world=(0.002, 0.003, 0.004), glare=0.5)
    mons, keys = control_room(a, b, 2)
    rv = make_pop("velvet", "velvet", (0.8, 0.0, 0), yaw=0.0, seed=3)
    eyes_state(rv, a, 1.0)
    # four butts at 0.4 s intervals; each tilts her onto the keys and back
    hits = [secs(0.35 + 0.4 * i) for i in range(5)]
    for f in hits:
        for dt, th in ((-4, 0.0), (0, 1.15), (3, 1.15), (6, 0.1), (9, 0.0)):
            rv.root.rotation_euler[0] = th
            rv.root.keyframe_insert("rotation_euler", frame=f + dt)
        eyes_state(rv, f - 1, 1.0)
        eyes_state(rv, f, 0.1)
        eyes_state(rv, f + 4, 1.0)
    lin(rv.root)
    r = random.Random(7)
    for i, k in enumerate(keys):
        for f in hits:
            for dt, z in ((-1, 0.036), (0, 0.02), (4, 0.036)):
                k.location.z = z
                k.keyframe_insert("location", frame=f + dt + r.randint(0, 1) * (i % 2))
    sc.frame_set(a)
    shed(rv, sc, [hits[1] + 1, hits[3] + 1], per=5, fall_frames=24, seed=1)
    # access granted
    ag = label("ACCESS GRANTED", (0.8, 3.9, 1.7), 0.35, color=(0.2, 1.0, 0.5), emit=0.0)
    em = ag.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    for f, v in ((a, 0.0), (hits[3], 0.0), (hits[3] + 1, 14.0), (b, 14.0)):
        em.default_value = v
        em.keyframe_insert("default_value", frame=f)
    area("Mon", (0.8, 2.5, 2.0), (0.8, 0, 0.5), 220, (0.3, 1.0, 0.8), 5, 2)
    area("Face", (0.2, -2.0, 1.2), (0.8, -0.2, 0.4), 22, (0.3, 0.8, 1.0), 1.2)
    cam = Cam(lens=38, fstop=3.2)
    ks = []
    r = random.Random(3)
    for f in range(a, b + 1, 2):
        ks.append((f, (2.3 + r.uniform(-0.02, 0.02), -2.2 + r.uniform(-0.02, 0.02), 0.55 + r.uniform(-0.02, 0.02)), (0.8, -0.3, 0.38)))
    cam.move(ks, "LINEAR")
    return (a, b)


@shot("roof")
def roof(sc, preview):
    """1:30 A rooftop in the rain: 'Promise me you'll come back.'"""
    a, b = 1, T.frames("roof")
    C.look((a, b), preview, haze=0.012, world=(0.004, 0.004, 0.007), glare=0.55, aniso=0.5)
    C.sky((0.9, 0.18, 0.05), (0.004, 0.004, 0.008), 1.0, 0.5)
    tar = mat("Tar", (0.02, 0.022, 0.028), 0.12, bump=0.1, bump_scale=8)
    C.floor(60, (0.02, 0.02, 0.025), 0.12, m=tar)
    prim("cube", "Parapet", (0, 3.4, 0.35), (9, 0.2, 0.35), mat("Para", (0.025, 0.025, 0.03), 0.6), smooth=False)
    C.backdrop(110, width=500, height=120, strength=2.4, falloff=0.3)
    C.skyline(41, 18, 40, 140, 60, 16, flick=(a, b), hmax=30)
    rv = make_pop("velvet", "velvet", (-0.55, 0.0, 0), yaw=-0.55, seed=3)
    va = make_pop("vanilla", "vanilla", (0.55, 0.0, 0), yaw=0.55, seed=2)
    for p in (rv, va):
        eyes_state(p, a, 1.0)
        idle(p, a, b, 0.0)
    blink(rv, secs(0.6)); blink(va, secs(3.4)); blink(va, secs(6.4))
    _talk_lines("roof", {"r03": rv, "v04": va})
    area("City", (0, 16, 3.0), (0, 0, 0.7), 1200, (1.0, 0.28, 0.08), 12, 3)
    area("Rain", (-2, -3, 3), (0, 0, 0.6), 60, COOL, 3)
    area("Face", (2.0, -2.5, 1.0), (0, 0, 0.6), 18, (1.0, 0.55, 0.3), 1.2)
    rain(a, b, n=420, box=(-5, 5, -3.5, 8, 0, 6), seed=5, length=0.5, speed=13.0, thick=0.0018, slant=0.15)
    cam = Cam(lens=42, fstop=2.8)
    t1, t2 = secs(1.1), secs(3.2)
    cam.shots([
        (a, t1, (0.5, -4.6, 0.8), (0, 0, 0.55), (0.35, -4.2, 0.8), (0, 0, 0.55)),
        (t1 + 1, t2, (-0.1, -1.7, 0.8), (-0.55, 0, 0.64), (-0.25, -1.45, 0.82), (-0.55, 0, 0.64)),
        (t2 + 1, b - 20, (0.9, -1.8, 0.78), (0.55, 0, 0.64), (0.75, -1.35, 0.8), (0.55, 0, 0.64)),
        (b - 19, b, (0.6, -4.0, 0.9), (0, 0, 0.55), (0.3, -4.6, 0.95), (0, 0, 0.55)),
    ])
    return (a, b)


# ------------------------------------------------------------ finale and title

def _hell_set(a, b, seed=2):
    C.sky((1.0, 0.1, 0.02), (0.004, 0.002, 0.003), 1.0, 0.5)
    hell_floor()
    C.backdrop(120, width=700, height=150, strength=1.0, falloff=0.22)
    r = random.Random(seed)
    fire = mat("HellFire", (1, 0.3, 0.05), 0.5, emit=(1.0, 0.07, 0.01), estr=0.9)
    for i in range(14):
        x = r.choice((-1, 1)) * r.uniform(2.5, 16)
        y = r.uniform(4, 40)
        h = r.uniform(3, 12)
        f = prim("cone", "HellFlame%d" % i, (x, y, h / 2), (r.uniform(0.6, 1.8), r.uniform(0.6, 1.8), h / 2), fire, seg=7)
        for fr in range(a, b + 1, 4):
            f.scale.z = h / 2 * (1 + 0.25 * math.sin(fr * 0.45 + i) + 0.1 * r.random())
            f.keyframe_insert("scale", frame=fr)
        lt = point("HellL%d" % i, (x, y - 1, h * 0.4), 450 if y > 15 else 160, (1.0, 0.28, 0.06), radius=0.6, shadow=False)
        flicker(lt, a, b, lt.data.energy, 0.3, 3, seed=i)


@shot("finale")
def finale(sc, preview):
    """1:36 hellfire; 'Let's sing'; the stage lights rise in hell."""
    a, b = 1, T.frames("finale")
    C.look((a, b), preview, haze=0.005, world=(0.004, 0.002, 0.003), glare=0.7, aniso=0.55)
    _hell_set(a, b)
    d = make_demon((0, 60, 0), 1.8, 0.0)
    eye_glow(d, a, 16)
    ps = []
    for k, x in (("velvet", -0.95), ("vanilla", 0.0), ("funfetti", 0.95)):
        y = 0.0 if k == "vanilla" else 0.25
        p = make_pop(k, k, (x, y, 0), yaw=0.0, seed=2 + int(x * 3), sprinkles=70)
        eyes_state(p, a, 1.0)
        idle(p, a, b, 0.0)
        ps.append(p)
    va = ps[1]
    blink(va, secs(0.7))
    _talk_lines("finale", {"v05": va})
    area("Face", (-0.6, -2.6, 0.9), (0, 0, 0.65), 40, (1.0, 0.5, 0.25), 1.2)
    area("RimF", (0, 6, 2.0), (0, 0, 0.7), 330, (1.0, 0.3, 0.08), 6, 2)
    # stage lights rise from the lava behind them, from 3.0 s
    cols = [(1.0, 0.2, 0.7), (0.2, 0.55, 1.0), (1.0, 0.9, 0.5), (0.6, 0.25, 1.0), (1.0, 0.2, 0.7), (0.2, 0.55, 1.0)]
    for i in range(10):
        x = -9 + i * 2.0
        L = spot("Rise%d" % i, (x, 9.0 + (i % 2) * 3, 0.2), (x * 0.4, 6, 0.5), 0.0, cols[i % 6], 22, 0.5, 0.2)
        for f, e, rx in ((a, 0, 95), (secs(3.0), 0, 95), (secs(4.2), 9000, 70), (secs(5.4), 26000, 52), (b, 36000, 45)):
            L.data.energy = e
            L.data.keyframe_insert("energy", frame=f)
            L.rotation_euler = (math.radians(rx), math.radians(10 * math.sin(i * 1.7)) * (1 if f > secs(4) else 0.3), 0)
            L.keyframe_insert("rotation_euler", frame=f)
    ash(a, b, n=220, box=(-8, 8, -2, 24, 0.2, 10), seed=6, drift=(0.3, 0.2, 1.1), size=0.04, glow=3.0, step=4)
    cam = Cam(lens=46, fstop=2.6)
    cam.move([(a, (0.4, -2.6, 0.55), (0, 0, 0.66)), (secs(3.0), (0.2, -1.5, 0.62), (0, 0, 0.66)),
              (b, (0.0, -4.6, 0.8), (0, 0, 0.9))])
    return (a, b)


@shot("title")
def title(sc, preview):
    """1:42 CAKE-POP DEMON HUNTERS."""
    a, b = 1, T.frames("title")
    C.look((a, b), preview, haze=0.007, world=(0.004, 0.002, 0.003), glare=0.9, aniso=0.55)
    _hell_set(a, b, 4)
    font = None
    for pth in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Impact.ttf"):
        try:
            font = bpy.data.fonts.load(pth)
            break
        except Exception:
            pass
    icing = mat("Icing", (1.0, 0.3, 0.5), 0.15, metal=0.1, coat=1.0, emit=(1.0, 0.2, 0.4), estr=1.0)
    gold = mat("Edge", (1.0, 0.75, 0.3), 0.2, metal=1.0, emit=(1.0, 0.6, 0.2), estr=0.3)
    texts = []
    for txt, z, size in (("CAKE-POP", 2.45, 1.25), ("DEMON HUNTERS", 1.25, 0.82)):
        cu = bpy.data.curves.new(txt, "FONT")
        cu.body = txt
        cu.size = size
        cu.align_x = "CENTER"
        cu.extrude = 0.09
        cu.bevel_depth = 0.012
        cu.bevel_resolution = 3
        if font:
            cu.font = font
        ob = C.link(bpy.data.objects.new(txt, cu))
        ob.location = (0, 9.0, z)
        ob.rotation_euler = (math.pi / 2, 0, 0)
        cu.materials.append(icing)
        cu.materials.append(gold)
        texts.append(ob)
    # slam: scale up and settle over the first 8 frames, then a slow drift
    for ob in texts:
        base = ob.location.copy()
        for f, s in ((a, 1.3), (a + 5, 0.97), (a + 10, 1.0), (b, 1.03)):
            ob.scale = (s, s, s)
            ob.keyframe_insert("scale", frame=f)
    sprinkle_rain(a, b, 260, (-7, 7, 2, 13, 0, 9), 3, 1.4)
    # beams rise behind the title
    cols = [(1.0, 0.2, 0.7), (0.2, 0.55, 1.0), (1.0, 0.9, 0.5), (0.6, 0.25, 1.0)]
    for i in range(8):
        x = -10 + i * 2.8
        spot("TB%d" % i, (x, 12, 0.2), (x * 0.5, 9, 6), 22000, cols[i % 4], 20, 0.5, 0.2)
    area("TitleKey", (-3, 1.0, 4.0), (0, 9, 2.0), 350, (1.0, 0.85, 0.8), 3)
    area("TitleRim", (4, 14, 5.0), (0, 9, 2.0), 600, (1.0, 0.4, 0.2), 4)
    flash = point("SlamFlash", (0, 6, 3), 0.0, (1.0, 0.8, 0.6), radius=0.5)
    for f, e in ((a, 90000), (a + 6, 5000), (a + 14, 0)):
        flash.data.energy = e
        flash.data.keyframe_insert("energy", frame=f)
    cam = Cam(lens=38, fstop=5.6)
    cam.move([(a, (0.0, 0.0, 2.2), (0, 9, 2.0)), (b, (0.0, 3.6, 2.2), (0, 9, 2.0))])
    return (a, b)


# ------------------------------------------------------------ stinger

@shot("stinger")
def stinger(sc, preview):
    """1:50 the demon catches Funfetti, sniffs her, eats her, chews: '...Needs salt.'"""
    a, b = 1, T.frames("stinger")
    C.look((a, b), preview, haze=0.004, world=(0.003, 0.0015, 0.0015), glare=0.6, aniso=0.55)
    C.sky((1.0, 0.12, 0.02), (0.003, 0.002, 0.003), 0.5, 0.5)
    hell_floor()
    C.backdrop(120, width=700, height=150, strength=0.9, falloff=0.25)
    S = 0.7
    d = make_demon((0, 12, 0), S, 0.0)
    eye_glow(d, a, 14)
    arm = d.arm["R"]
    # poses (shoulder x, elbow x) over time: the arm swings forward, the fist closes, the hand rises to the mouth
    P = [(a, 0.05, 0.0), (secs(0.8), -0.55, -0.35), (secs(1.7), -0.85, -0.5), (secs(2.2), -0.95, -0.55),
         (secs(3.1), -1.05, -1.35), (secs(3.9), -0.95, -2.35), (secs(4.8), -0.9, -2.55), (b, -0.9, -2.55)]
    for f, sh, el in P:
        arm["sh"].rotation_euler[0] = sh
        arm["sh"].keyframe_insert("rotation_euler", frame=f)
        arm["el"].rotation_euler[0] = el
        arm["el"].keyframe_insert("rotation_euler", frame=f)
    for f, c in ((a, 0.0), (secs(1.7), 0.0), (secs(2.2), 1.0), (b, 1.0)):
        curl(arm, f, c)
    # head: sniff forward at 3.4 s, jaw opens at 4.5 s, chews, then waits
    for f, y, rx in ((a, -0.2, -0.05), (secs(0.8), -0.2, 0.3), (secs(3.2), -0.2, 0.3), (secs(3.6), -1.3, 0.35), (secs(4.2), -1.3, 0.3),
                     (secs(4.8), -1.5, 0.22), (b, -1.5, 0.22)):
        d.head.location.y = y
        d.head.keyframe_insert("location", frame=f)
        d.head.rotation_euler[0] = rx
        d.head.keyframe_insert("rotation_euler", frame=f)
    j_open, j_close = secs(4.5), secs(5.0)
    d.jaw.rotation_euler[0] = 0
    d.jaw.keyframe_insert("rotation_euler", frame=j_open - 8)
    d.jaw.rotation_euler[0] = 0.85
    d.jaw.keyframe_insert("rotation_euler", frame=j_open)
    d.jaw.keyframe_insert("rotation_euler", frame=j_close - 4)
    t = j_close
    for i in range(4):
        d.jaw.rotation_euler[0] = 0.0
        d.jaw.keyframe_insert("rotation_euler", frame=t)
        d.jaw.rotation_euler[0] = 0.22
        d.jaw.keyframe_insert("rotation_euler", frame=t + 6)
        t += 11
    d.jaw.rotation_euler[0] = 0.0
    d.jaw.keyframe_insert("rotation_euler", frame=t)
    jaw_talk(d, secs(6.3), secs(6.3) + secs(T.line_dur("d04")), 0.12)
    # Funfetti stands where his hand will close, then rides in it
    p = make_pop("funfetti", "funfetti", (0, 0, 0), yaw=0.0, seed=4, sprinkles=70)
    eyes_state(p, a, 1.0)
    sc.frame_set(secs(2.2))
    bpy.context.view_layer.update()
    hp = arm["hand"].matrix_world.translation.copy()
    ground = Vector((hp.x, hp.y - 0.15, max(hp.z - 0.9 * S, 0.0)))
    rockh = ground.z
    prim("cyl", "Plinth", (ground.x, ground.y, rockh / 2), (0.9, 0.9, max(rockh / 2, 0.01)), mat("Plinth", (0.03, 0.02, 0.02), 0.8, bump=0.5, bump_scale=4), seg=10)
    p.root.location = ground
    p.root.keyframe_insert("location", frame=a)
    p.root.keyframe_insert("location", frame=secs(2.1))
    f_in = j_open + 2
    for f in range(secs(2.2), f_in + 1, 2):
        sc.frame_set(f)
        bpy.context.view_layer.update()
        h = arm["hand"].matrix_world.translation.copy()
        p.root.location = h + Vector((0.0, -0.05, -0.30 * S))
        p.root.keyframe_insert("location", frame=f)
        p.root.rotation_euler[0] = 0.0
    p.root.hide_render = False
    p.root.keyframe_insert("hide_render", frame=f_in - 1)
    for ob in [p.root] + list(p.root.children_recursive):
        ob.hide_render = False
        ob.keyframe_insert("hide_render", frame=f_in - 1)
        ob.hide_render = True
        ob.keyframe_insert("hide_render", frame=f_in)
    lin(p.root)
    sc.frame_set(a)
    shed(p, sc, [secs(2.5), secs(3.0)], per=6, floor_z=rockh, fall_frames=40, seed=2)
    # lights
    area("Fire", (0, 5, 1.2), (0, 12, 3), 90, (1.0, 0.3, 0.08), 6, 2)
    area("RimC", (6, 16, 9), (0, 12, 5), 1300, COOL, 8, 4)
    area("Face", (-2.5, 4.0, 3.5), (0, 11.5, 5.5), 70, (1.0, 0.55, 0.3), 3)
    ash(a, b, n=160, box=(-8, 8, 0, 20, 0.3, 12), seed=3, drift=(0.4, 0.3, 0.9), size=0.05, glow=3.0, step=4)
    # camera: wide, the grab, the sniff, the bite, the chew, the pause
    cam = Cam(lens=30, fstop=4.0)
    c1, c2, c3, c4, c5 = secs(1.9), secs(3.3), secs(4.4), secs(5.4), secs(6.2)

    def hw(f, ob):
        sc.frame_set(f)
        bpy.context.view_layer.update()
        return ob.matrix_world.translation.copy()

    ks = []
    # 1 wide: the whole demon, Funfetti small at his hand
    for f, loc, tgt in ((a, Vector((-6.0, 1.5, 1.3)), Vector((0.8, 12.0, 4.0))), (c1, Vector((-5.0, 2.0, 1.4)), Vector((0.8, 12.0, 4.2)))):
        ks.append((f, loc, tgt, f == c1))
    # 2 the held pop: fixed camera, target follows her
    pc = hw(c1 + 1, p.root) + Vector((0.0, 0.0, 0.5))
    camp = pc + Vector((-2.2, -3.2, 0.2))
    for f in range(c1 + 1, c2 + 1, 3):
        ks.append((f, camp, hw(f, p.root) + Vector((0, 0, 0.6)), f + 3 > c2))
    # 3 the sniff: close on the snout
    hc = hw(c2 + 1, d.head)
    for f, off, toff in ((c2 + 1, Vector((1.2, -4.6, 0.0)), Vector((0, -1.0, 0.0))), (c3, Vector((0.8, -3.6, -0.1)), Vector((0, -1.0, 0.0)))):
        h_ = hw(f, d.head)
        ks.append((f, h_ + off, h_ + toff, f == c3))
    # 4 the bite: the mouth opens, she goes in
    for f, off in ((c3 + 1, Vector((-2.6, -3.6, 0.2))), (c4, Vector((-2.2, -3.2, 0.2)))):
        h_ = hw(f, d.head)
        ks.append((f, h_ + off, h_ + Vector((0, -0.9, -0.5)), f == c4))
    # 5 chewing
    for f, off in ((c4 + 1, Vector((1.4, -3.6, -0.2))), (c5, Vector((1.0, -3.2, -0.2)))):
        h_ = hw(f, d.head)
        ks.append((f, h_ + off, h_ + Vector((0, -0.9, -0.6)), f == c5))
    # 6 the pause
    for f, off in ((c5 + 1, Vector((0.2, -3.6, -0.2))), (b, Vector((0.0, -2.9, -0.1)))):
        h_ = hw(f, d.head)
        ks.append((f, h_ + off, h_ + Vector((0, -0.9, -0.4)), f == b))
    for f, loc, tgt, last in ks:
        cam.ob.location = loc
        cam.tgt.location = tgt
        cam.ob.keyframe_insert("location", frame=f)
        cam.tgt.keyframe_insert("location", frame=f)
    ends = set(f for f, l, t, last in ks if last)
    for o in (cam.ob, cam.tgt):
        for fc in C._fcurves(o):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT" if int(round(kp.co.x)) in ends else "BEZIER"
    sc.frame_set(a)
    print("[stinger] head", hw(secs(3.0), d.head), "hand", hw(secs(2.2), arm["hand"]), "pop", hw(secs(2.2), p.root))
    return (a, b)


def _pos(sc, p, f):
    sc.frame_set(f)
    return p.root.matrix_world.translation.copy()


@shot("sprinkle")
def sprinkle(sc, preview):
    """One sprinkle drops through the bad.llc ident's last frame (transparent, composited in the edit)."""
    a, b = 1, secs(1.2)
    C.look((a, b), preview, haze=0.0, world=(0, 0, 0), glare=0.3)
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = "RGBA"
    m = mat("Spr", (1.0, 0.25, 0.5), 0.3, coat=1.0, emit=(1.0, 0.3, 0.5), estr=0.6)
    s = prim("sphere", "OneSprinkle", (0.25, 0, 3.0), (0.012, 0.012, 0.045), m, seg=12)
    for k in range(0, b - a + 1, 2):
        t = k / (b - a)
        s.location = (0.25 - 0.05 * t, 0, 1.6 - 3.4 * t * t - 0.4 * t)
        s.rotation_euler = (0.4 + t * 6.0, 0.3, 0.8 + t * 3)
        s.keyframe_insert("location", frame=a + k)
        s.keyframe_insert("rotation_euler", frame=a + k)
    lin(s)
    area("K", (-1.5, -2.5, 1.5), (0.2, 0, 0.8), 80, (1, 0.9, 0.85), 1)
    area("R", (2, 1.5, 2.5), (0.2, 0, 0.8), 60, COOL, 1)
    cam = Cam(lens=40, fstop=8.0, dof=False)
    cam.move([(a, (0.0, -3.4, 0.8), (0.1, 0, 0.8))])
    return (a, b)
