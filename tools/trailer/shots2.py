"""Shots, part two: the cold open, the team, the stage (BAD-857)."""

import math
import random

import bpy
from mathutils import Vector

import chars
import common as C
import timeline as T
from common import COOL, FPS, HELL, WARM, Cam, area, ash, aim, empty, explosion, flicker, lin, mat, point, prim, rain, spot
from chars import (blink, curl, eye_glow, eyes_state, hop, idle, jaw_talk, make_demon, make_pop, shed, squash, talk)
from shots import SHOTS, dust_floor, label, secs, shot


def _talk_lines(shot_name, who):
    """Flap the mouth (or the demon's jaw) for this shot's lines; who = {line id: pop or demon}."""
    for lid, off in T.lines(shot_name):
        if lid in who:
            f0 = secs(off)
            f1 = f0 + secs(T.line_dur(lid))
            t = who[lid]
            if hasattr(t, "jaw"):
                jaw_talk(t, f0, f1)
            else:
                talk(t, f0, f1, seed=hash(lid) % 50)


# ------------------------------------------------------------ cold open

@shot("city")
def city(sc, preview):
    """0:08 black, drone, a city on fire, ash."""
    a, b = 1, T.frames("city")
    C.look((a, b), preview, haze=0.014, world=(0.004, 0.002, 0.002), glare=0.55, aniso=0.55)
    C.sky((1.0, 0.1, 0.02), (0.003, 0.002, 0.003), 1.2, 0.5)
    C.floor(300, (0.01, 0.008, 0.008), 0.3)
    C.backdrop(160, width=800, height=170, strength=2.6, falloff=0.22)
    C.avenue(2, 8, 110, 9.0, 30, 18, (a, b))
    C.skyline(5, 115, 35, 220, 40, 10, flick=(a, b), hmax=26)
    area("Glow", (0, 40, 20), (0, 0, 2), 9000, (1.0, 0.2, 0.05), 40, 10)
    area("Cool", (-6, -8, 10), (0, 20, 5), 500, COOL, 6)
    ash(a, b, n=300, box=(-14, 14, 0, 60, 0.3, 22), seed=4, drift=(0.8, 0.4, -0.7), size=0.05, glow=2.0, step=4)
    cam = Cam(lens=32, fstop=5.6)
    cam.move([(a, (0.0, -2.0, 1.5), (0, 60, 7.0)), (b, (0.5, 14.0, 2.4), (0, 90, 10.0))])
    # fade up from black
    return (a, b)


@shot("horns")
def horns(sc, preview):
    """0:14 a 40-foot horned shape in the smoke."""
    a, b = 1, T.frames("horns")
    C.look((a, b), preview, haze=0.006, world=(0.003, 0.002, 0.002), glare=0.6, aniso=0.6)
    C.sky((1.0, 0.12, 0.02), (0.003, 0.002, 0.003), 1.0, 0.45)
    C.floor(400, (0.01, 0.008, 0.008), 0.35)
    C.backdrop(110, width=900, height=160, strength=3.2, falloff=0.25)
    C.avenue(7, 8, 66, 10.0, 22, 8, (a, b))
    d = make_demon((0, 75, 0), 1.25, 0.0)
    d.head.rotation_euler = (0.08, 0, 0)
    eye_glow(d, a, 0.0)
    eye_glow(d, secs(2.2), 0.0)
    eye_glow(d, secs(3.4), 30.0)
    eye_glow(d, b, 50.0)
    # smoke banks between us and it
    for i, (x, y, sx, sz) in enumerate(((0, 50, 60, 10), (-25, 62, 30, 14), (30, 60, 35, 12), (0, 85, 70, 20))):
        s = prim("cube", "Smoke%d" % i, (x, y, sz * 0.8), (sx, 18, sz), C.volume_smoke("Smoke%d" % i, 0.05, (0.05, 0.04, 0.04), 0.06), smooth=False)
    area("Glow", (0, 40, 15), (0, 75, 8), 1500, (1.0, 0.2, 0.05), 60, 10)
    ash(a, b, n=260, box=(-14, 14, 0, 70, 0.3, 24), seed=8, drift=(0.7, 0.3, -0.6), size=0.05, glow=2.0, step=4)
    cam = Cam(lens=55, fstop=6.0)
    cam.move([(a, (0.0, 4.0, 1.7), (0, 75, 11.5)), (b, (0.0, 22.0, 2.0), (0, 75, 12.5))])
    return (a, b)


# ------------------------------------------------------------ the team

def control_room(a, b, seed=1):
    """The war room: a monitor wall, a long desk, a keyboard."""
    r = random.Random(seed)
    C.floor(40, (0.015, 0.016, 0.02), 0.25)
    prim("plane", "WallBack", (0, 4.5, 3.0), (14, 3.2, 1), mat("Wall", (0.012, 0.014, 0.018), 0.8), rot=(math.pi / 2, 0, 0), smooth=False)
    cols = [(0.1, 1.0, 0.55), (0.15, 0.7, 1.0), (1.0, 0.7, 0.15), (0.2, 1.0, 0.9), (1.0, 0.2, 0.15)]
    mons = []
    for i in range(9):
        for j in range(4):
            col = r.choice(cols[:4]) if r.random() < 0.92 else cols[4]
            m = mat("Mon%d_%d" % (i, j), (0.01, 0.01, 0.01), 0.3, emit=col, estr=0.12)
            prim("plane", "Mon%d_%d" % (i, j), (-4.4 + i * 1.1, 4.4, 0.9 + j * 0.78), (0.44, 0.28, 1), m, rot=(math.pi / 2, 0, 0), smooth=False)
            nd = m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
            for f in range(a, b + 1, 5):
                nd.default_value = r.uniform(0.015, 0.1)
                nd.keyframe_insert("default_value", frame=f)
            mons.append(m)
    # keyboard
    kb = mat("Keys", (0.02, 0.02, 0.025), 0.4, emit=(0.2, 0.6, 1.0), estr=0.25)
    base = prim("cube", "KbBase", (0.8, -0.45, 0.015), (0.4, 0.14, 0.015), mat("KbBase", (0.015, 0.015, 0.02), 0.5), smooth=False)
    keys = []
    for row in range(4):
        for col in range(13):
            k = prim("cube", "Key", (0.8 - 0.36 + col * 0.06, -0.45 - 0.09 + row * 0.06, 0.036), (0.022, 0.022, 0.016), kb, smooth=False)
            keys.append(k)
    return mons, keys


@shot("velvet")
def velvet(sc, preview):
    """0:35 Red Velvet (brains), lit by a monitor wall."""
    a, b = 1, T.frames("velvet")
    C.look((a, b), preview, haze=0.012, world=(0.002, 0.003, 0.004), glare=0.45)
    control_room(a, b, 1)
    rv = make_pop("velvet", "velvet", (-0.35, 0, 0), yaw=0.15, seed=3)
    va = make_pop("vanilla", "vanilla", (0.8, -0.2, 0), yaw=-0.4, seed=2)
    for p in (rv, va):
        eyes_state(p, a, 1.0)
        idle(p, a, b, 0.0)
    blink(rv, secs(2.0)); blink(va, secs(5.6))
    _talk_lines("velvet", {"r01": rv, "r02": rv, "v02": va})
    area("Mon", (0, 2.5, 2.2), (0, 0, 0.6), 260, (0.3, 1.0, 0.8), 6, 2.4)
    area("Face", (-0.2, -2.6, 1.0), (-0.35, 0, 0.6), 22, (0.3, 0.8, 1.0), 1.2)
    area("RimW", (2.8, 1.0, 2.0), (0, 0, 0.6), 160, (1.0, 0.5, 0.25), 1.5)
    cam = Cam(lens=42, fstop=2.8)
    w1, w2 = secs(0.5), secs(4.3)
    w3, w4 = secs(6.6), secs(8.0)
    cam.shots([
        (a, w1, (1.2, -4.2, 1.15), (0.2, 0, 0.6), (1.0, -4.0, 1.1), (0.2, 0, 0.6)),
        (w1 + 1, w2, (-0.1, -1.9, 0.85), (-0.35, 0, 0.62), (-0.3, -1.6, 0.84), (-0.35, 0, 0.62)),
        (w2 + 1, w3, (0.6, -2.0, 0.82), (0.8, -0.2, 0.64), (0.78, -1.7, 0.82), (0.8, -0.2, 0.64)),
        (w3 + 1, w4, (-0.1, -1.7, 0.85), (-0.35, 0, 0.62), (-0.25, -1.45, 0.85), (-0.35, 0, 0.62)),
        (w4 + 1, b, (1.4, -4.4, 1.2), (0.2, 0, 0.6), (1.2, -4.1, 1.15), (0.2, 0, 0.6)),
    ])
    ash(a, b, n=40, box=(-3, 3, -1, 3, 0.2, 3), seed=1, drift=(0, 0, 0.1), size=0.006, color=(0.4, 0.9, 1.0), glow=3.0, step=8)
    return (a, b)


@shot("funfetti")
def funfetti(sc, preview):
    """0:42 Funfetti (loose cannon) walks away from an explosion."""
    a, b = 1, T.frames("funfetti")
    C.look((a, b), preview, haze=0.006, world=(0.008, 0.004, 0.004), glare=0.55, aniso=0.5)
    C.sky((1.0, 0.2, 0.04), (0.006, 0.004, 0.005), 1.4, 0.45)
    dust_floor(200)
    C.backdrop(150, width=700, height=160, strength=2.6, falloff=0.3)
    C.skyline(9, 70, 40, 180, 50, 8, flick=(a, b), hmax=24)
    p = make_pop("funfetti", "funfetti", (0.0, 7.0, 0), yaw=0.0, seed=4, sprinkles=90)
    eyes_state(p, a, 1.0)
    # the blast goes off behind her at 0.9 s; she does not turn around
    t0 = secs(0.9)
    explosion(t0, Vector((0.5, 20.0, 1.5)), 5.5, 26, strength=40)
    end = hop(p, secs(1.4), [(0.0, 5.4), (0.2, 3.8), (0.0, 2.4)], air=11, rest=8, height=0.28)
    landings = [secs(1.4) + 8 * (i + 1) + 11 * (i + 1) + 3 * i for i in range(3)]
    sc.frame_set(a)
    shed(p, sc, landings + [secs(1.4) + 12], per=7, wind=(0, 0.6, 0), fall_frames=34, seed=5)
    talk(p, secs(2.2), secs(2.2) + secs(T.line_dur("f01")), seed=9)
    area("Blast", (0.5, 8.0, 2.5), (0, 7, 0.6), 1.0, (1.0, 0.5, 0.2), 2)
    L = point("BlastRim", (0.5, 11.0, 1.4), 0.0, (1.0, 0.45, 0.15), radius=0.5, shadow=False)
    for f, e in ((a, 0), (t0, 0), (t0 + 2, 2500), (t0 + 14, 600), (b, 250)):
        L.data.energy = e
        L.data.keyframe_insert("energy", frame=f)
    area("Face", (-0.8, 0.8, 0.9), (0, 5, 0.7), 120, (1.0, 0.65, 0.4), 1.2)
    ash(a, b, n=200, box=(-8, 8, 0, 18, 0.2, 7), seed=7, drift=(-0.5, -1.2, 0.9), size=0.03, glow=2.5, step=4)
    cam = Cam(lens=40, fstop=2.6)
    cam.move([(a, (0.5, 3.6, 0.35), (0, 7.0, 0.85)), (b, (0.3, -2.0, 0.45), (0, 2.5, 0.75))])
    import fire as FX
    FX.shake(cam, t0, t0 + 50, 0.14, seed=1)
    return (a, b)


@shot("stage")
def stage(sc, preview):
    """0:48 day job: a K-pop stage and a sea of lightsticks."""
    a, b = 1, T.frames("stage")
    C.look((a, b), preview, haze=0.006, world=(0.002, 0.001, 0.004), glare=0.7, aniso=0.6, exposure=-0.2)
    C.floor(200, (0.01, 0.01, 0.014), 0.15)
    # stage: a glossy deck, an LED wall
    prim("cube", "Deck", (0, 9, 0.4), (6.5, 3.6, 0.4), mat("Deck", (0.02, 0.02, 0.03), 0.12, coat=0.4), smooth=False)
    wall = mat("LED", (0.01, 0.01, 0.01), 0.3, emit=(1.0, 0.1, 0.5), estr=0.04)
    prim("plane", "LEDWall", (0, 12.8, 5.0), (7.5, 4.6, 1), wall, rot=(math.pi / 2, 0, 0), smooth=False)
    nd = wall.node_tree.nodes["Principled BSDF"].inputs["Emission Color"]
    for f, col in ((a, (1.0, 0.25, 0.7)), (secs(1.5), (0.3, 0.5, 1.0)), (secs(3), (1.0, 0.5, 0.9)), (b, (0.6, 0.3, 1.0))):
        nd.default_value = (col[0], col[1], col[2], 1)
        nd.keyframe_insert("default_value", frame=f)
    # the three heroes on the deck
    ps = []
    for i, (k, x) in enumerate((("velvet", -1.2), ("vanilla", 0.0), ("funfetti", 1.2))):
        p = make_pop(k, k, (x * 1.3, 9.0, 0.8), yaw=0.0, scale=1.9, seed=i + 1, sprinkles=60)
        eyes_state(p, a, 1.0)
        ps.append(p)
    # they bounce to the beat (0.5 s)
    for i, p in enumerate(ps):
        hop(p, a, [(p.root.location.x, 9.0)] * 10, air=8, rest=4, height=0.3)
    sc.frame_set(a)
    shed(ps[1], sc, range(secs(1.5), b, 7), floor_z=0.8, per=3, fall_frames=24, seed=3)
    # truss lights
    cols = [(1.0, 0.2, 0.7), (0.2, 0.5, 1.0), (1.0, 0.85, 0.3), (0.5, 0.2, 1.0)]
    for i in range(8):
        x = -7 + i * 2.0
        L = spot("Beam%d" % i, (x, 11.5, 8.5), (x * 0.3, 5 + (i % 3) * 2, 1.0), 14000, cols[i % 4], 26, 0.5, 0.2)
        for f in range(a, b + 1, 6):
            L.rotation_euler = (math.radians(100 + 12 * math.sin(f * 0.07 + i)), math.radians(8 * math.cos(f * 0.05 + i * 2)), 0)
            L.keyframe_insert("rotation_euler", frame=f)
    area("Spot", (0, 3, 6), (0, 9, 1.2), 250, (1.0, 0.85, 0.8), 2)
    # the crowd: heads and lightsticks
    r = random.Random(12)
    head = mat("Head", (0.004, 0.004, 0.005), 0.9)
    stickc = [mat("Stick%d" % i, (0.02, 0.02, 0.02), 0.4, emit=c, estr=8.0) for i, c in enumerate(cols + [(0.3, 1.0, 0.6), (1.0, 0.3, 0.3)])]
    for row in range(9):
        for k in range(36):
            x = -9.5 + k * 0.55 + r.uniform(-0.2, 0.2) + (row % 2) * 0.27
            y = 0.2 + row * 0.95
            h = r.uniform(0.0, 0.1)
            prim("sphere", "Fan", (x, y, 1.05 + h), (0.13, 0.13, 0.17), head, seg=8)
            if r.random() < 0.8:
                s = prim("cyl", "LStick", (x + 0.15, y, 1.6 + h), (0.013, 0.013, 0.2), r.choice(stickc), seg=6)
                ph = r.uniform(0, 6.28)
                dr = s.driver_add("rotation_euler", 1)
                dr.driver.expression = "sin(frame*0.33+%.2f)*0.35" % ph
                dz = s.driver_add("location", 2)
                dz.driver.expression = "%.2f+sin(frame*0.33+%.2f)*0.05" % (1.6 + h, ph)
    cam = Cam(lens=32, fstop=2.8)
    cam.move([(a, (0.8, 0.0, 1.9), (0, 9, 1.9)), (b, (0.2, 2.0, 2.3), (0, 9, 1.8))])
    return (a, b)
