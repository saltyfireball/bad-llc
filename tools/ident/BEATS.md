# Bad Omen production logo: "Every omen at once" (SLRM-1922)

The company's studio ident. Plays before Bad Omen projects and in the bad.llc
hero. Deadpan: the raven never reacts to the chaos it causes. Nobody is joking.

## Format

- 1920x1080, 24 fps, 216 frames (9.0 s). Frame numbers below are 1-based.
- Masters: `out/ident.mp4` (H.264 + AAC), `out/ident.webm` (VP9 + Opus),
  `out/ident-poster.jpg` (frame 200), `out/ident-silent.mp4` (no audio track).
- Palette from `public/kit/v1/tokens.css`: near-black ground, bone `#e8e2d6`
  for the wordmark, one warm practical key light, cool rim. Mostly dark.

## Stage (camera locked, slight slow push-in over the whole shot)

Left to right, on a plain wooden floor against a dark plaster wall:

1. A wooden step ladder leaning against the wall, center-left, legs on the
   floor, open space under it big enough for the raven to walk through.
2. A small side table just right of the ladder, a glass salt shaker on it.
3. A tall rectangular standing mirror, center-right, facing camera, on a
   simple wooden frame/stand. Its glass is the canvas for the wordmark.

The raven: the Director of Omens (see `public/img/raven.svg`): glossy black,
small bone-coloured badge on its chest. The cat: plain black, low, fast.

## Beats (frame : event : sound cue)

| Frames  | Event | Sound cue (frame) |
|---------|-------|-------------------|
| 1-24    | Fade up from black. Bulb flickers once (f6-10) then steadies. | bulb buzz/tick f6 |
| 14-62   | Raven walks in from frame left, unhurried, straight under the ladder. Steps every 6 frames. | steps f16,22,28,34,40,46,52,58 |
| 60      | Raven clears the ladder. Its tail flicks the ladder leg. | tail flick f60 |
| 62-80   | Ladder creaks, wobbles, tips right. | creak f64 |
| 82      | Ladder hits the side table. | wood clunk f82 |
| 84-110  | Salt shaker topples, rolls, salt spills off the table edge in a stream. | shaker clink f84, salt hiss f86-110 |
| 88-118  | Table jolt rocks the mirror on its stand; it tips forward, catches, slams back upright. | wobble thud f100, slam f118 |
| 120     | Glass cracks. | glass crack f120 |
| 120-150 | Cracks run across the glass and settle into the BAD OMEN wordmark, faintly lit from within (bone). | crackle tail f122-150 |
| 128-146 | Black cat bolts across the foreground right to left, motion-blurred, in front of everything. | whoosh f128-140, short "mrrp" f134 |
| 150-168 | Raven, now front-right of the mirror, turns its head to camera. Holds. | none (silence beat f150-160) |
| 162     | Raven opens a small black umbrella. Indoors. | umbrella pop f162 |
| 168-216 | Hold on the tableau. Wordmark glows steady. | low hit/drone swell f168, decays by f216 |
| 176-196 | Card fades in under the mirror: "A Bad Omen project." (Spectral light, bone). | none |
| 200     | Poster frame. | |
| 204-216 | Optional: slight vignette tighten. No fade to black (the end frame must work as a still). | |

## Interfaces between parts

- Characters live in `tools/ident/characters.blend`, built by
  `tools/ident/characters.py`. Each character is one root Empty
  (`RAVEN_ROOT`, `CAT_ROOT`) with named parented parts or a simple armature,
  documented at the top of `characters.py` (pivot points, forward axis,
  scale in metres, which bones/parts to key for walk, head turn, tail flick,
  umbrella open). Raven height about 0.35 m to the top of the head; the cat
  about 0.25 m at the shoulder. Forward is -X for the raven at rest (it walks
  left to right in shot, so the scene rotates it); document whatever you pick.
- The scene, `tools/ident/scene.py`, builds `tools/ident/ident.blend` from
  nothing, appends the characters by name, keys every beat above by frame, and
  renders PNG frames to `tools/ident/out/frames/`. It must run headless:
  `blender -b -P tools/ident/scene.py -- --render [--preview]`.
- Sound, `tools/ident/sting.py`, synthesizes `tools/ident/out/sting.wav`
  (48 kHz, stereo, exactly 9.0 s) from the cue column. No samples, no
  downloaded audio: everything synthesized in code.
- `tools/ident/build.sh` muxes frames + sting into the masters and copies the
  web set into `public/kit/v1/ident/`.
- `tools/ident/out/` is gitignored; only the web set under `public/` is
  committed.
