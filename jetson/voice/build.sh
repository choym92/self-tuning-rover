#!/usr/bin/env bash
# Run on the Jetson only. Default: read-only checks. --build requires a separate go.
set -euo pipefail
mode="${1:---check}"
[[ "$mode" == "--check" || "$mode" == "--build" ]] || { echo 'Use --check or --build'; exit 2; }
[[ "$(uname -s)" == Linux && "$(uname -m)" == aarch64 ]] || { echo 'Refusing: expected Linux aarch64 Jetson'; exit 1; }
[[ "$(hostname)" == paul-cho-jetson ]] || { echo 'Refusing: unexpected hostname'; exit 1; }
grep -q 'REVISION: 5.2' /etc/nv_tegra_release
[[ "$(uname -r)" == 5.15.199-tegra ]] || { echo 'Refusing: preflight kernel changed'; exit 1; }
cd -- "$(dirname -- "$0")"
[[ "$PWD" == /home/paulcho/llm/voice ]] || { echo 'Refusing: expected /home/paulcho/llm/voice'; exit 1; }
docker info --format '{{json .Runtimes}}' | grep -q '"nvidia"'
docker image inspect nvcr.io/nvidia/l4t-jetpack:r36.4.0 >/dev/null
available_kb=$(df -Pk . | awk 'END {print $4}')
[[ "$available_kb" -gt 10485760 ]] || { echo 'Refusing: need at least 10 GiB free'; exit 1; }
echo 'Identity, runtime, base image, path and free disk checks passed.'
if [[ "$mode" == --check ]]; then
    echo 'Check only: no build or download performed.'
    exit 0
fi
docker build --build-arg WHISPER_TAG=v1.9.4 -t rover/whisper:v1.9.4 .
docker run --rm --runtime nvidia rover/whisper:v1.9.4 whisper-server --help
