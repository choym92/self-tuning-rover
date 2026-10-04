# Current project status

Last reviewed: 2026-09-25 EDT

This is the short cross-agent handoff. It records current direction, not the
full evidence. Follow its links for measurements and history. Re-check live
processes and hardware instead of assuming this snapshot is still running.

## Platform

- VERIFIED: Jetson Orin Nano Super 8 GB, JetPack 6.2.3 / L4T R36.5.2, kernel
  5.15.199-tegra, CUDA 12.6, root on the 512 GB NVMe, MAXN_SUPER.
- VERIFIED: SSH from the Mac at `paulcho@192.168.1.234` with key login.
- DECIDED: experimental GPU workloads remain containerized; models live under
  `/home/paulcho/models`, builds and logs under `/home/paulcho/llm`.
- TEMPORARY: `paulcho` was added to the Docker group for the 2026-09-25 test
  session. Removal is pending: Paul must run `sudo gpasswd -d paulcho docker`
  and log out/in after the experiment day.

Read-only live checks:

```sh
ssh paulcho@192.168.1.234 'hostname; uname -r; free -m; docker ps'
lsof -nP -iTCP:18090 -sTCP:LISTEN
```

## Active focus: English voice input

- VERIFIED: `rover/whisper:v1.9.4` was built with CUDA for Orin sm_87. The
  multilingual base model checksum was verified at
  `/home/paulcho/models/ggml-base.bin`.
- DECIDED: voice recognition is English-only.
- VERIFIED: the first live Mac microphone → SSH → Jetson CUDA English STT run
  transcribed the test sentence correctly. Canonical transcript and timings:
  `docs/verify.md#whisper-baseen-live-stt-2026-09-25`.
- CURRENT LIMITATION: capture uses a fixed eight-second window. Wake word, VAD,
  routing, TTS, LLM connection and robot action are not implemented.
- PROPOSED architecture and open UX decisions:
  `docs/voice-orchestration.md`.
- LAST OBSERVED 2026-09-25 22:58 EDT: `rover-stt` used Jetson loopback 8090 and
  the Mac tunnel used loopback 18090. Re-check with the commands above.

Next steps:

1. Record a compact 5-10 phrase English STT baseline covering navigation,
   negation, stop, status and a general question.
2. Decide the first interaction: wake → acknowledgement → command, or support a
   one-breath wake phrase plus command immediately.
3. Define typed command/state contracts and test them against a fake robot API.

## LLM work

- VERIFIED: `rover/llama_cpp:v0.5.0`; Nemotron 3 Nano 4B, Gemma 4 E2B and
  Qwen3.5 4B models are present and benchmarked. Canonical measurements:
  `docs/verify.md#llm-on-the-jetson-llamacpp-v050-built-in-a-container-2026-09-25`.
- DECIDED: reasoning stays off on the robot. Mandatory server flags and runbook:
  `jetson/llm/README.md`.
- PROPOSED, not decided by Paul: Gemma as the fast default and Qwen as the
  higher tool-accuracy alternative. See `docs/decisions.md`.
- Pending: re-run Gemma and Nemotron with reasoning off; revise the general-task
  system prompt and `look_at` tool description.
- OpenClaw may receive a bounded later trial. NemoClaw is deferred on the 8 GB
  board. Research snapshot: `docs/reference/2026-09-25-agent-runtime-options.md`.

## Vision (2026-10-03)

- DECIDED: detector YOLO26s TensorRT FP16; owner recognition SCRFD + ArcFace R50 with
  the guided gallery `~/yolo/owner/paul_guided.npz` (34 shots). Evidence and costs in
  `docs/verify.md`; choices in `docs/decisions.md`.
- PLANNED by Paul (later): time-sharing between vision and the LLM on the 8 GB board
  (vision + LLM together measured near 7.3 of 7.6 GB). Pause or slow face
  recognition while the LLM answers; consider headless mode and loading a small LLM
  on demand.
- Pending: brother re-test with the 34-shot gallery; recognition on another day;
  speed-up (faces only inside person boxes, recognition in a separate thread).

## Hardware

- RealSense D436: arrived; first live depth + color + IMU check passed on the
  Jetson over USB 3 on 2026-10-03 (`docs/verify.md`). 10-minute IMU soak with video
  passed (0.006% gyro samples missing, 0 video drops). Still to do: depth accuracy
  against a tape measure. The Mac is not a usable live host.
- Waveshare UGV Rover PT Acce: selected but repository status says not ordered.
  Never promote the hypothetical assembled-rover discussion to a purchase fact.
- Final microphone: not purchased. Test the Waveshare audio board first; the
  planned fallback is a Seeed reSpeaker XVF3800 USB four-mic array.

## Documentation health

- `AGENTS.md` is stable policy and a task-based document router.
- `CLAUDE.md` imports `AGENTS.md`; do not duplicate it.
- This file is the only current-state handoff.
- Historical setup and research files are not mandatory reading. Search and
  open only the section relevant to the current task.
