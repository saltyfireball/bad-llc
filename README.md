# bad-llc

The landing page for https://bad.llc, home of Bad Omen: one static page, hosted on Cloudflare Pages.

Everything in this repo ends up public. Keep hostnames, IPs, internal URLs, secrets, private details and licensed assets out of it. Art is hand-made SVG; fonts are OFL and self-hosted, with their licenses in `public/kit/v1/fonts/`.

Epic: SLRM-1779

## The Bad Omen kit

`public/kit/v1/` is the shared kit every Bad Omen site uses: fonts, the `--bo-*`
color, type and spacing tokens, the shared footer, a starter page and the voice
guide (`VOICE.md`). bad.llc loads it like any other site would; cassie.sh and
carrie.sh copy the folder. Its own README covers using it and when a change
needs a `v2/`. Epic: SLRM-1881.

## Tests

The living portrait player has tests (`node --test`, no dependencies, Node 20 or newer). From the repo root:

    node --test tests/

They cover the state machine (clip commands, the idle seam, blink and pose grid), the manifest checks
and the 6 KB gzip budget.

Sections sit one `--bo-section` apart, set in `style.css` rather than the frozen kit: 3.5rem on a phone,
6rem on a desktop, the same on all three sites (SLRM-1953). `tests/test_spacing.py` loads the page in
headless Chromium and WebKit at 375, 390, 768, 1280 and 1440px and fails when the visible gap between
two sections passes 64px on a phone or 104px wider (the hero may add 48px). It needs Playwright, so run
`~/.venvs/claude/bin/python -m unittest discover tests`; plain `python3` skips it.

## Updating the page

1. Edit the files in `public/` directly. There is no build step. JavaScript is tiny, deferred and only for easter eggs; the page works without it.
2. To check it locally, serve `public/` with any static server.
3. Run `./deploy.sh` to publish `public/` to the preview, https://preview.bad-llc-ncd.pages.dev. `./deploy.sh main` publishes production.

Cloudflare gives `.css`, `.js`, `.mp4` and `.webp` a 4 hour browser cache whatever `_headers` says, so
`deploy.sh` uploads a staged copy where a changed file has a new URL: CSS and JS get `?v=HASH` on the
pages, and every duet clip, still and atlas is renamed `NAME.HASH.EXT` by `tools/stamp_duet.py`, which
rewrites the manifests and the page to match. Keep plain names in `public/`; the stamping happens only
at deploy.

`deploy.sh` never attaches domains or touches DNS. bad.llc carries live Proton Mail records (MX, SPF, DKIM, DMARC): leave them alone.

## The duet

Under the wordmark, Cassandra (left) and Carrie (right) share one frame and play short bits together:
one glares and the other rolls her eyes, a stare-down (one stares first, the other answers late and
holds on longer), or one gets caught watching the other. Each bit comes in both orders, and its halves
act in counterpoint, never on the same frame (SLRM-1948). A random bit plays every 10 to 25 seconds, and
hover or a tap starts one (never two at once). Between bits both blink and follow the cursor with their
eyes, each on her own clock: one looks first, and the other looks late, only half turns, or ignores it.
Without JavaScript, or under `prefers-reduced-motion`, the page shows the two stills only.

- `public/duet/` holds the baked frames: `duet.json` (the bits, which clip each side plays and how
  long) and a `cassandra/` and `carrie/` folder, each an ordinary portrait bake (manifest, H.264
  clips, WebP atlases and stills).
- `public/duet.js` is the player. It runs the kit's `portrait-core.js` on each side for blinks and
  eyes and starts both halves of a bit together once both clips are ready.
- The CSP allows `media-src 'self'` for the clips; scripts stay `'self'`.

Only rendered frames are committed: never the models, their textures, mocap or anything they come
from. `python3 -m unittest discover tests` checks that `public/duet/` stays under 2.5 MB (the duet budget, SLRM-1951), that every
file the manifests name exists, that the halves of each bit match in length, and that no model or
mocap file is anywhere in `public/`.

To rebake, in assistant-avatar run `~/.venvs/claude/bin/python portrait/duet.py` (add `--crf N` if it
is over budget; the bits live in `portrait/duet.json` and `portrait/actions/*-duet.json`), then copy
`out/portrait-duet/` over `public/duet/` without its `.cache/` and report files. Epic card: SLRM-1921.

## Text and motion

Text is readable on first paint. The studio ident is a 9-second video in the hero (`public/kit/v1/ident/`,
made from `tools/ident/`) in a box reserved before it loads, so it never blocks or moves the text. It plays once a
visit, muted, and holds its last frame; later visits show the poster with a Replay button. Its own Skip button
jumps to the end, and Sound: off restarts it with sound. Under `prefers-reduced-motion` it shows the poster and
waits for Play. Without JavaScript it is the poster with native controls; if the video cannot play, the old SVG
mark shows in its place, with its own CSS ident that skips on a click or key and is off under reduced motion.

`no-transform` in `public/_headers` is there on purpose: it stops Cloudflare adding its analytics script to the page.
