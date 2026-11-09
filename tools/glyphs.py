"""Outline text to SVG path data with fontTools (reads woff2 with brotli)."""

from functools import lru_cache
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FONTS = Path(__file__).resolve().parent.parent / "public" / "kit" / "v1" / "fonts"
PIRATA = FONTS / "pirata-one-latin-400-normal.woff2"
MONO = FONTS / "geist-mono-latin-400-normal.woff2"


def _num(n):
    s = f"{n:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


@lru_cache(maxsize=None)
def _font(path):
    font = TTFont(str(path))
    return font, font.getGlyphSet(), font.getBestCmap(), font["head"].unitsPerEm


def _kern_pairs(font):
    """Plain pair kerning from GPOS format 1 lookups, if any (good enough here)."""
    pairs = {}
    if "GPOS" not in font:
        return pairs
    gpos = font["GPOS"].table
    for lookup in gpos.LookupList.Lookup:
        for sub in lookup.SubTable:
            if lookup.LookupType == 9:
                sub = sub.ExtSubTable
            if getattr(sub, "LookupType", lookup.LookupType) != 2 or sub.Format != 1:
                continue
            cov = sub.Coverage.glyphs
            for i, ps in enumerate(sub.PairSet):
                for rec in ps.PairValueRecord:
                    v = rec.Value1
                    adv = getattr(v, "XAdvance", 0) if v else 0
                    if adv:
                        pairs[(cov[i], rec.SecondGlyph)] = adv
    return pairs


def text_path(text, font_path=PIRATA, size=100.0, x=0.0, y=0.0, tracking=0.0, kern=True):
    """Return (d, advance_width, (xmin, ymin, xmax, ymax)) with baseline at y."""
    font, gs, cmap, upm = _font(font_path)
    pairs = _kern_pairs(font) if kern else {}
    k = size / upm
    pen = SVGPathPen(gs, ntos=_num)
    bounds = BoundsPen(gs)
    cx = x
    prev = None
    for ch in text:
        name = cmap[ord(ch)]
        if prev is not None:
            cx += pairs.get((prev, name), 0) * k
        t = (k, 0, 0, -k, cx, y)
        gs[name].draw(TransformPen(pen, t))
        gs[name].draw(TransformPen(bounds, t))
        cx += gs[name].width * k + tracking
        prev = name
    return pen.getCommands(), cx - x - tracking, bounds.bounds
