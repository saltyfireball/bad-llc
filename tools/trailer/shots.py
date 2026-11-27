"""Shot builders for Cake-Pop Demon Hunters (BAD-857).

build(shot_id, preview) -> (scene, (first_frame, last_frame)). 24 fps.
Every shot resets the scene, lights it with the ident's look (warm practical,
cool rim, haze), keys it and returns. Timeline times are in edit.py.
"""

import math
import random

import bpy
from mathutils import Vector

import chars
import common as C
import timeline as T
from common import COOL, FPS, HELL, WARM, Cam, area, ash, aim, empty, ease, explosion, flicker, lin, mat, point, prim, rain, spot
from chars import make_pop, make_demon, hop, talk, shed, idle, blink, eyes_state, squash, curl

SHOTS = {}


def shot(name):
    def deco(fn):
        SHOTS[name] = fn
        return fn
    return deco


def build(name, preview=False):
    C._proto.clear()
    sc = C.reset()
    frames = SHOTS[name](sc, preview)
    sc.frame_set(frames[0])
    return sc, frames


def secs(s):
    return int(round(s * FPS))


def label(text, loc, size=0.1, color=(0.9, 0.88, 0.82), rot=(math.pi / 2, 0, 0), emit=1.0, align="CENTER"):
    cu = bpy.data.curves.new("txt", "FONT")
    cu.body = text
    cu.size = size
    cu.align_x = align
    ob = C.link(bpy.data.objects.new("txt", cu))
    ob.location = loc
    ob.rotation_euler = rot
    ob.data.materials.append(mat("txt", color, 0.6, emit=color, estr=emit))
    return ob


def dust_floor(size=80, color=(0.05, 0.035, 0.03)):
    return C.floor(size, color, 0.85, m=mat("Dirt", color, 0.9, bump=0.5, bump_scale=3.0))


# ------------------------------------------------------------ design sheets

@shot("sheet_heroes")
def sheet_heroes(sc, preview):
    C.look((1, 1), preview, haze=0.0, world=(0.01, 0.01, 0.013), glare=0.2, exposure=-0.4)
    C.floor(40, (0.05, 0.05, 0.055), 0.5)
    back = prim("plane", "Back", (0, 3, 2), (30, 1, 6), mat("BackWall", (0.04, 0.04, 0.05), 0.9), rot=(math.pi / 2, 0, 0), smooth=False)
    pops = []
    for i, (nm, k) in enumerate((("VANILLA", "vanilla"), ("RED VELVET", "velvet"), ("FUNFETTI", "funfetti"), ("GRANDMASTER CRUMB", "crumb"))):
        x = -1.65 + i * 1.1 + (0.15 if i == 3 else 0)
        p = make_pop(k, k, (x, 0, 0), yaw=0.0, seed=i + 1)
        label(nm, (x, -0.05, -0.17), 0.07, emit=1.0)
        pops.append(p)
    area("Key", (-2.5, -3.5, 3.0), (0, 0, 0.5), 260, WARM, 2.0)
    area("Rim", (3.0, 2.0, 2.5), (0, 0, 0.5), 350, COOL, 1.5, 2.5)
    area("Fill", (2.5, -4, 1.5), (0, 0, 0.5), 120, (0.85, 0.9, 1.0), 3.0)
    cam = Cam(lens=50, fstop=8.0)
    cam.move([(1, (0.0, -6.8, 0.95), (0, 0, 0.55))])
    label("CAKE-POP DEMON HUNTERS - HEROES", (0, 0, 1.75), 0.09, color=(0.8, 0.75, 0.6), emit=0.6)
    return (1, 1)


@shot("sheet_demon")
def sheet_demon(sc, preview):
    C.look((1, 1), preview, haze=0.0012, world=(0.002, 0.0015, 0.002), glare=0.4, exposure=-0.3)
    C.floor(120, (0.02, 0.012, 0.012), 0.6, m=C.lava_mat("DemonFloor", (0.02, 0.012, 0.012), scale=0.5, strength=4))
    d = make_demon((0, 0, 0), 1.0)
    d.head.rotation_euler = (0.18, 0, 0)
    d.jaw.rotation_euler = (0.25, 0, 0)
    for side in "LR":
        d.arm[side]["sh"].rotation_euler = (0.1, 0, 0.0)
        curl(d.arm[side], 1, 0.5)
    area("Rim", (14, 14, 18), (0, 0, 6), 9000, COOL, 8, 12)
    area("RimL", (-14, 12, 10), (0, 0, 6), 6000, (1.0, 0.4, 0.15), 8, 12)
    area("Key", (0, -22, 6), (0, 0, 9), 2500, (1.0, 0.45, 0.2), 10, 8)
    cam = Cam(lens=45, fstop=11.0)
    cam.move([(1, (0, -46, 6.2), (0, 0, 6.2))])
    label("THE DEMON KING", (0, -3, 0.0), 1.2, color=(1.0, 0.45, 0.2), emit=2.0, rot=(math.pi / 2, 0, 0))
    return (1, 1)


# ------------------------------------------------------------ style test shots

@shot("bakery")
def bakery(sc, preview):
    """0:19 slow push-in through rain on a bakery window to three cake-pops in a foam block."""
    return _bakery(sc, preview, 1, T.frames("bakery"), "push")


@shot("eyes")
def eyes(sc, preview):
    """0:25 silence, one cake-pop opens its eyes."""
    return _bakery(sc, preview, 1, T.frames("eyes"), "eyes")


def _bakery(sc, preview, a, b, mode):
    C.look((a, b), preview, haze=0.01, world=(0.005, 0.006, 0.01), glare=0.45)
    # inside: shelf, foam block, wall
    wall = mat("Wall", (0.2, 0.09, 0.11), 0.8, bump=0.05, bump_scale=30)
    prim("plane", "WallBack", (0, 2.4, 1.5), (8, 1, 3), wall, rot=(math.pi / 2, 0, 0), smooth=False)
    prim("cube", "Shelf", (0, 0.9, 0.12), (1.3, 0.55, 0.12), mat("Wood", (0.12, 0.06, 0.03), 0.5, bump=0.1, bump_scale=18), smooth=False)
    prim("cube", "Counter", (0, 1.6, 0.0), (4, 1.6, 0.14), mat("Counter", (0.25, 0.2, 0.18), 0.25), smooth=False)
    foam = mat("Foam", (0.6, 0.6, 0.58), 0.95, bump=0.8, bump_scale=300)
    prim("cube", "FoamBlock", (0, 0.9, 0.32), (0.5, 0.16, 0.09), foam, smooth=False)
    pops = []
    for i, (k, x) in enumerate((("vanilla", -0.32), ("velvet", 0.0), ("funfetti", 0.32))):
        p = make_pop(k, k, (x, 0.9, 0.34), yaw=0.0, scale=0.55, sprinkles=50, seed=i + 5)
        eyes_state(p, 1, 0.04)
        if mode == "eyes" and k == "vanilla":
            for f, o in ((secs(1.6), 0.04), (secs(1.6) + 3, 0.5), (secs(1.6) + 6, 0.5), (secs(1.6) + 12, 1.0)):
                eyes_state(p, f, o)
        pops.append(p)
    # shelves of other pastries as warm bokeh
    r = random.Random(4)
    glowm = mat("Glow", (1, 0.7, 0.4), 0.5, emit=(1.0, 0.65, 0.3), estr=1.2)
    for i in range(26):
        prim("sphere", "Bokeh%d" % i, (r.uniform(-3, 3), r.uniform(2.0, 2.3), r.uniform(0.3, 2.6)), (0.04,) * 3, glowm, seg=8)
    label("OPEN", (-0.62, 0.15, 1.45), 0.18, color=(1.0, 0.25, 0.55), emit=18)
    # the glass and its drops
    glass = mat("Glass", (0.9, 0.95, 1.0), 0.04, alpha=0.06, spec=1.0)
    gl = prim("plane", "Glass", (0, 0, 1.0), (3.2, 1, 1.6), glass, rot=(math.pi / 2, 0, 0), smooth=False)
    r = random.Random(9)
    drop = mat("Drop", (0.85, 0.9, 1.0), 0.02, alpha=0.28, spec=1.0)
    for i in range(160):
        x, z = r.uniform(-0.9, 0.9), r.uniform(0.15, 1.5)
        s = r.uniform(0.006, 0.026)
        o = prim("sphere", "Drip%d" % i, (x, -0.006, z), (s, s * 0.5, s * 1.25), drop, seg=12)
        if r.random() < 0.4:
            z2 = z - r.uniform(0.2, 0.6)
            o.location.z = z
            o.keyframe_insert("location", frame=a)
            o.location.z = max(0.05, z2)
            o.keyframe_insert("location", frame=b)
            lin(o)
    # light: the bakery's warm bulb, street cool, fire glow far right
    point("Bulb", (0.0, 0.5, 1.35), 70, (1.0, 0.7, 0.4), radius=0.1)
    area("Street", (-3.0, -3.5, 2.5), (0, 0.9, 0.6), 110, COOL, 1.5)
    area("FireGlow", (4.5, -2.0, 2.0), (0, 0.9, 0.6), 90, (1.0, 0.35, 0.1), 1.5)
    area("Under", (0, 0.4, 0.9), (0, 0.9, 0.35), 8, (1.0, 0.8, 0.6), 0.8)
    rain(a, b, n=150, box=(-1.4, 1.4, -2.0, -0.12, 0.0, 2.4), seed=3, length=0.22, speed=9.0, thick=0.0012, slant=0.1)
    if mode == "push":
        cam = Cam(lens=45, fstop=3.5)
        cam.move([(a, (0.15, -3.2, 1.25), (0.0, 0.0, 1.0)),
                  (b, (0.0, -0.55, 0.62), (0.0, 0.9, 0.58))])
    else:
        cam = Cam(lens=75, fstop=2.8)
        cam.move([(a, (-0.18, -0.55, 0.62), (-0.32, 0.9, 0.64)),
                  (b, (-0.24, -0.45, 0.64), (-0.32, 0.9, 0.64))])
    return (a, b)


@shot("vanilla")
def vanilla_card(sc, preview):
    """0:30 Vanilla, the leader: wind blowing with nothing to blow."""
    a, b = 1, T.frames("vanilla")
    C.look((a, b), preview, haze=0.004, world=(0.01, 0.005, 0.004), glare=0.5, aniso=0.5)
    C.sky((1.0, 0.22, 0.05), (0.01, 0.004, 0.006), 1.6, 0.45)
    dust_floor()
    C.backdrop(150, width=700, height=170, strength=3.4, falloff=0.28)
    C.skyline(3, 85, 45, 200, 60, 12, flick=(a, b), hmax=22)
    p = make_pop("vanilla", "vanilla", (0, 0, 0), yaw=0.0, seed=2)
    idle(p, a, b, sway=0.0)
    eyes_state(p, a, 1.0)
    blink(p, secs(1.4))
    talk(p, secs(2.4), secs(4.4), seed=1)
    # hell on the horizon behind, cool rim from the side, a kick of warm on her face
    area("Horizon", (-3, 14, 3.5), (0, 0, 0.7), 250, (1.0, 0.3, 0.07), 14, 5)
    area("Rim", (4, 3, 2.5), (0, 0, 0.7), 450, COOL, 1.5, 2.5)
    area("Face", (-1.5, -3.5, 1.2), (0, 0, 0.7), 90, (1.0, 0.6, 0.35), 1.2)
    for i, (x, h) in enumerate(((-5, 6), (-2.5, 9), (3, 7), (6, 11), (1, 5))):
        prim("cone", "Spire%d" % i, (x * 2.2, 22 + i * 3, h / 2), (1.6, 1.6, h), mat("Spire", (0.01, 0.008, 0.008), 0.9), seg=7)
    # the wind: it moves everything but her
    ash(a, b, n=320, box=(-9, 9, -3, 6, 0.0, 4.0), seed=2, drift=(-9.0, 0.5, 0.2), size=0.035, glow=3.0, step=3)
    cam = Cam(lens=38, fstop=2.4)
    cam.move([(a, (0.5, -3.6, 0.3), (0, 0, 0.78)), (b, (0.25, -2.5, 0.38), (0, 0, 0.8))])
    return (a, b)


@shot("rolldown")
def rolldown(sc, preview):
    """1:14 Vanilla gets knocked over and rolls downhill, still serious."""
    a, b = 1, T.frames("rolldown")
    C.look((a, b), preview, haze=0.01, world=(0.01, 0.006, 0.006), glare=0.45, exposure=0.7)
    C.sky((1.0, 0.25, 0.06), (0.01, 0.005, 0.006), 1.5, 0.5)
    tilt = math.radians(17)
    hill = prim("plane", "Hill", (0, 0, 0), (60, 60, 1), mat("Hillside", (0.05, 0.04, 0.03), 0.9, bump=0.6, bump_scale=2.5), smooth=False)
    hill.rotation_euler = (0, tilt, 0)       # falls toward +X
    area("Sun", (-18, 14, 12), (0, 0, 0), 9000, (1.0, 0.4, 0.12), 10, 6)
    area("Rim", (20, 10, 8), (0, 0, 0), 1700, COOL, 8, 8)
    area("Fill", (0, -12, 6), (0, 0, 0), 1000, (0.8, 0.85, 1.0), 6)
    r = random.Random(6)
    for i in range(30):
        x, y = r.uniform(-14, 22), r.uniform(-6, 12)
        if abs(y) < 1.6:
            continue
        s = r.uniform(0.2, 0.7)
        prim("sphere", "Rock%d" % i, (x, y, -x * math.tan(tilt) + s * 0.3), (s, s, s * 0.7), mat("Rock", (0.04, 0.035, 0.03), 0.9, bump=0.5, bump_scale=6), seg=10)
    p = make_pop("vanilla", "vanilla", (0, 0, 0), yaw=0.0, seed=2, sprinkles=80)
    eyes_state(p, a, 1.0)
    dirv = Vector((math.cos(tilt), 0, -math.sin(tilt)))
    start = Vector((-4.0, 0, 4.0 * math.tan(tilt)))
    from mathutils import Euler, Matrix
    pivot_off = Vector((0, 0, chars.BALL_Z))
    N = b - a
    for f in range(a, b + 1):
        t = (f - a) / FPS
        s_ = 0.25 * 9.8 * math.sin(tilt) * t * t * 1.6 + 2.2 * t
        theta = s_ / chars.R * 0.55
        c = start + dirv * s_ + Vector((0, 0, chars.R * 0.0 + 0.27))
        rot = Matrix.Rotation(theta, 3, "Y")
        p.root.rotation_euler = rot.to_euler()
        p.root.location = c - rot @ pivot_off
        p.root.keyframe_insert("location", frame=f)
        p.root.keyframe_insert("rotation_euler", frame=f)
    lin(p.root)
    sc.frame_set(a + 4)
    shed(p, sc, range(a + 8, b, 5), floor_z=0.0, per=3, fall_frames=30)
    ash(a, b, n=80, box=(-10, 20, -4, 8, 0, 6), seed=2, drift=(0, 0, 0.4), size=0.02)
    # camera tracks beside her, low
    cam = Cam(lens=40, fstop=3.2)
    ks = []
    for f in range(a, b + 1, 6):
        t = (f - a) / FPS
        s_ = 0.25 * 9.8 * math.sin(tilt) * t * t * 1.6 + 2.2 * t
        c = start + dirv * s_
        ks.append((f, (c.x + 1.2, -4.3, c.z + 0.75), (c.x + 0.8, 0, c.z + 0.35)))
    cam.move(ks)
    return (a, b)


import shots2  # noqa: E402,F401  (registers more shots)
import shots3  # noqa: E402,F401
