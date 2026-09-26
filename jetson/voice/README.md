# Live Mac microphone → Jetson Whisper base

Status: Jetson CUDA image, model, service, SSH transport and the first live Mac
microphone transcription were verified on 2026-09-25. English is the selected
language. Python 3 standard library; Mac also uses the existing FFmpeg (8.1.1
observed). Jetson dependencies live inside Docker.

The Mac streams 16 kHz mono int16 PCM as it is captured, through an SSH tunnel.
The Jetson bridge buffers one bounded utterance in RAM, wraps it in WAV and
calls a persistent local whisper-server. Speech recognition runs on Jetson.
Audio upload is live; transcription starts after capture ends. This is not
incremental transcription. For this first baseline, the window is fixed (8 s
default, 30 s maximum). Wake word, VAD, TTS and agents are later steps.

## Local validation (no Jetson or microphone needed)

```sh
python3 -B -m unittest discover -s jetson/voice -p 'test_*.py' -v
bash -n jetson/voice/build.sh
```

## Execution, one approved step at a time

Steps 1-4 completed on 2026-09-25. Re-check
`docs/preflight.md`, current free memory, running GPU containers and temporary
Docker membership before execution. Stop if Docker needs sudo: Paul runs sudo
himself. Do not install on the host to resolve a build failure.

1. Stage on Jetson from the Mac repository root, after approval:

```sh
ssh paulcho@192.168.1.234 'mkdir -p /home/paulcho/llm/voice'
scp jetson/voice/Dockerfile jetson/voice/.dockerignore jetson/voice/protocol.py jetson/voice/bridge.py jetson/voice/build.sh paulcho@192.168.1.234:/home/paulcho/llm/voice/
ssh paulcho@192.168.1.234 'bash /home/paulcho/llm/voice/build.sh --check'
```

2. Build in a Jetson terminal. Logs stay under the allowed experiment directory:

```sh
bash /home/paulcho/llm/voice/build.sh --build > /home/paulcho/llm/voice/build.log 2>&1
```

3. Download multilingual **base**, not base.en, using the built container.
The SHA-1 is the published integrity checksum in the pinned upstream model list;
it is not a cryptographic signature. An existing target is never overwritten.

```sh
docker run --rm --user "$(id -u):$(id -g)" -v /home/paulcho/models:/models rover/whisper:v1.9.4 sh -ec '
test ! -e /models/ggml-base.bin
test ! -e /models/ggml-base.bin.part
curl -fL --retry 3 https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin -o /models/ggml-base.bin.part
echo "465707469ff3a37a2b9b8d8f89f2f99de7299dac  /models/ggml-base.bin.part" | sha1sum -c -
mv /models/ggml-base.bin.part /models/ggml-base.bin'
```

4. Start the service in a Jetson terminal. Keep this terminal open. First run
tests STT alone; do not automatically stop any existing LLM workload.

```sh
docker run --rm --name rover-stt --runtime nvidia \
  -p 127.0.0.1:8090:8090 -v /home/paulcho/models:/models:ro \
  rover/whisper:v1.9.4
```

Require startup logs showing the Orin CUDA device/backend and loaded multilingual
base model, then `Ready: 0.0.0.0:8090; language=en`. A CUDA build flag alone does
not prove GPU inference.
Whisper's internal HTTP server is loopback-only inside the container. The PCM
bridge has no authentication; never publish its port on all host interfaces.

5. In a Mac terminal, keep an SSH tunnel open:

```sh
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:18090:127.0.0.1:8090 paulcho@192.168.1.234
```

6. List Mac microphones (FFmpeg can exit nonzero after listing; expected):

```sh
ffmpeg -hide_banner -f avfoundation -list_devices true -i ''
```

7. In another Mac terminal, replace `0` with the desired **audio** device index.
Allow microphone access for the terminal when macOS asks. A first permission
dialog can delay or fail capture; grant permission and repeat the run.

```sh
python3 jetson/voice/mac_stream.py --device 0 --seconds 8 --out jetson/voice/results/base.jsonl
```

Speak after `Microphone is streaming.` Keep the sentence short enough to fit
the window. The first line is a preparation notice, not a ready microphone.
Try natural requests such as `Hey Jetson, go to the kitchen`, `Hey Jetson,
don't go to the kitchen`, `Hey Jetson, stop`, and `Hey Jetson, what's the
weather today?`. Run several times and distinguish the
first (cold inference) from later requests. Transcripts are saved only with
`--out`; no raw audio is saved. Ctrl-C stops the client and closes its connection.

## Timing definitions

All durations use monotonic clocks on their own host; no Mac/Jetson clock sync
is assumed. No number is labelled pure one-way network latency.

| Field | Meaning |
|---|---|
| `transport_rtt_s` | Small application ping/pong through SSH; includes scheduling |
| `capture_startup_s` | Capture launch to first PCM bytes (includes mic permission/startup) |
| `capture_and_send_s` | Capture launch through final send; includes recording time |
| `upload_tail_ack_s` | Final send to Jetson receipt acknowledgment; an upload-tail round trip, not full recording/upload duration |
| `server_receive_s` | Jetson's receive window; includes real-time capture pacing |
| `server_inference_api_s` | Local Whisper HTTP request elapsed time; includes decoding and API overhead, not isolated GPU kernel time |
| `server_processing_s` | WAV/multipart preparation plus local Whisper API request |
| `post_capture_result_s` | Final send through received transcript; not physical end-of-speech latency |
| `transport_and_overhead_residual_s` | Post-capture time minus server processing; includes transport/buffering/scheduling; may be slightly negative due to overlap |
| `total_s` | Connection start through transcript; includes fixed recording window |

Real VAD/end-of-speech latency and final robot microphone quality are untested.
For deterministic transport tests, `--wav input.wav` sends a <=30s mono 16kHz
int16 WAV without real-time pacing. Never compare its capture timing with live
microphone runs. Unit tests use a fake backend and do not measure STT accuracy.

## Stop and rollback

Stop just this service using `docker stop rover-stt` (the `--rm` container is
removed automatically), then Ctrl-C the Mac SSH tunnel. This leaves the image
and model reusable. Removing `rover/whisper:v1.9.4` and the exact `ggml-base.bin`
file is a separate cleanup step; do not remove the shared JetPack base image or
the existing LLM models. Failed downloads leave `.part` for inspection.
