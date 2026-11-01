#!/usr/bin/env bash
# Save YouTube transcripts as Markdown for personal study, one file per video.
# Output goes to private/transcripts/ (gitignored: lecture transcripts are not ours to publish).
# Usage: scripts/fetch-youtube-transcripts.sh VIDEO_ID [VIDEO_ID ...]
# With no IDs it fetches the Stanford CS329A playlist (9 videos).
set -euo pipefail

VENV="$HOME/venvs/yt"
OUT="$(cd "$(dirname "$0")/.." && pwd)/private/transcripts"

if [ ! -x "$VENV/bin/youtube_transcript_api" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet youtube-transcript-api
fi

if [ "$#" -eq 0 ]; then
  set -- 6YnLB0XbTnI -Ggc37xLj_Y p7TdPUcPoik Lxh9RF5S-K0 Ml_fp9XkB8Y yVnmHSAy3ck Uni9dqyuuDM 8JAqLnTaZu4 AyO6wyu4DEg
fi

mkdir -p "$OUT"
n=0
for id in "$@"; do
  n=$((n + 1))
  file="$OUT/$(printf '%02d' "$n")-$id.md"
  {
    echo "# https://www.youtube.com/watch?v=$id"
    echo
    "$VENV/bin/youtube_transcript_api" -- "$id" --format text
  } > "$file" && echo "saved $file" || echo "FAILED $id" >&2
done
