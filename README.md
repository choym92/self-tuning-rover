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

- **Compute ready.** Jetson Orin Nano Super, JetPack 6.2.3 / L4T 36.5.2 (upgraded from 36.4.7 on 2026-09-25 to fix a CUDA allocation regression), booting from a 512 GB NVMe (moved from microSD without an Ubuntu host — see `docs/decisions.md`), MAXN_SUPER, SSH from the Mac.
- **Camera software ready.** librealsense 2.58.4 built with the RSUSB backend so the camera IMU works on the JetPack 6 kernel (which ships without HID sensor drivers); `pyrealsense2` importable in `~/venvs/robot`. The RealSense D436 was ordered on 2026-09-24.
- **Base chosen (order pending).** Waveshare UGV Rover PT Jetson Orin AI Kit, "Acce" version (no Jetson): 6-wheel skid-steer aluminium chassis, four encoder motors with PID on an ESP32 sub-controller (JSON over serial, 660 pulses/rev), base IMU, 2-DOF pan-tilt with serial-bus servos, 3S 18650 UPS, audio board, gamepad and web app. Reasons and firmware facts in `docs/decisions.md`.
- **Not started.** Logging, AprilTag, filter, controller, replay harness.

## Next steps

| Buy | Then, when it arrives |
|---|---|
| RealSense D436 — ordered | Plug into a USB 3 port → `rs-enumerate-devices` → depth + RGB streams → **IMU at 200 Hz for 10 min with no frame drops** (Route A; else Route B in decisions.md) → Depth Quality Tool → first recorded `.bag` → pan-tilt visual tracking demo (milestone 0) |
| UGV Rover PT Jetson Orin AI Kit Acce (Waveshare, SKU 27772) + 3× 18650 cells + charger | Mount the Jetson devkit board, confirm 12 V feed → gamepad teleop → read the `T:1001` feedback stream (wheel speeds, odometry, IMU) → first timestamped logs → encoder counts per revolution, 1 m push test (see verify.md) |
| WiFi card: Waveshare AW-CB375NF (RTL8822CE, antennas included) — when the base is close | Check `modinfo rtl8822ce` first; power off, seat the card under the module, antennas on the chassis rail → `nmcli device wifi connect` → DHCP reservation → SSH alias |
| Later: 2D lidar (D500 or RPLidar C1, ~$100) only if VSLAM proves fragile; reSpeaker mic array only if the kit's audio board is not enough | — |

Software order: pan-tilt tracking loop (first tuning-by-replay experiment) → timestamped logging → AprilTag range/bearing → Kalman filter → wheel PID → Mac replay harness → tuning loop → VSLAM / navigation.

## What is in this repository

| Path | Contents |
|---|---|
| [docs/setup-log.md](docs/setup-log.md) | Dated log of every setup step, including what went wrong and why |
| [docs/decisions.md](docs/decisions.md) | Decisions and their reasons, hardest-to-reverse first |
| [docs/preflight.md](docs/preflight.md) | Checks written *before* each device-changing step: official sources, device facts, VERIFIED vs INFERENCE, fallback |
| [docs/verify.md](docs/verify.md) | Per-layer verification procedures and the measured values |
| [docs/build-spec.md](docs/build-spec.md) | Parts, SKUs, prices — actual purchases separated from plans |
| [docs/reference/](docs/reference/) | Dated research snapshots kept for reuse: NVIDIA devkit guide review (2026-09-23), parts-build BOM (2026-09-22), software plan (2026-09-22), lessons from other builds (2026-09-24), sources on running small LLMs on this board incl. the R36.4.7 CUDA allocation regression (2026-09-25). Not maintained; decisions.md is current |
| [scripts/](scripts/) | Guarded scripts: microSD flashing from a Mac, NVMe install on the Jetson |
| [jetson/](jetson/) | Code that runs on the robot (`requirements.txt` documents the Python environment) |
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
