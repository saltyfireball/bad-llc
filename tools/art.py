"""Regenerate every asset in public/img (and tools/og.svg) for bad.llc.

Run from the repo root:
    uv run --with fonttools --with brotli python tools/art.py
Needs rsvg-convert and magick on PATH for the PNGs.
"""

import math
import random
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from glyphs import MONO, PIRATA, text_path  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "public" / "img"
TOOLS = ROOT / "tools"

INK = "#0b0b0c"    # near-black
BONE = "#e8e2d6"
ASH = "#6b6760"
RED = "#b3261e"    # omen red, sparingly
SOOT = "#161618"   # raven feathers, a hair above the ground


def n(v):
    s = f"{v:.1f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def pts(points):
    return " ".join(f"{n(x)} {n(y)}" for x, y in points)


def poly(points):
    return "M" + pts(points[:1]) + "L" + pts(points[1:]) + "Z"


def polar(cx, cy, r, deg):
    a = math.radians(deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def circle_d(cx, cy, r):
    return (f"M{n(cx - r)} {n(cy)}a{n(r)} {n(r)} 0 1 0 {n(2 * r)} 0"
            f"a{n(r)} {n(r)} 0 1 0 {n(-2 * r)} 0Z")


# ---------------------------------------------------------------- the eye --
# viewBox 0 0 240 240, centre (120, 120).
C = 120
RING_OUT, RING_IN, HAIR = 96, 84, 78
EYE_L, EYE_R = 44, 196
ALMOND_TOP = f"M{EYE_L} {C}C76 80 164 80 {EYE_R} {C}"
ALMOND_BOT = f"C164 160 76 160 {EYE_L} {C}"
ALMOND = ALMOND_TOP + ALMOND_BOT + "Z"


def spikes(count, r0, r_long, r_short, half_deg, offset):
    out = []
    for i in range(count):
        a = -90 + offset + i * 360 / count
        tip = r_long if i % 2 == 0 else r_short
        out.append(poly([polar(C, C, r0, a - half_deg), polar(C, C, tip, a),
                         polar(C, C, r0, a + half_deg)]))
    return "".join(out)


def rays(r0, r1, angles, half_deg):
    return "".join(poly([polar(C, C, r0, a - half_deg), polar(C, C, r1, a),
                         polar(C, C, r0, a + half_deg)]) for a in angles)


def wear_mask(mask_id, seed, count, size=240):
    """Small chips and scuffs knocked out of the print, seeded so it is stable."""
    rnd = random.Random(seed)
    chips = []
    for _ in range(count):
        r = rnd.uniform(RING_IN - 4, 112)
        a = rnd.uniform(0, 360)
        x, y = polar(C, C, r, a)
        k = rnd.choice((3, 4, 4, 5))
        s = rnd.uniform(0.8, 2.6)
        rot = rnd.uniform(0, 360)
        chips.append(poly([polar(x, y, s * rnd.uniform(0.5, 1.2), rot + j * 360 / k)
                           for j in range(k)]))
    # a few scuffs across the sclera and the rays
    for _ in range(count // 3):
        x, y = rnd.uniform(60, 180), rnd.uniform(70, 170)
        a = rnd.uniform(-30, 30)
        ln = rnd.uniform(3, 9)
        w = rnd.uniform(0.5, 1.1)
        p1, p2 = polar(x, y, ln, a), polar(x, y, -ln, a)
        q1, q2 = polar(p1[0], p1[1], w, a + 90), polar(p2[0], p2[1], w, a + 90)
        chips.append(poly([p1, q1, q2, p2]))
    return (f'<mask id="{mask_id}" maskUnits="userSpaceOnUse" x="0" y="0" '
            f'width="{size}" height="{size}">'
            f'<rect width="{size}" height="{size}" fill="#fff"/>'
            f'<path fill="#000" d="{"".join(chips)}"/></mask>')


def eye_parts(worn=True, simple=False, ids=True, prefix="omen"):
    """Inner markup of the eye mark in a 240 box. simple=True is the favicon cut."""
    def gid(name):
        return f' id="{prefix}-{name}"' if ids else ""

    mask = f' mask="url(#{prefix}-wear)"' if worn else ""
    defs = [f'<clipPath id="{prefix}-almond"><path d="{ALMOND}"/></clipPath>']
    if worn:
        defs.append(wear_mask(f"{prefix}-wear", 1781, 46))

    if simple:
        ring = (f'<path fill="{BONE}" fill-rule="evenodd" d="{circle_d(C, C, 104)}'
                f'{circle_d(C, C, 84)}"/>'
                f'<path fill="{BONE}" d="{spikes(8, 103, 118, 118, 9, 22.5)}"/>')
    else:
        ring = (f'<path fill="{BONE}" fill-rule="evenodd" d="{circle_d(C, C, RING_OUT)}'
                f'{circle_d(C, C, RING_IN)}"/>'
                f'<circle cx="{C}" cy="{C}" r="{HAIR}" fill="none" stroke="{BONE}" '
                f'stroke-width="2"/>'
                f'<path fill="{BONE}" d="{spikes(16, 95, 112, 104, 4.2, 11.25)}"/>'
                f'<path fill="{BONE}" d="'
                f'{rays(44, 70, (-90, -64, -116), 3.2)}'
                f'{rays(44, 62, (-40, -140), 2.6)}'
                f'{rays(44, 70, (90, 64, 116), 3.2)}'
                f'{rays(44, 62, (40, 140), 2.6)}"/>')

    flick = (f"M{EYE_L + 2} {C - 4}L{EYE_L - 18} {C}L{EYE_L + 2} {C + 4}Z"
             f"M{EYE_R - 2} {C - 4}L{EYE_R + 18} {C}L{EYE_R - 2} {C + 4}Z")
    if simple:
        flick = ""
    iris_r, pupil_r = (30, 13) if simple else (27, 11)
    iris = (f'<circle cx="{C}" cy="{C}" r="{iris_r}" fill="{RED}"/>'
            + ("" if simple else
               f'<circle cx="{C}" cy="{C}" r="{iris_r - 1}" fill="none" stroke="{INK}" '
               f'stroke-width="2"/>'
               f'<circle cx="{C}" cy="{C}" r="18" fill="none" stroke="{INK}" '
               f'stroke-width="1" stroke-dasharray="2 3" opacity=".55"/>')
            + f'<circle cx="{C}" cy="{C}" r="{pupil_r}" fill="{INK}"/>'
            + f'<circle cx="{C + 7}" cy="{C - 8}" r="{4.5 if simple else 3.5}" '
              f'fill="{BONE}"/>')

    # Lids. Each covers its half of the almond and is drawn at scaleY(0) about
    # the centre line y=120, so the file shows an open eye. A seam and lashes ride
    # on the bottom lid; their strokes flatten to nothing at scaleY(0).
    rest = f' transform="matrix(1 0 0 0 0 {C})"'
    lid_top = (f'<g{gid("lid-top")}{rest}><path fill="{INK}" '
               f'd="M{EYE_L - 3} {C}C76 77 164 77 {EYE_R + 3} {C}Z"/></g>')
    lashes = "".join(f"M{x} {C + 1}L{x + dx} {C + 11}" for x, dx in
                     ((78, -4), (99, -2), (120, 0), (141, 2), (162, 4)))
    lid_bot = (f'<g{gid("lid-bottom")}{rest}><path fill="{INK}" '
               f'd="M{EYE_L - 3} {C}C76 163 164 163 {EYE_R + 3} {C}Z"/>'
               + ("" if simple else
                  f'<path fill="none" stroke="{BONE}" stroke-width="3.5" '
                  f'stroke-linecap="round" d="M{EYE_L + 6} {C}L{EYE_R - 6} {C}{lashes}"/>')
               + "</g>")
    outline = (f'<path fill="none" stroke="{BONE}" stroke-width="{7 if simple else 5}" '
               f'stroke-linejoin="round" d="{ALMOND}"/>'
               + (f'<path fill="{BONE}" d="{flick}"/>' if flick else ""))

    return (
        f'<defs>{"".join(defs)}</defs>'
        f'<g{gid("ring")}><g{mask}>{ring}</g></g>'
        f'<g{gid("eye")}><path fill="{BONE}" d="{ALMOND}"{mask}/>'
        f'<g clip-path="url(#{prefix}-almond)"><g{gid("iris")}>{iris}</g></g></g>'
        f'<g clip-path="url(#{prefix}-almond)">{lid_top}{lid_bot}</g>'
        f'<g{gid("eye-outline")}><g{mask}>{outline}</g></g>'
    )


EYE_NOTES = (
    "<!-- Bad Omen eye mark. viewBox 0 0 240 240, centre (120,120).\n"
    "     Ring: outer r=96, so the TOP OF THE RING is y=24 (x=120); the raven perches\n"
    "     there, between two spikes (nearest spike tips: y~10 at x 99 and 141).\n"
    "     Eye CENTRE LINE is y=120 (almond x 44..196, y 90..150).\n"
    "     #omen-lid-top / #omen-lid-bottom rest at scaleY(0) about y=120 (open eye).\n"
    "     To blink: transform-origin: 120px 120px; transform: scaleY(1) closes them.\n     Lids are clipped to the almond, so a lid-like blink also works: top lid\n     origin 120px 90px, bottom lid origin 120px 150px, scaleY 0 -> 1.\n"
    "     #omen-iris may be translated a few px to look around (clipped to the almond). -->"
)


def svg(view_w, view_h, body, label, extra=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {view_w} {view_h}" '
            f'role="img" aria-label="{label}"{extra}>{body}</svg>\n')


# -------------------------------------------------------------- the raven --
# viewBox 0 0 120 150, faces left, feet at the bottom centre (60, 150).
RV_W, RV_H = 120, 150


def raven_parts(prefix="raven"):
    rim = f'stroke="{ASH}" stroke-width="1.6" stroke-linejoin="round"'
    tail = poly([(76, 118), (90, 112), (112, 144), (107, 147), (104, 143), (100, 149),
                 (95, 145), (91, 149), (84, 140)])
    # body with ragged throat hackles down the front and scruffy trousers
    body = ("M42 46L36 52L40 54L33 60L38 62L31 69L36 71L30 78L34 80"
            "C28 100 34 122 50 131L54 136L57 132L61 137L64 133L68 137L71 133"
            "C78 134 84 128 88 121C96 102 92 64 68 44Z")
    legs = "M56 128L55 145M66 128L66 145"
    toes = ("M55 145L47 148M55 145L50 150M55 145L56 150M55 145L62 147"
            "M66 145L59 148M66 145L62 150M66 145L68 150M66 145L73 147")
    body_g = (
        f'<g id="{prefix}-body">'
        f'<path fill="{SOOT}" {rim} d="{tail}"/>'
        f'<path fill="none" stroke="{ASH}" stroke-width="3" stroke-linecap="round" '
        f'd="{legs}"/>'
        f'<path fill="none" stroke="{ASH}" stroke-width="2" stroke-linecap="round" '
        f'd="{toes}"/>'
        f'<path fill="{SOOT}" {rim} d="{body}"/>'
        f'</g>')

    wing = ("M52 56C70 46 90 58 90 82L104 136L97 131L96 138L90 128L87 134L82 123"
            "L78 127L72 114C58 108 47 88 52 56Z")
    feathers = ("M60 70C70 78 80 96 86 120M56 84C63 94 70 106 77 118"
                "M68 60C78 68 86 86 92 110M58 60C68 56 78 62 82 72")
    wings_g = (
        f'<g id="{prefix}-wings">'
        f'<path fill="{INK}" {rim} d="{wing}"/>'
        f'<path fill="none" stroke="{ASH}" stroke-width="1" stroke-linecap="round" '
        f'd="{feathers}"/>'
        f'</g>')

    head = ("M35 30C35 19 43 12 52 12L53 7L56 12L61 9L60 14L65 12L63 18"
            "C69 23 70 36 66 45C61 54 48 56 40 51C36 45 35 38 35 30Z")
    beak = "M38 22C28 21 16 27 7 37C9 40 12 41 15 40C23 41 31 44 40 46Z"
    bristles = "M40 26L33 27M40 29L32 31M41 32L34 34"
    head_g = (
        f'<g id="{prefix}-head">'
        f'<path fill="{SOOT}" {rim} d="{head}"/>'
        f'<path fill="#232225" {rim} d="{beak}"/>'
        f'<path fill="none" stroke="{BONE}" stroke-width=".9" stroke-linecap="round" '
        f'opacity=".55" d="M34 23C26 24 17 29 10 36"/>'
        f'<path fill="none" stroke="{ASH}" stroke-width="1" stroke-linecap="round" '
        f'd="{bristles}"/>'
        # the flat, half-lidded, entirely unimpressed eye
        f'<path fill="{BONE}" d="M46 29A5.5 5.5 0 0 0 57 29Z"/>'
        f'<circle cx="50.5" cy="30.6" r="2.2" fill="{INK}"/>'
        f'<path fill="none" stroke="{BONE}" stroke-width="1.6" stroke-linecap="round" '
        f'd="M44.5 28.6L58.5 28.6"/>'
        f'<path fill="none" stroke="{BONE}" stroke-width=".9" stroke-linecap="round" '
        f'opacity=".45" d="M50 17C57 16 63 20 65 27"/>'
        f'</g>')

    # badge: lanyard round the neck, card tilted a touch
    l1, _, _ = text_path("DIRECTOR", MONO, 3.4, 0, 0, tracking=0.05, kern=False)
    l2, _, _ = text_path("OF OMENS", MONO, 3.4, 0, 0, tracking=0.05, kern=False)
    badge_g = (
        f'<g id="{prefix}-badge">'
        f'<path fill="none" stroke="{RED}" stroke-width="1.2" stroke-linejoin="round" '
        f'd="M42 50L46 82M62 50L50 82"/>'
        f'<g transform="rotate(-7 47 90)">'
        f'<rect x="35" y="82" width="24" height="16" rx="1.2" fill="{BONE}" '
        f'stroke="{INK}" stroke-width=".6"/>'
        f'<rect x="35" y="82" width="24" height="3.2" fill="{RED}"/>'
        f'<rect x="45" y="80.6" width="4" height="2.6" rx=".6" fill="{ASH}"/>'
        f'<path fill="{INK}" transform="translate(36.6 90.2)" d="{l1}"/>'
        f'<path fill="{INK}" transform="translate(36.6 95.2)" d="{l2}"/>'
        f'</g></g>')
    return body_g + wings_g + head_g + badge_g


RAVEN_NOTES = (
    "<!-- Raven, Director of Omens. viewBox 0 0 120 150, faces left.\n"
    "     Feet grip at the bottom centre (60,150): place that point on the ring top.\n"
    "     Suggested size: 0.6x (72 x 90 eye units) on the 240 eye. -->"
)


# ------------------------------------------------------------ wordmark etc --
def wordmark():
    d, _, (x0, y0, x1, y1) = text_path("BAD OMEN", PIRATA, 100, 0, 0, tracking=2)
    pad = 2
    vb = f"{n(x0 - pad)} {n(y0 - pad)} {n(x1 - x0 + 2 * pad)} {n(y1 - y0 + 2 * pad)}"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" role="img" '
            f'aria-label="Bad Omen"><path fill="{BONE}" d="{d}"/></svg>\n'), (x0, y0, x1, y1), d


def grain():
    # Bone specks with a hard alpha cut, so it reads as ink on a tee, not fog.
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" '
        'viewBox="0 0 160 160"><filter id="g" x="0" y="0" width="100%" height="100%">'
        '<feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" '
        'seed="1781" stitchTiles="stitch"/>'
        '<feColorMatrix values="0 0 0 0 .91 0 0 0 0 .886 0 0 0 0 .84 0 0 0 2.6 -1.25"/>'
        '</filter><rect width="160" height="160" filter="url(#g)"/></svg>\n')


def favicon(rx=36):
    return svg(240, 240,
               f'<rect width="240" height="240" rx="{rx}" fill="{INK}"/>'
               f'<g transform="translate(120 120) scale(.9) translate(-120 -120)">'
               f'{eye_parts(worn=False, simple=True, ids=False, prefix="fi")}</g>',
               "Bad Omen")


def og():
    W, H = 1200, 630
    eye_s = 1.2                      # eye 288 px across
    ex, ey = W / 2 - 120 * eye_s, 118
    ring_top = ey + 24 * eye_s
    rv_s = 0.6 * eye_s
    rx, ry = W / 2 - 60 * rv_s, ring_top - 150 * rv_s + 2
    _, (x0, y0, x1, y1), wd = wordmark()
    wm_w = 520
    ws = wm_w / (x1 - x0)
    wx, wy = W / 2 - (x0 + (x1 - x0) / 2) * ws, 532 - y1 * ws
    sp, adv, _ = text_path("est. 2026 \u00b7 no refunds", MONO, 22, 0, 0, tracking=1.5,
                           kern=False)
    sx = W / 2 - adv / 2
    body = (
        f'<rect width="{W}" height="{H}" fill="{INK}"/>'
        f'<filter id="og-grain" x="0" y="0" width="100%" height="100%">'
        f'<feTurbulence type="fractalNoise" baseFrequency=".8" numOctaves="2" seed="7"/>'
        f'<feColorMatrix values="0 0 0 0 .91 0 0 0 0 .886 0 0 0 0 .84 0 0 0 2.6 -1.25"/>'
        f'</filter>'
        f'<g transform="translate({n(ex)} {n(ey)}) scale({eye_s})">{eye_parts()}</g>'
        f'<g transform="translate({n(rx)} {n(ry)}) scale({n(rv_s)})">{raven_parts()}</g>'
        f'<path fill="{BONE}" transform="translate({n(wx)} {n(wy)}) scale({ws:.4f})" '
        f'd="{wd}"/>'
        f'<path fill="{ASH}" transform="translate({n(sx)} 586)" d="{sp}"/>'
        f'<rect width="{W}" height="{H}" filter="url(#og-grain)" opacity=".10"/>'
    )
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}">{body}</svg>\n')


def run(*cmd):
    subprocess.run(cmd, check=True)


def main():
    IMG.mkdir(parents=True, exist_ok=True)
    files = {
        IMG / "eye.svg": svg(240, 240, EYE_NOTES + eye_parts(), "Bad Omen eye"),
        IMG / "raven.svg": svg(RV_W, RV_H, RAVEN_NOTES + raven_parts(),
                               "A raven wearing a Director of Omens badge"),
        IMG / "wordmark.svg": wordmark()[0],
        IMG / "favicon.svg": favicon(),
        IMG / "grain.svg": grain(),
        TOOLS / "og.svg": og(),
    }
    for path, text in files.items():
        text.encode("ascii")  # every source file stays ASCII
        path.write_text(text)

    for tool in ("rsvg-convert", "magick"):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found; SVGs written, PNGs skipped")
    # The apple icon is a full opaque square: iOS rounds the corners itself.
    square = TOOLS / "apple-touch-icon.svg"
    square.write_text(favicon(rx=0))
    for out, src, size in (("favicon-32.png", IMG / "favicon.svg", 32),
                           ("apple-touch-icon.png", square, 180)):
        run("rsvg-convert", "-w", str(size), "-h", str(size), str(src), "-o", str(IMG / out))
        run("magick", str(IMG / out), "-strip", "-colors", "64", f"PNG8:{IMG / out}")
    og_png = str(IMG / "og.png")
    run("rsvg-convert", str(TOOLS / "og.svg"), "-o", og_png)
    run("magick", og_png, "-strip", "-colors", "128", f"PNG8:{og_png}")
    for f in sorted(IMG.iterdir()):
        print(f"{f.stat().st_size:>8}  {f.name}")


if __name__ == "__main__":
    main()
