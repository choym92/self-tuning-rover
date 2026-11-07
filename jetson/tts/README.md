# On-robot text-to-speech

Two CPU engines run as containers; nothing is installed on the Jetson host. Model files live in
`/home/paulcho/models/` and are mounted read-only.

| Engine | Folder | Container, port | Languages | Status |
|---|---|---|---|---|
| **Supertonic 3** (voice M1) | `supertonic/` | `rover-tts-st`, 8093 | 31, incl. Korean and English | **in use** (Paul, 2026-11-06) |
| Kokoro-82M fp32 | this folder | `rover-tts`, 8092 | English and others, no Korean | installed, off |

Both servers answer `POST /say` with a WAV (peak-normalised to -1 dBFS) and `GET /health` or `/`.
Measurements: `docs/verify.md`. Decision: `docs/decisions.md`.

## Supertonic 3

Build once (image `rover/supertonic:1.3.1`), then download the pinned assets (383 MB) into
`/home/paulcho/models/supertonic-3`:

```sh
scp -r jetson/tts/supertonic paulcho@192.168.1.238:tts/
ssh paulcho@192.168.1.238 'docker build -t rover/supertonic:1.3.1 ~/tts/supertonic'
ssh paulcho@192.168.1.238 'docker run --rm --user "$(id -u):$(id -g)" -e HF_HOME=/tmp/hf -v /home/paulcho/models/supertonic-3:/models rover/supertonic:1.3.1 python3 -c "
from huggingface_hub import snapshot_download
snapshot_download(\"supertone-oss-archive/supertonic-3\", revision=\"aafc6e32416a594460b32413efc49d7fe4ce6d46\", local_dir=\"/models\", allow_patterns=[\"onnx/*\",\"voice_styles/*\",\"config.json\",\"LICENSE\",\"README.md\"])"'
```

Run:

```sh
docker run -d --name rover-tts-st -p 127.0.0.1:8093:8093 -v /home/paulcho/models/supertonic-3:/models:ro rover/supertonic:1.3.1
```

Request fields: `text`, `lang` (`ko`, `en`, ...), `voice` (`F1`-`F5`, `M1`-`M5`; default `M1`), `steps` (5 fast to 12 best; default 8), `speed` (0.7-2.0; default 1.05).

## Kokoro (kept as an alternative)

`bash jetson/tts/build.sh` builds `rover/kokoro:0.6.1` and downloads the int8 model; the fp32 and
fp16 files were added by hand. fp16 does not work on the CPU runtime. Run:

```sh
docker run -d --name rover-tts -p 127.0.0.1:8092:8092 -v /home/paulcho/models/kokoro:/models:ro rover/kokoro:0.6.1
```

Request fields: `text`, `voice` (for example `af_jessica`, `am_adam`, `bm_george`), `speed`, `gain`.

## Licences

Supertonic 3 weights: OpenRAIL-M (use restrictions travel with the files); SDK MIT. Kokoro weights
Apache-2.0; `kokoro-onnx` MIT. Supertone archived its repositories in September 2026; everything
here runs offline from the pinned files.
