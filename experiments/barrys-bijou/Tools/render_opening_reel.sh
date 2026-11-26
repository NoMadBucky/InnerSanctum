#!/bin/bash
# Build the distribution print from the original Core Graphics animation and piano master.
set -euo pipefail
cd "$(dirname "$0")/.."
scratch=$(mktemp -d "${TMPDIR:-/tmp}/bijou-print.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
xcrun swiftc -parse-as-library -O Bijou/Playbill.swift Tools/OpeningReel/{Timing,main}.swift \
    Tools/render_reel_piano.swift -o "$scratch/draw"
"$scratch/draw" "$scratch/piano.wav"
"$scratch/draw" | ffmpeg -nostdin -v error -f rawvideo -pixel_format bgra -video_size 960x720 -framerate 60 \
    -i pipe:0 -i "$scratch/piano.wav" -map 0:v:0 -map 1:a:0 -c:v libx264 -preset medium -crf 21 \
    -pix_fmt yuv420p -colorspace bt709 -color_primaries bt709 -color_trc bt709 -c:a aac -b:a 128k \
    -movflags +faststart "$scratch/print.mp4"
mv "$scratch/print.mp4" Bijou/BijouOpening.mp4
