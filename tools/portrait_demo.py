"""Bakes the synthetic demo portrait for public/kit/v1/portrait-demo/.

A made-up face drawn from shapes (no real art, no model files), baked into the manifest v1
format the kit player reads: opaque stills, opaque H.264 clips for the actions (2x only, 24 fps,
each starting and ending on rest), and two cropped WebP atlases (blink, and a 5x3 pose grid
with closed eyes) in both densities. Needs Pillow and ffmpeg.

Run from the repo root:

    uv run --with pillow python tools/portrait_demo.py

Output goes to public/kit/v1/portrait-demo/portrait/. ASCII only.
"""
import json
import math
import os
import subprocess

from PIL import Image, ImageChops, ImageDraw

W, H = 160, 200
FPS = 24
OUT = os.path.join(os.path.dirname(__file__), "..", "public", "kit", "v1", "portrait-demo", "portrait")
ATLAS_W = 512
BG = (23, 21, 28)

SKIN, HAIR, SHIRT, EYE, IRIS, LIP = (226, 190, 165), (58, 34, 78), (160, 40, 52), (245, 240, 235), (60, 120, 110), (150, 60, 70)


def pose(**kw):
    """yaw and pitch turn the head; gx and gy move only the eyes (the pose grid uses those)."""
    p = dict(yaw=0, pitch=0, gx=0, gy=0, blink=0, mouth=0, arm=0, breath=0, brow=0)
    p.update(kw)
    return p


def render(p, s):
    """One pose at scale s: an opaque RGB image of the whole portrait box on the backdrop."""
    img = Image.new("RGB", (W * s, H * s), BG)
    d = ImageDraw.Draw(img)
    hx, hy = 80 + p["yaw"] * 0.5, 92 + p["pitch"] * 0.5 + p["breath"] * 0.5

    def R(x0, y0, x1, y1):
        return [x0 * s, y0 * s, x1 * s, y1 * s]

    rise = p["breath"] * 2
    d.ellipse(R(hx - 46, hy - 56, hx + 46, hy + 60), fill=HAIR)
    d.rectangle(R(hx - 12, hy + 40, hx + 12, 152), fill=SKIN)
    d.ellipse(R(hx - 36, hy - 44, hx + 36, hy + 48), fill=SKIN)
    d.pieslice(R(hx - 40, hy - 50, hx + 40, hy + 20), 180, 360, fill=HAIR)
    d.polygon([(c * s) for xy in [(20, 200), (36, 150 - rise), (124, 150 - rise), (140, 200)] for c in xy], fill=SHIRT)
    if p["arm"] > 0.02:  # a raised arm and a hand, in front of the shirt; absent at rest
        lift = p["arm"]
        ax = 126 + 10 * math.sin(p["arm"] * 14)
        hy2 = 146 - 66 * lift
        d.line([(120 * s, 146 * s), (ax * s, hy2 * s)], fill=SKIN, width=10 * s)
        d.ellipse(R(ax - 9, hy2 - 14, ax + 9, hy2 + 4), fill=SKIN)
    for side in (-1, 1):
        ex, ey = hx + side * 15 + p["yaw"] * 0.4, hy - 2 + p["pitch"] * 0.3
        open_ = max(1, 7 * (1 - p["blink"]))
        d.ellipse(R(ex - 8, ey - open_, ex + 8, ey + open_), fill=EYE)
        if p["blink"] < 0.7:
            px, py = ex + p["yaw"] * 0.25 + p["gx"], ey + p["pitch"] * 0.2 + p["gy"]
            d.ellipse(R(px - 3.5, py - 3.5, px + 3.5, py + 3.5), fill=IRIS)
        d.line([(ex - 9) * s, (ey - 12 - p["brow"]) * s, (ex + 9) * s, (ey - 12 - p["brow"]) * s], fill=HAIR, width=2 * s)
    m = p["mouth"]
    d.ellipse(R(hx - 8 + p["yaw"] * 0.3, hy + 24, hx + 8 + p["yaw"] * 0.3, hy + 25 + 6 * m), fill=LIP)
    return img


def sweep(n, fn):
    return [fn(i / (n - 1)) for i in range(n)]  # u runs 0..1 inclusive, so ends are rest


def bump(u):
    return math.sin(math.pi * u)


# name: (frames of poses, loop). Every one starts and ends on rest.
CLIPS = {
    "idle": (sweep(37, lambda u: pose(breath=(1 - math.cos(2 * math.pi * u)) / 2)), True),
    "wave": (sweep(37, lambda u: pose(arm=bump(u) ** 0.5, mouth=0.4 * bump(u), brow=-2 * bump(u))), False),
    "glance": (sweep(25, lambda u: pose(yaw=14 * bump(u))), False),
    "tilt": (sweep(25, lambda u: pose(pitch=-6 * bump(u), yaw=-6 * bump(u), brow=3 * bump(u))), False),
    "look": (sweep(25, lambda u: pose(pitch=6 * bump(u), yaw=-14 * bump(u))), False),
}
BLINK = [pose(blink=v) for v in (0.5, 1, 1, 0.5)]
YAW, PITCH = [-14, -7, 0, 7, 14], [-6, 0, 6]


def encode(poses, name):
    """Pipe 2x frames to ffmpeg: H.264 High, yuv420p, BT.709 tagged, faststart, no audio."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W * 2, H * 2),
           "-r", str(FPS), "-i", "-", "-vf", "scale=out_color_matrix=bt709:out_range=tv", "-c:v", "libx264",
           "-profile:v", "high", "-pix_fmt", "yuv420p", "-crf", "30", "-preset", "veryslow", "-colorspace", "bt709",
           "-color_primaries", "bt709", "-color_trc", "bt709", "-movflags", "+faststart", "-an",
           os.path.join(OUT, name)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for q in poses:
        p.stdin.write(render(q, 2).tobytes())
    p.stdin.close()
    if p.wait():
        raise SystemExit("ffmpeg failed for " + name)


def save(img, name):
    img.save(os.path.join(OUT, name), "WEBP", quality=88, method=6)


def bake_atlas(name, poses, rest):
    """Crop each pose to where it differs from rest (1x pixel boxes), shelf-pack the crops into one
    atlas per density. Returns the atlas entry and the frame rects (null = the same as rest)."""
    boxes = []
    for p in poses:
        bb = ImageChops.difference(render(p, 1), rest[1]).getbbox()
        boxes.append(None if not bb else (max(0, bb[0] - 1), max(0, bb[1] - 1), min(W, bb[2] + 1), min(H, bb[3] + 1)))
    pos, x, y, row = {}, 0, 0, 0
    for i, bx in enumerate(boxes):
        if bx is None:
            continue
        w, h = bx[2] - bx[0], bx[3] - bx[1]
        if x + w > ATLAS_W:
            x, y, row = 0, y + row, 0
        pos[i] = (x, y)
        x, row = x + w, max(row, h)
    ah = max(y + row, 1)
    files = {}
    for dn in (1, 2):
        sheet = Image.new("RGB", (ATLAS_W * dn, ah * dn), BG)
        for i, bx in enumerate(boxes):
            if bx is not None:
                src = render(poses[i], dn)
                sheet.paste(src.crop(tuple(c * dn for c in bx)), (pos[i][0] * dn, pos[i][1] * dn))
        fn = "%s%s.webp" % (name, "" if dn == 1 else "@2x")
        save(sheet, fn)
        files[str(dn)] = fn
    frames = [None if bx is None else [pos[i][0], pos[i][1], bx[2] - bx[0], bx[3] - bx[1], bx[0], bx[1]]
              for i, bx in enumerate(boxes)]
    return {"files": files, "width": ATLAS_W, "height": ah}, frames


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))
    rest = {1: render(pose(), 1), 2: render(pose(), 2)}
    save(rest[1], "rest.webp")
    save(rest[2], "rest@2x.webp")
    m = {"version": 1, "persona": "demo", "width": W, "height": H, "background": "#%02x%02x%02x" % BG,
         "still": {"1": "rest.webp", "2": "rest@2x.webp"}, "clips": {}, "atlases": {}}
    for name, (poses, loop) in CLIPS.items():
        encode(poses, name + ".mp4")
        m["clips"][name] = {"src": name + ".mp4", "duration": round(len(poses) / FPS, 3)}
        if loop:
            m["clips"][name]["loop"] = True
    m["atlases"]["blink"], frames = bake_atlas("blink", BLINK, rest)
    m["blink"] = {"atlas": "blink", "fps": FPS, "frames": frames}
    cells = [pose(gx=y * 0.25, gy=-p * 0.25) for p in PITCH for y in YAW]
    closed = [pose(gx=y * 0.25, gy=-p * 0.25, blink=1) for p in PITCH for y in YAW]
    m["atlases"]["grid"], frames = bake_atlas("grid", cells + closed, rest)
    m["grid"] = {"atlas": "grid", "yaw": YAW, "pitch": PITCH, "frames": frames[:15], "closed": frames[15:]}
    m["behaviour"] = {"intro": "wave", "poke": "wave", "idles": ["glance", "tilt", "look"],
                      "every": [6, 12], "blinkEvery": [2, 5]}
    m["bytes"] = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(m, f, indent=1)
        f.write("\n")
    print("wrote %d bytes to %s" % (m["bytes"], os.path.normpath(OUT)))


if __name__ == "__main__":
    main()
