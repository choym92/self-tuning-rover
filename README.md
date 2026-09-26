# self-tuning-rover

A small wheeled robot built on a Jetson Orin Nano Super, with one idea at its center: **the robot's own logs are the test bench.** Every sensor stream is recorded with timestamps, replayed offline against ground truth, scored with objective metrics (RMSE, filter consistency), and the parameters — Kalman filter noise models, PID gains — are tuned in a loop. The tuning loop can be driven by hand, by grid or Bayesian search, or by an LLM; the point is that all of them are judged by the same replay harness, on logs they have not seen.

This is the shape of how autonomous-vehicle teams evaluate systems (log replay, ground truth, held-out scenarios), rebuilt at desk scale.

## Pipeline

```
RealSense D436 (depth + RGB + IMU) → AprilTag detection → range/bearing measurements
Wheel encoders (control input) ─────────────────────────┐
                                                        ▼
                                  Kalman filter (x, y, heading) → PID → motors
                                                        │
                       every stream logged with timestamps
                                                        ▼
        Mac: replay logs → score (RMSE vs ground truth, NIS) → propose parameters → replay …
```

Ground truth comes from AprilTags at surveyed positions; they are scaffolding, removed once a vision-only estimate can be scored against them.

## Current state and plans

Mutable state is kept out of this overview so it cannot silently go stale:

- current handoff and next actions: [`docs/STATUS.md`](docs/STATUS.md)
- purchase and parts status: [`docs/build-spec.md`](docs/build-spec.md)
- measured hardware/software results: [`docs/verify.md`](docs/verify.md)
- accepted and proposed choices: [`docs/decisions.md`](docs/decisions.md)

The stable development direction is pan-tilt tracking → timestamped logging →
AprilTag range/bearing → state estimation → wheel control → Mac replay and
scoring → parameter tuning → VSLAM/navigation. The current order within that
direction belongs in `docs/STATUS.md`.

## What is in this repository

| Path | Contents |
|---|---|
| [AGENTS.md](AGENTS.md) / [CLAUDE.md](CLAUDE.md) | Shared agent rules; Claude imports the same canonical instructions instead of maintaining a copy |
| [docs/STATUS.md](docs/STATUS.md) | Short current handoff: verified platform, active work, next steps and live-state checks |
| [docs/setup-log.md](docs/setup-log.md) | Dated log of every setup step, including what went wrong and why |
| [docs/decisions.md](docs/decisions.md) | Decisions and their reasons, hardest-to-reverse first |
| [docs/preflight.md](docs/preflight.md) | Checks written *before* each device-changing step: official sources, device facts, VERIFIED vs INFERENCE, fallback |
| [docs/verify.md](docs/verify.md) | Per-layer verification procedures and the measured values |
| [docs/build-spec.md](docs/build-spec.md) | Parts, SKUs, prices — actual purchases separated from plans |
| [docs/reference/](docs/reference/) | Dated research snapshots kept for reuse: NVIDIA devkit guide review (2026-09-23), parts-build BOM (2026-09-22), software plan (2026-09-22), lessons from other builds (2026-09-24), sources on running small LLMs on this board incl. the R36.4.7 CUDA allocation regression (2026-09-25). Not maintained; decisions.md is current |
| [scripts/](scripts/) | Guarded scripts: microSD flashing from a Mac, NVMe install on the Jetson |
| [jetson/](jetson/) | Code that runs on the robot (`requirements.txt` documents the Python environment) |
| [jetson/voice/](jetson/voice/README.md) | Live Mac microphone → Jetson Whisper base/en; CUDA build and first live transcript verified, wake word/VAD pending |
| [docs/voice-orchestration.md](docs/voice-orchestration.md) | Working voice/orchestration architecture, safety boundary, phased implementation and open UX decisions |
| [tools/](tools/) | Replay, scoring and tuning tools that run on the Mac (empty for now) |

## Things learned so far that are hard to find elsewhere

- balenaEtcher 2.1.7 cannot open images on Apple Silicon; a `dd` script with SHA-256 read-back does the same job with verification (`scripts/flash-jetson-sd-mac.sh`).
- JetPack 6 on the Orin Nano can be moved from microSD to NVMe without an Ubuntu host: write the same image to the SSD and change `root=` in the SSD copy's `extlinux.conf`. NVIDIA's own initrd, resize and bootloader scripts inside the image handle an NVMe root explicitly; the package upgrade to 36.4.7 left the edit alone (`docs/preflight.md` has the evidence).
- A `dd | head -c N | sha256sum` verification under `set -eo pipefail` dies silently of SIGPIPE; read an exact block count instead.
- RealSense IMU models lose the IMU on JetPack 6 because the kernel is built without `HID_SENSOR_HUB`. Two routes: build librealsense with `FORCE_RSUSB_BACKEND=ON`, or add the missing HID sensor modules (`docs/decisions.md`).
- The DP→HDMI output on this kit does not come back after screen blanking (nvidia-modeset VRR error); disable blanking.
- L4T R36.4.7 (the October 2025 security update) limits CUDA allocations: a 4 GiB `cudaMalloc` fails with 5 GiB reported free. NVIDIA fixed it in R36.5; moving there is an apt source change plus `dist-upgrade`, no reflash (`docs/preflight.md`).

## Working rules

- Files in this repository are in English.
- Before any command that changes the device: official documentation for the exact version, a known-issues search, read-only checks on the device, each claim labelled VERIFIED or INFERENCE, and a stated fallback. The log records what actually happened, including mistakes.
- This is a personal project; AI assistance is used throughout (research, scripts, tuning loop) and is part of the design.

## Hardware

Jetson Orin Nano Super Developer Kit (8 GB), T-FORCE G50 512 GB NVMe, SanDisk 64 GB microSD (fallback system), Inland DP→HDMI adapter. Ordered: RealSense D436. Planned: Waveshare UGV Rover PT Jetson Orin AI Kit (Acce), RTL8822CE WiFi card (AW-CB375NF), 18650 cells. Details and prices in `docs/build-spec.md`.
