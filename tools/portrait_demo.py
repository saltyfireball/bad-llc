"""Bakes the synthetic demo portrait for public/kit/v1/portrait-demo/.

A made-up face drawn from shapes (no real art, no model files), baked into the manifest v1
format the kit player reads: two layers (base, shirt), two densities, cropped frames packed
into one atlas per action, a 5x3 pose grid with closed eyes, and the behaviour block.

Run from the repo root:

    uv run --with pillow python tools/portrait_demo.py

Output goes to public/kit/v1/portrait-demo/portrait/. ASCII only.
"""
import json
import math
import os

from PIL import Image, ImageChops, ImageDraw

W, H = 160, 200
OUT = os.path.join(os.path.dirname(__file__), "..", "public", "kit", "v1", "portrait-demo", "portrait")
ATLAS_W = 512

SKIN, HAIR, SHIRT, EYE, IRIS, LIP = (226, 190, 165), (58, 34, 78), (160, 40, 52), (245, 240, 235), (60, 120, 110), (150, 60, 70)


def pose(**kw):
    p = dict(yaw=0, pitch=0, blink=0, mouth=0, arm=None, breath=0, brow=0)
    p.update(kw)
    return p


def render(p, s):
    """One pose at scale s: returns (base, shirt) RGBA images of the whole portrait box."""
    base = Image.new("RGBA", (W * s, H * s), (0, 0, 0, 0))
    shirt = Image.new("RGBA", (W * s, H * s), (0, 0, 0, 0))
    b, t = ImageDraw.Draw(base), ImageDraw.Draw(shirt)
    hx, hy = 80 + p["yaw"] * 0.5, 92 + p["pitch"] * 0.5 + p["breath"] * 0.5

    def R(x0, y0, x1, y1):
        return [x0 * s, y0 * s, x1 * s, y1 * s]

    # shirt: a body that rises a little with the breath
    rise = p["breath"] * 2
    t.polygon([(c * s) for xy in [(20, 200), (36, 150 - rise), (124, 150 - rise), (140, 200)] for c in xy], fill=SHIRT)
    # base: hair back, neck, head, hair front, face
    b.ellipse(R(hx - 46, hy - 56, hx + 46, hy + 60), fill=HAIR)
    b.rectangle(R(hx - 12, hy + 40, hx + 12, 152), fill=SKIN)
    b.ellipse(R(hx - 36, hy - 44, hx + 36, hy + 48), fill=SKIN)
    b.pieslice(R(hx - 40, hy - 50, hx + 40, hy + 20), 180, 360, fill=HAIR)
    if p["arm"] is not None:  # a raised arm and a hand that waves, above the shirt
        ax = 126 + 8 * math.sin(p["arm"])
        b.line([(120 * s, 146 * s), (ax * s, 80 * s)], fill=SKIN, width=10 * s)
        b.ellipse(R(ax - 9, 66, ax + 9, 84), fill=SKIN)
    for side in (-1, 1):
        ex, ey = hx + side * 15 + p["yaw"] * 0.4, hy - 2 + p["pitch"] * 0.3
        open_ = max(1, 7 * (1 - p["blink"]))
        b.ellipse(R(ex - 8, ey - open_, ex + 8, ey + open_), fill=EYE)
        if p["blink"] < 0.7:
            px, py = ex + p["yaw"] * 0.25, ey + p["pitch"] * 0.2
            b.ellipse(R(px - 3.5, py - 3.5, px + 3.5, py + 3.5), fill=IRIS)
        b.line([(ex - 9) * s, (ey - 12 - p["brow"]) * s, (ex + 9) * s, (ey - 12 - p["brow"]) * s], fill=HAIR, width=2 * s)
    m = p["mouth"]
    b.ellipse(R(hx - 8 + p["yaw"] * 0.3, hy + 24, hx + 8 + p["yaw"] * 0.3, hy + 25 + 6 * m), fill=LIP)
    return base, shirt


def sweep(n, fn):
    return [fn(i / n) for i in range(n)]


def bump(u):
    return math.sin(math.pi * u)


ACTIONS = {
    "idle": (8, True, sweep(16, lambda u: pose(breath=(1 - math.cos(2 * math.pi * u)) / 2))),
    "blink": (24, False, [pose(blink=v) for v in (0.5, 1, 1, 0.5)]),
    "wave": (12, False, sweep(14, lambda u: pose(arm=u * 14, mouth=0.4 * bump(u), brow=-2 * bump(u)))),
    "glance": (12, False, sweep(10, lambda u: pose(yaw=14 * bump(u)))),
    "tilt": (12, False, sweep(10, lambda u: pose(pitch=-6 * bump(u), yaw=-6 * bump(u), brow=3 * bump(u)))),
    "look": (12, False, sweep(12, lambda u: pose(pitch=6 * bump(u), yaw=-14 * bump(min(1, u * 1.6))))),
}
YAW, PITCH = [-14, -7, 0, 7, 14], [-6, 0, 6]


def bake_set(poses, rest):
    """Crop each pose to where it differs from rest, in 1x pixel boxes.

    Both layers get the union box of the two diffs: the player clears each rect before it draws,
    so a layer that is null there would otherwise leave a hole where the other one is cropped."""
    boxes, crops = [], {1: [], 2: []}
    for p in poses:
        r1, r2 = render(p, 1), render(p, 2)
        diffs = [d for d in (ImageChops.difference(r1[i], rest[1][i]).getbbox() for i in (0, 1)) if d]
        if not diffs:
            boxes.append([None, None])
            crops[1] += [None, None]
            crops[2] += [None, None]
            continue
        x0, y0 = max(0, min(d[0] for d in diffs) - 1), max(0, min(d[1] for d in diffs) - 1)
        x1, y1 = min(W, max(d[2] for d in diffs) + 1), min(H, max(d[3] for d in diffs) + 1)
        boxes.append([(x0, y0, x1 - x0, y1 - y0)] * 2)
        for li in (0, 1):
            crops[1].append(r1[li].crop((x0, y0, x1, y1)))
            crops[2].append(r2[li].crop((x0 * 2, y0 * 2, x1 * 2, y1 * 2)))
    return boxes, crops


def pack(boxes, crops):
    """Shelf-pack every layer's crops into an atlas (1x pixels); returns rects and atlas files."""
    pos, x, y, row = {}, 0, 0, 0
    for fi, frame in enumerate(boxes):
        for li, bx in enumerate(frame):
            if bx is None:
                continue
            if x + bx[2] > ATLAS_W:
                x, y, row = 0, y + row, 0
            pos[(fi, li)] = (x, y)
            x, row = x + bx[2], max(row, bx[3])
    return pos, y + row


def save(img, name):
    img.save(os.path.join(OUT, name), "WEBP", quality=88, method=6)


def bake_atlas(name, poses, rest, layers):
    boxes, crops = bake_set(poses, rest)
    pos, ah = pack(boxes, crops)
    ah = max(ah, 1)
    files = {l: {} for l in layers}
    for d in (1, 2):
        sheets = [Image.new("RGBA", (ATLAS_W * d, ah * d), (0, 0, 0, 0)) for _ in layers]
        for fi, frame in enumerate(boxes):
            for li, bx in enumerate(frame):
                if bx is not None:
                    sheets[li].paste(crops[d][fi * 2 + li], (pos[(fi, li)][0] * d, pos[(fi, li)][1] * d))
        for li, l in enumerate(layers):
            fn = "%s.%s%s.webp" % (name, l, "" if d == 1 else "@2x")
            save(sheets[li], fn)
            files[l][str(d)] = fn
    frames = []
    for fi, frame in enumerate(boxes):
        f = {}
        for li, l in enumerate(layers):
            bx = frame[li]
            f[l] = None if bx is None else [pos[(fi, li)][0], pos[(fi, li)][1], bx[2], bx[3], bx[0], bx[1]]
        frames.append(f)
    return {"width": ATLAS_W, "height": ah, "files": files}, frames


def main():
    os.makedirs(OUT, exist_ok=True)
    layers = ["base", "shirt"]
    rest = {1: render(pose(), 1), 2: render(pose(), 2)}
    for d, suffix in ((1, ""), (2, "@2x")):
        # The still is base then shirt, like every frame.
        save(Image.alpha_composite(rest[d][0], rest[d][1]), "rest%s.webp" % suffix)
    m = {"version": 1, "persona": "demo", "width": W, "height": H, "densities": [1, 2], "background": None,
         "still": {"1": "rest.webp", "2": "rest@2x.webp"}, "layers": layers, "atlases": {}, "actions": {}}
    for name, (fps, loop, poses) in ACTIONS.items():
        atlas, frames = bake_atlas(name, poses, rest, layers)
        m["atlases"][name] = atlas
        m["actions"][name] = {"atlas": name, "fps": fps, "frames": frames}
        if loop:
            m["actions"][name]["loop"] = True
    cells = [pose(yaw=y, pitch=p) for p in PITCH for y in YAW]
    closed = [pose(yaw=y, pitch=p, blink=1) for p in PITCH for y in YAW]
    atlas, frames = bake_atlas("grid", cells + closed, rest, layers)
    m["atlases"]["grid"] = atlas
    m["grid"] = {"atlas": "grid", "yaw": YAW, "pitch": PITCH, "frames": frames[:15], "closed": frames[15:]}
    m["behaviour"] = {"intro": "wave", "poke": "wave", "idles": ["glance", "tilt", "look"],
                      "every": [6, 12], "blinkEvery": [2, 5], "grid": True}
    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT) if f.endswith(".webp"))
    m["bytes"] = total
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(m, f, indent=1)
        f.write("\n")
    print("wrote %d bytes of webp to %s" % (total, os.path.normpath(OUT)))


if __name__ == "__main__":
    main()
