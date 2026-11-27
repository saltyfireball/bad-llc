#!/bin/sh
# kr.sh SHOT[,SHOT...] [render.py args] : full render on kif into ~/.local/share/cpdh-trailer/frames
# retries while kif's card is busy (exit 75).
cd "$(dirname "$0")/../.." || exit 1
OUT="$HOME/.local/share/cpdh-trailer/frames"
mkdir -p "$OUT"
while :; do
  kif-render -t 14400 -o "$OUT/$1.job" --dir tools/trailer tools/trailer/trailer.blend tools/trailer/render.py -- "$@"
  rc=$?
  [ "$rc" -eq 75 ] || break
  echo "kif busy, retrying in 60 s"
  sleep 60
done
# flatten: job out/ has <shot>/frame_*.png
for s in $(echo "$1" | tr ',' ' '); do
  mkdir -p "$OUT/$s"
  [ -d "$OUT/$1.job/$s" ] && cp -R "$OUT/$1.job/$s/." "$OUT/$s/"
done
exit $rc
