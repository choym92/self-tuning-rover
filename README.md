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

## Status (2026-09-24)

- **Compute ready.** Jetson Orin Nano Super, JetPack 6.2.1 / L4T 36.4.7, booting from a 512 GB NVMe (moved from microSD without an Ubuntu host — see `docs/decisions.md`), MAXN_SUPER, SSH from the Mac.
- **Camera software ready.** librealsense 2.58.4 built with the RSUSB backend so the camera IMU works on the JetPack 6 kernel (which ships without HID sensor drivers); `pyrealsense2` importable in `~/venvs/robot`. The camera itself (RealSense D436) is not bought yet.
- **Not started.** Robot base (wheeled, built from parts with encoder motors), WiFi card, logging, AprilTag, filter, controller, replay harness.

## What is in this repository

| Path | Contents |
|---|---|
| [docs/setup-log.md](docs/setup-log.md) | Dated log of every setup step, including what went wrong and why |
| [docs/decisions.md](docs/decisions.md) | Decisions and their reasons, hardest-to-reverse first |
| [docs/preflight.md](docs/preflight.md) | Checks written *before* each device-changing step: official sources, device facts, VERIFIED vs INFERENCE, fallback |
| [docs/verify.md](docs/verify.md) | Per-layer verification procedures and the measured values |
| [docs/build-spec.md](docs/build-spec.md) | Parts, SKUs, prices |
| [research/](research/) | Research notes (camera, Jetson, platforms, community, DIY BOM, software plan); `sentdex/` has notes on 21 videos. Written in Korean; translation pending |
| [scripts/](scripts/) | Guarded scripts: microSD flashing from a Mac, NVMe install on the Jetson |
| [jetson/](jetson/) | Code that runs on the robot (`requirements.txt` documents the Python environment) |
| [tools/](tools/) | Replay, scoring and tuning tools that run on the Mac (empty for now) |

## Things learned so far that are hard to find elsewhere

- balenaEtcher 2.1.7 cannot open images on Apple Silicon; a `dd` script with SHA-256 read-back does the same job with verification (`scripts/flash-jetson-sd-mac.sh`).
- JetPack 6 on the Orin Nano can be moved from microSD to NVMe without an Ubuntu host: write the same image to the SSD and change `root=` in the SSD copy's `extlinux.conf`. NVIDIA's own initrd, resize and bootloader scripts inside the image handle an NVMe root explicitly; the package upgrade to 36.4.7 left the edit alone (`docs/preflight.md` has the evidence).
- A `dd | head -c N | sha256sum` verification under `set -eo pipefail` dies silently of SIGPIPE; read an exact block count instead.
- RealSense IMU models lose the IMU on JetPack 6 because the kernel is built without `HID_SENSOR_HUB`. Two routes: build librealsense with `FORCE_RSUSB_BACKEND=ON`, or add the missing HID sensor modules (`docs/decisions.md`).
- The DP→HDMI output on this kit does not come back after screen blanking (nvidia-modeset VRR error); disable blanking.

## Working rules

- Files in this repository are in English.
- Before any command that changes the device: official documentation for the exact version, a known-issues search, read-only checks on the device, each claim labelled VERIFIED or INFERENCE, and a stated fallback. The log records what actually happened, including mistakes.
- This is a personal project; AI assistance is used throughout (research, scripts, tuning loop) and is part of the design.

## Hardware

Jetson Orin Nano Super Developer Kit (8 GB), T-FORCE G50 512 GB NVMe, SanDisk 64 GB microSD (fallback system), Inland DP→HDMI adapter. Planned: RealSense D436, Waveshare AC8265 WiFi, a wheeled base with encoder motors, a far-field USB microphone array. Details and prices in `docs/build-spec.md`.
