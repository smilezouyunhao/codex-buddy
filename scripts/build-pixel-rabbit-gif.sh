#!/usr/bin/env bash
set -euo pipefail

source_image="${1:?usage: build-pixel-rabbit-gif.sh SOURCE_PNG OUTPUT_GIF}"
output_gif="${2:?usage: build-pixel-rabbit-gif.sh SOURCE_PNG OUTPUT_GIF}"
output_dir="$(dirname "$output_gif")"
frames_dir="$output_dir/frames"

mkdir -p "$frames_dir"

# Eight equal cells across the generated 1983 px sheet. Flatten the slight
# backdrop variation, then reduce to a 128 px logical canvas and scale 2x with
# point sampling so every edge stays deliberately blocky.
for i in {0..7}; do
  x=$((i * 248))
  magick "$source_image" \
    -crop "248x330+${x}+220" +repage \
    -fuzz 7% -fill '#dcf1dd' -opaque '#dcf1dd' \
    -background '#dcf1dd' -gravity center -extent 330x330 \
    -filter point -resize 128x128! \
    -filter point -resize 256x256! \
    "$frames_dir/frame-${i}.png"
done

magick \
  -delay 26 "$frames_dir/frame-0.png" \
  -delay 12 "$frames_dir/frame-1.png" \
  -delay 10 "$frames_dir/frame-2.png" \
  -delay 9  "$frames_dir/frame-3.png" \
  -delay 15 "$frames_dir/frame-4.png" \
  -delay 10 "$frames_dir/frame-5.png" \
  -delay 15 "$frames_dir/frame-6.png" \
  -delay 22 "$frames_dir/frame-7.png" \
  -loop 0 -layers Optimize "$output_gif"
