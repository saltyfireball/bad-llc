# tools

`art.py` regenerates every image in `public/img/` from code. All shapes are
hand-built paths in the script; the only outside outlines are Pirata One
(wordmark) and Geist Mono (raven badge, og small print), both OFL and read
from `public/kit/v1/fonts/`.

Run from the repo root:

    uv run --with fonttools --with brotli python tools/art.py

Needs `rsvg-convert` and `magick` on PATH for the PNGs.

It writes:

- `public/img/eye.svg`, `raven.svg`, `wordmark.svg`, `favicon.svg`, `grain.svg`
- `public/img/favicon-32.png`, `apple-touch-icon.png` (from `tools/apple-touch-icon.svg`)
- `public/img/og.png` (1200x630, from `tools/og.svg`)
- the inline hero mark in `public/index.html` (the `<svg class="omen">`: the eye with
  the raven perched on it, inlined so CSS can run the ident on its parts)

`glyphs.py` outlines text to SVG path data with fontTools. The wear on the eye
is a seeded mask, so output is the same on every run. Geometry notes for the
animation (ids, ring top, eye centre line) are in the comments at the top of
`eye.svg` and `raven.svg`.
