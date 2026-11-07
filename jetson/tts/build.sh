#!/usr/bin/env bash
# Build the Kokoro TTS image and fetch the model files on the Jetson. Nothing touches the host
# outside Docker and /home/paulcho/models/kokoro. Re-running skips files that already exist.
#   bash build.sh --check   # read-only guards only
#   bash build.sh           # build image rover/kokoro:0.6.1 and download the two model files
set -euo pipefail
MODE="${1:-run}"
HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS=/home/paulcho/models/kokoro
BASE=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1
IMAGE=rover/kokoro:0.6.1

fail() { echo "REFUSED: $*" >&2; exit 1; }
[ "$(hostname)" = "paul-cho-jetson" ] || fail "not paul-cho-jetson"
[ "$(uname -m)" = "aarch64" ] || fail "not aarch64"
docker info >/dev/null 2>&1 || fail "docker not usable without sudo"
avail_mb=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
[ "$avail_mb" -ge 1200 ] || fail "only ${avail_mb} MB available; stop a container first"
free_gb=$(df -BG --output=avail /home | tail -1 | tr -dc 0-9)
[ "$free_gb" -ge 5 ] || fail "less than 5 GB free on /home"
echo "guards passed (RAM available ${avail_mb} MB, disk ${free_gb} GB)"
[ "$MODE" = "--check" ] && { echo "--check: nothing built or downloaded"; exit 0; }

mkdir -p "$MODELS"
for f in kokoro-v1.0.int8.onnx voices-v1.0.bin; do
  if [ -s "$MODELS/$f" ]; then echo "have $f"; continue; fi
  curl -fL --retry 3 -o "$MODELS/$f.part" "$BASE/$f" && mv "$MODELS/$f.part" "$MODELS/$f"
  echo "downloaded $f ($(stat -c %s "$MODELS/$f") bytes)"
done
docker build -t "$IMAGE" "$HERE"
echo "built $IMAGE"
