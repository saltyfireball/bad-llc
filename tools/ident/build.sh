#!/usr/bin/env bash
# Bad Omen studio ident: mux the rendered frames and the sting into the
# delivery files (SLRM-1922).
#
#   tools/ident/build.sh
#
# Needs the frames from
#   blender -b --factory-startup -P tools/ident/scene.py -- --render
# in tools/ident/out/frames (frame_0001.png .. frame_0216.png, 24 fps).
# The sting is synthesized by tools/ident/sting.py if out/sting.wav is
# missing.
#
# Writes to tools/ident/out/:
#   ident.mp4         1920x1080 H.264 high, yuv420p, CRF 18, AAC 192k, faststart
#   ident.webm        1920x1080 VP9 CRF 32, Opus 128k
#   ident-silent.mp4  as ident.mp4 without audio
#   ident-poster.jpg  frame 200, 1920x1080
#   web/              1280x720 copies sized for the site
# and copies the web copies to public/kit/v1/ident/ (ident.mp4, ident.webm,
# ident-poster.jpg).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="$HERE/out"
FRAMES="$OUT/frames"
WAV="$OUT/sting.wav"
WEB="$OUT/web"
KIT="$REPO/public/kit/v1/ident"
FPS=24
NFRAMES=216
POSTER_FRAME=200
# web size targets in bytes
MP4_MAX=$((3000 * 1024))
WEBM_MAX=$((2500 * 1024))

log() { printf '[build] %s\n' "$*"; }
size() { stat -f %z "$1" 2>/dev/null || stat -c %s "$1"; }

n=$(ls "$FRAMES"/frame_*.png 2>/dev/null | wc -l | tr -d ' ')
if [ "$n" -ne "$NFRAMES" ]; then
    echo "expected $NFRAMES frames in $FRAMES, found $n; render first" >&2
    exit 1
fi
if [ ! -f "$WAV" ]; then
    log "sting.wav missing, synthesizing"
    (cd "$REPO" && uv run --with numpy --with scipy python tools/ident/sting.py)
fi

FF=(ffmpeg -hide_banner -loglevel error -y)
IN=(-framerate "$FPS" -i "$FRAMES/frame_%04d.png")
DUR=$(awk "BEGIN { print $NFRAMES / $FPS }")
mkdir -p "$WEB"

log "ident.mp4"
"${FF[@]}" "${IN[@]}" -i "$WAV" -map 0:v -map 1:a -t "$DUR" \
    -c:v libx264 -profile:v high -preset slow -crf 18 -pix_fmt yuv420p \
    -c:a aac -b:a 192k -movflags +faststart "$OUT/ident.mp4"

log "ident-silent.mp4"
"${FF[@]}" "${IN[@]}" -an \
    -c:v libx264 -profile:v high -preset slow -crf 18 -pix_fmt yuv420p \
    -movflags +faststart "$OUT/ident-silent.mp4"

log "ident.webm"
"${FF[@]}" "${IN[@]}" -i "$WAV" -map 0:v -map 1:a -t "$DUR" \
    -c:v libvpx-vp9 -crf 32 -b:v 0 -row-mt 1 -pix_fmt yuv420p \
    -c:a libopus -b:a 128k "$OUT/ident.webm"

log "ident-poster.jpg"
"${FF[@]}" -i "$FRAMES/$(printf 'frame_%04d.png' "$POSTER_FRAME")" \
    -q:v 3 "$OUT/ident-poster.jpg"

# Web copies: 1280x720, the lowest CRF that fits the size target, so the
# dark gradients keep as many bits as the budget allows.
SCALE=(-vf "scale=1280:720:flags=lanczos")
for crf in 20 22 24 26 28; do
    log "web ident.mp4 crf $crf"
    "${FF[@]}" "${IN[@]}" -i "$WAV" -map 0:v -map 1:a -t "$DUR" "${SCALE[@]}" \
        -c:v libx264 -profile:v high -preset slow -tune film -crf "$crf" \
        -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart "$WEB/ident.mp4"
    [ "$(size "$WEB/ident.mp4")" -le "$MP4_MAX" ] && break
done
for crf in 34 36 38 40 42; do
    log "web ident.webm crf $crf"
    "${FF[@]}" "${IN[@]}" -i "$WAV" -map 0:v -map 1:a -t "$DUR" "${SCALE[@]}" \
        -c:v libvpx-vp9 -crf "$crf" -b:v 0 -row-mt 1 -pix_fmt yuv420p \
        -c:a libopus -b:a 96k "$WEB/ident.webm"
    [ "$(size "$WEB/ident.webm")" -le "$WEBM_MAX" ] && break
done
"${FF[@]}" -i "$FRAMES/$(printf 'frame_%04d.png' "$POSTER_FRAME")" "${SCALE[@]}" \
    -q:v 4 "$WEB/ident-poster.jpg"

cp "$WEB/ident.mp4" "$WEB/ident.webm" "$WEB/ident-poster.jpg" "$KIT/"

for f in "$OUT/ident.mp4" "$OUT/ident.webm" "$OUT/ident-silent.mp4" \
         "$OUT/ident-poster.jpg" "$KIT/ident.mp4" "$KIT/ident.webm" \
         "$KIT/ident-poster.jpg"; do
    printf '%10d  %s\n' "$(size "$f")" "${f#"$REPO"/}"
done
