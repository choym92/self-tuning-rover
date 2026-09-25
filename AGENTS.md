# Briefing for coding agents (Codex, Claude, or anyone new)

Read this first, then `README.md`. Everything durable about this project lives in this repository; nothing important is only in a chat.

## What this project is

A self-tuning rover on a Jetson Orin Nano Super (8 GB). The idea: every sensor stream is logged with timestamps, replayed on the Mac, scored against ground truth, and the filter/controller parameters are tuned in a loop. Personal project of Paul Cho (Data Science Lead, not a software engineer): explain what commands do, keep steps small, and never assume he watched a command run. Chat with him in Korean; write every repository file in English.

## The device and how to reach it

| Item | Value |
|---|---|
| Board | Jetson Orin Nano Super Developer Kit, 8 GB, hostname `paul-cho-jetson` |
| Address | `ssh paulcho@192.168.1.234` from the Mac on the home LAN (key login already set up; Ethernet). Prompt on the Jetson is `paulcho@paul-cho-jetson`, on the Mac `Pauls-MacBook-Pro` — check which one you are on before running anything |
| OS | JetPack 6.2.3 / Jetson Linux R36.5.2, kernel 5.15.199-tegra, CUDA 12.6, root on the 512 GB NVMe, MAXN_SUPER power mode |
| sudo | Needs a password. Never type or ask for it. Paul runs sudo commands himself in his own terminal; give him one command at a time with the expected output |
| Docker | 29.8.1 with the NVIDIA runtime. `paulcho` is **temporarily** in the `docker` group (added 2026-09-25 for the LLM test day; undo pending: `sudo gpasswd -d paulcho docker`) |
| Python | `~/venvs/robot` (3.10); `pyrealsense2` 2.58.4 from a source build in `~/src/librealsense/build/Release` (RSUSB backend, needed for the camera IMU on this kernel) |
| Read-only checks that need no sudo | `free -m`, `tegrastats --interval 1000` (RAM, GPU %, temperatures), `/sys/class/thermal/thermal_zone*/temp`, `journalctl -k -b`, `docker ps`, `docker logs` |

Other hardware: WiFi/Bluetooth card is built in (RTL8822CE, verified). RealSense D436 ordered 2026-09-24, not yet arrived. Waveshare UGV Rover PT Jetson Orin AI Kit (Acce) chosen but not ordered; four questions are with Waveshare support. Never insert the microSD while the NVMe system is running (identical filesystem UUIDs).

## Rules that are not negotiable

1. **One step at a time.** Propose, get an explicit go, run one step, report what actually happened, then the next. Do not run ahead, do not record decisions Paul has not made.
2. **Preflight before anything that changes the device** (installs on the host, boot config, firmware, kernel, system services). Template and past entries in `docs/preflight.md`: official source for the exact version, known-issues search, read-only device checks, every claim labelled VERIFIED or INFERENCE, a fallback, then the commands. Read-only checks and research need no preflight.
3. **Nothing installed on the host for experiments.** Use Docker containers, `~/models` (model files) and `~/llm` (build files, logs). No `daemon.json` edits, no systemd units, no swapfiles, no global npm/pip.
4. **Report faithfully.** If a command failed, say so with the output. If something was not verified, say so. Paul has been burned by confident claims that were wrong (a WiFi card "missing" that was there, parts marked "ordered" that were never bought). Label inferences.
5. **Commits:** plain messages, no "Co-Authored-By" or "Generated with" lines. English. Push to `origin main`.
6. Never edit a script while it is running. Reddit is blocked in every tool; do not try workarounds.
7. Files under the separate course repository (`cs7638-robotics/problem-sets`, `projects`) are off limits.

## Where to look, in this order

| File | What it holds |
|---|---|
| `README.md` | Status, next steps, layout |
| `docs/decisions.md` | Every decision and its reasons, newest additions near the end; open items are marked |
| `docs/verify.md` | Measured values with dates: device checks, the LLM benchmark tables, memory curves, the OOM investigation |
| `docs/preflight.md` | Checklist template plus one entry per device-changing step (NVMe move, two OS upgrades, the LLM container work) with outcomes |
| `docs/setup-log.md` | Chronological log of what was done and what went wrong |
| `docs/build-spec.md` | What was bought vs planned, prices, SKUs |
| `docs/reference/` | Dated research snapshots (not maintained; decisions.md is current) |
| `jetson/llm/` | `Dockerfile` (llama.cpp v0.5.0 with CUDA, built on `nvcr.io/nvidia/l4t-jetpack:r36.4.0`), `harness.py` + `prompts.json` (fixed 37-prompt evaluation), `render_results.py`, `results/comparison.md` (every question and every model's answer side by side), `README.md` (how to run, standard flags, scoring rubric) |
| `scripts/` | Guarded shell scripts used for the microSD flash and the NVMe install (history; do not run) |

## State of the LLM work (2026-09-25 evening)

- Image on the Jetson: `rover/llama_cpp:v0.5.0` (10.6 GB) and its base `nvcr.io/nvidia/l4t-jetpack:r36.4.0`. Models in `/home/paulcho/models`: `NVIDIA-Nemotron3-Nano-4B-Q4_K_M.gguf`, `gemma-4-E2B-it-Q4_K_M.gguf`, `Qwen3.5-4B-Q4_K_M.gguf`.
- Standard server command (the flags matter; the defaults leak ~245 MB per request on this board and the kernel kills the server):

```
docker run -d --name llm --runtime nvidia -p 127.0.0.1:8080:8080 -v /home/paulcho/models:/models \
  rover/llama_cpp:v0.5.0 llama-server -m /models/<file>.gguf -ngl 99 -np 1 -c 4096 \
  --load-mode none -b 512 -ub 512 -fa on --ctx-checkpoints 0 --cache-ram 0 --reasoning off \
  --host 0.0.0.0 --port 8080
```

- Harness from the Mac: `ssh -f -N -L 18080:127.0.0.1:8080 paulcho@192.168.1.234`, then `python3 jetson/llm/harness.py --url http://127.0.0.1:18080 --label <model-label>`; render tables with `python3 jetson/llm/render_results.py`. Stop the server with `docker rm -f llm`.
- Results so far: Nemotron 19.6 tok/s, Gemma 29.2, Qwen 16.0 (llama-bench). Tools 8/10, 8/10, 9–10/10. All honest 5/5. Korean works on all three (Qwen best). All three "think" by default; thinking must be off on the robot (`--reasoning off` works for all three, verified). Gemma and Nemotron have not yet been re-run with thinking off; Qwen has. Recommendation recorded in `docs/decisions.md` (Gemma default, Qwen alternative), **not decided by Paul yet**.
- Open tasks, in order: (1) re-run Gemma and Nemotron with `--reasoning off` for a fair round; (2) prompt set v2: a system-prompt line that general questions and text tasks are fine, and a clearer `look_at` description (all three got "camera to the right" wrong the same way); (3) speech pipeline prep without hardware: whisper.cpp CUDA in a container, Piper TTS (check Korean voices), WAV → whisper → LLM → Piper, measure latency and memory; (4) undo the docker group.

## Coming hardware steps (when parts arrive)

D436: `rs-enumerate-devices` → depth/RGB → IMU at 200 Hz for 10 minutes → Depth Quality Tool → pan-tilt tracking (milestone 0). UGV kit: mount the devkit, confirm the 12 V feed, gamepad teleop, read the ESP32 `T:1001` JSON feedback (wheel odometry, IMU), first timestamped logs, then build the ESP32 firmware from source with the community fix for low-speed cogging (`waveshareteam/ugv_base_ros` PR #11) — details in `docs/decisions.md`, "Robot base".
