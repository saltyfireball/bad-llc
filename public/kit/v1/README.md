# Bad Omen kit v1

The shared look of every Bad Omen site: fonts, colors, spacing, the footer,
and the voice. bad.llc runs on it; cassie.sh and carrie.sh copy it.

Static files only. No build step, no trackers, no outside requests, so it works
under a strict `default-src 'none'` CSP with `'self'` for styles and fonts. The
only script is the optional living portrait (below), which needs `script-src 'self'`
and `media-src 'self'`.

## Files

| File | What it is |
| --- | --- |
| `tokens.css` | `@font-face` for the four fonts and every `--bo-*` variable: color, type, spacing |
| `footer.css` | The shared footer (`.bo-foot`). Needs `tokens.css` first |
| `footer.html` | The footer markup to paste at the end of `<body>` |
| `template.html` | A starter page with both stylesheets and the footer wired in |
| `portrait-core.js`, `portrait.js`, `portrait.css` | The living portrait: a still that breathes, blinks and follows the cursor (see below) |
| `portrait-demo/` | A made-up face baked in the portrait format (H.264 clips and WebP atlases), to try it with |
| `VOICE.md` | How Bad Omen copy sounds, and what it never says |
| `fonts/` | Pirata One, Geist, Geist Mono, Spectral (all OFL, licenses beside them) |

## Use it on a site

1. Copy this whole `v1` folder into the site as `kit/v1/`, so every site serves
   its own copy and needs nothing from another origin.
2. In `<head>`, before the site's own stylesheet:

       <link rel="stylesheet" href="kit/v1/tokens.css">
       <link rel="stylesheet" href="kit/v1/footer.css">

3. Paste `footer.html` at the end of `<body>`, put the site's own footer lines
   above the band, and give the site's own link `aria-current="page"`.
4. Use `var(--bo-...)` in the site's CSS rather than raw colors.

The canonical copy lives in the bad-llc repo at `public/kit/v1/` and is served
at https://bad.llc/kit/v1/.

## Living portrait

A still `img` that comes alive: breathing, blinking, an idle now and then, eyes
and head following the cursor, a poke on hover. Without script, under
`prefers-reduced-motion: reduce`, or on any error it is just the `img`. No
dependencies, under 6 KB gzipped for both scripts (a test checks it).

Markup. The `img` is the still and is what the page paints first:

    <link rel="stylesheet" href="kit/v1/portrait.css">
    ...
    <figure data-portrait="portrait/manifest.json">
      <img src="portrait/rest.webp" srcset="portrait/rest@2x.webp 2x"
           width="350" height="420" alt="...">
    </figure>
    <script src="kit/v1/portrait-core.js" defer></script>
    <script src="kit/v1/portrait.js" defer></script>

- `data-portrait` is the manifest's path. The manifest, the stills, the clips
  and the atlases sit in that one folder (`public/portrait/`), as the bake
  writes them (manifest v1, in the cassie.sh and carrie.sh living-portraits
  doc). Every image and clip is opaque on the persona's backdrop.
- After first paint, once the figure is near the viewport and the browser is
  idle, the script fetches the manifest and the blink and pose-grid atlases
  (density 2 when `devicePixelRatio` is above 1, else 1). Over the `img` (which
  keeps its place in the layout and stays the still) it puts a `video` for the
  action clips (idle loop, intro, poke, idles; H.264, 2x only) and a `canvas`
  for the blink and pose-grid crops. Clips are fetched one at a time, as they
  are needed. The video shows once a clip's first frame is up and hides when
  it ends (its last frame is rest, the same as the still).
- Idles, pokes and blinks start only at the end of an idle pass. Following the
  cursor holds there too: the idle pauses on rest, the grid runs, and the idle
  resumes after she recentres.
- If a clip fails to load or play (iOS Low Power Mode refuses autoplay), clips
  are dropped and she stays on the still with the grid and blinks.
- It pauses when the tab is hidden or the portrait is off screen, and picks up
  where it stopped. A touch tap pokes, or looks toward the tap while the poke
  cools down.
- The `img` keeps its `alt`; the video and canvas are `aria-hidden`.
- Give the figure a size through the `img` (or CSS); the video and canvas follow it.

CSP: `script-src 'self'` for the scripts, `connect-src 'self'` for the
manifest, `img-src 'self'` for the atlases and `media-src 'self'` for the clips.
No inline script or style (the player sets video attributes from JS and toggles
classes from `portrait.css`), so nothing else changes.

To use it on a site: copy `v1/` as above (the demo folder can stay out), add
the markup, and copy the bake's `portrait/` folder into `public/`. The demo
page `portrait-demo/index.html` is a working example. To rebuild its art, run
`uv run --with pillow python tools/portrait_demo.py` from the repo root.

## Versions

A folder is frozen once another site copies it. Fixes that change nothing
visible can land in place. Anything that changes the look, a token name or the
footer markup goes in a new `v2/` folder beside it, so a site moves when it
chooses to.

The one exception is the footer's link list: a new public project is added in
place, to `footer.html`, `template.html` and bad.llc together, and the other
sites recopy `footer.html`.
