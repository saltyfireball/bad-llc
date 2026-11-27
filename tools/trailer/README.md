# Cake-Pop Demon Hunters: the parody trailer (BAD-857)

A teaser of about 2:04, played dead serious, in the same look as the bad.llc studio
ident (`tools/ident`): Blender EEVEE with screen-space raytracing, AgX Medium High
Contrast, a thin haze with a fog glow on the bright bits, one warm practical key and
a cool rim, mostly dark. It opens with the ident itself, untouched; one sprinkle
drops through its last frame. Every design is original: cake-pops on sticks (no
arms, no legs, they hop, sprinkles fall off them), Grandmaster Crumb, the Demon King.

Nothing here is licensed or sampled. The music is synthesized (see
`tools/trailer_audio/score.py`), the voices are Orpheus on kif.

## Layout

| Path | What |
|---|---|
| `timeline.py` | the cut: shot order, durations, where each voice line starts |
| `common.py` | the ident's render look, lights, camera rig, materials, rain, ash, fire |
| `chars.py` | Vanilla, Red Velvet, Funfetti, Crumb (cake-pops) and the Demon King |
| `shots.py`, `shots2.py`, `shots3.py` | one builder per shot; `build(shot_id)` makes the scene |
| `render.py` | Blender entry: renders a shot's frames |
| `kr.sh` | sends a render to kif, retries while the card is busy |
| `edit.py` | frames + cards + mix -> the mp4 |
| `../trailer_audio/` | `lines.json`, `vo.py` (Orpheus takes), `vo_post.py` (whisper picks the take, dresses each voice), `score.py`, `mix.py`, `vo/` (the dressed lines) |

## Rendering

No renders on the Mac. All Blender work goes to kif:

    tools/trailer/kr.sh city,horns,bakery            # full quality, frames land in ~/.local/share/cpdh-trailer/frames
    kif-render --dir tools/trailer tools/trailer/trailer.blend tools/trailer/render.py -- vanilla preview list=1,60

`preview` is half size at 16 samples; `list=1,60` or `f=1-24` limit the frames. A
frame at 1080p / 64 samples takes about 0.6 to 1.5 s on the 4090.

## Audio

    uv run --with numpy --with scipy python tools/trailer_audio/score.py score.wav
    uv run --with numpy --with scipy python tools/trailer_audio/mix.py score.wav mix.wav
    uv run --with pillow python tools/trailer/edit.py mix.wav cake-pop-demon-hunters.mp4

`vo.py` needs kif's Orpheus running (`voice-start` through the gate, Strata stopped
first) and mlx-audio for SNAC. The dressed lines in `trailer_audio/vo/` are kept so
the cut can be rebuilt without it.

Frames, videos and `raw/` takes are not committed.
