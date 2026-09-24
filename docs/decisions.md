# Decisions and Reasons

Hardest-to-reverse first. For answering "why did we do this?" later.

---

## AI use: unrestricted — personal project (2026-09-23)

- The robot is a personal project. AI is used fully: writing code, tuning parameters, and an LLM-driven tuning loop.
- The course's no-generative-AI rule is not imposed on this project. It would only apply to something submitted for the Hardware Challenge extra credit — check Ed #50/#51 if and when that happens.

---

## Install JetPack 6.x, not 7.2.1 (2026-09-23)

1. Board firmware is 36.4.7 → **JetPack 6 generation**. It matches as-is; no firmware change needed.
2. Most RealSense D435i success reports are on JetPack 6; there are instability reports on JetPack 7 (community forum/GitHub reports, 2025–2026; no first-party statement either way).
3. Isaac ROS 3.x targeted JetPack 6 when this was written. *Audit 2026-09-24:* Isaac ROS 4.6 (2026) moved its supported stack to JetPack 7.2 + ROS 2 Jazzy — see the re-check below.
4. Super mode is supported from **JetPack 6.2** (NVIDIA blog "JetPack 6.2 Brings Super Mode…", 2025-01-16) → no performance loss on 6.2.1. *(Audit 2026-09-24: an earlier draft said 6.1; corrected.)*
5. **Asymmetric reversibility**: installing 7 moves the firmware to the 7 generation; going back to 6 requires re-flashing from an Ubuntu host. Online downgrade is not supported.

Why the board ships with JetPack 6 firmware: the firmware was built 2025-09-18 (read from the board). JetPack 7.2 (2026-06) was the first 7.x release to cover the Orin Nano, and JetPack 7.2.1 followed on 2026-08-12 (JetsonHacks release note; NVIDIA JetPack archive). The hardware is current — only the factory software predates JetPack 7.

**Update (same day)**: there is a **Windows** PC at home.
- SDK Manager runs on Windows through WSL2, but NVIDIA's SDK Manager docs list Windows support (from JetPack 6.2.1) for **AGX Orin and AGX Thor** only; Orin Nano is not listed, and "flashing an external storage device is not supported via WSL2" (docs.nvidia.com/sdk-manager, WSL page; audited 2026-09-24).
- NVIDIA forum threads report Orin Nano flashes failing on WSL/Windows with USB connection errors.
- The reliable route would be dual-booting Ubuntu 22.04 on that PC (half a day of work).
- → Point 5 is only partly mitigated ("reversible, but painful"). **Keep JetPack 6.x; the case for it got stronger.**
- SDK Manager also needs a jumper wire to put the Jetson into recovery mode.
- Uses for the USB flash drive: JetPack 7 USB installer, or an Ubuntu installer for the PC.

**Re-checked 2026-09-24 (would JetPack 7 fix the RealSense IMU?)** — No. librealsense 2.58.4 supports JetPack 7.2 through the same kernel-patch script (`patch-realsense-ubuntu-L4T.sh`), and its release notes carry the line "IMU stream is not working well on latest versions"; the two IMU routes (RSUSB build, or added HID sensor modules) are the same on 7 as on 6. Costs of moving now: full reinstall (official USB ISO from the Mac — that part is easy), firmware moves to the 7 generation so the JetPack 6 microSD fallback stops booting and going back needs an Ubuntu host (a "downgrade 7.2 → 6.2" forum thread exists, Aug 2026), and fewer RealSense success reports on 7. The one pull toward 7: Isaac ROS 4.6 moved its supported stack to JetPack 7.2 + ROS 2 Jazzy (JetPack 6 + Humble is now the previous generation). Decision: stay on 6.2.1; revisit JetPack 7 after the camera is proven and only if Isaac ROS 4.6 / JP7-only features are actually needed.

## Write the SD card with `dd` instead of Etcher (2026-09-23)

- Etcher 2.1.7 cannot open source files on Apple Silicon (known bug, GitHub #4672).
- `dd` writes the same bytes Etcher would; the script adds Etcher's safety (target checks) and its verification (full SHA-256 compare).

## Defer the depth camera (D435i) (2026-09-23)

- The graded work (Kalman filter + PID) is covered by a webcam + AprilTag.
- AprilTag range/bearing matches the course's landmark-based localization better than depth does.
- The D435i's value ($410) is "accurate distance with consistent error". It pays off for marker-free distance or obstacle maps.
- Prerequisite: confirm librealsense works on the installed JetPack.
  - **2026-09-23 software pre-check (no camera yet)**: PyPI has prebuilt `pyrealsense2` wheels for our exact platform — `pyrealsense2-2.58.4.10922-cp310-cp310-manylinux2014_aarch64.whl` (Python 3.10 on ARM64 = the Jetson's Python 3.10.12). aarch64 cp310 wheels exist for 2.58.0 through 2.58.4. ~~→ No source build of librealsense needed for the Python binding.~~ *Superseded 2026-09-24:* the wheel imports fine but uses the kernel (V4L2/HID) path, which cannot deliver the IMU on the JetPack 6 kernel — a source build with the RSUSB backend was needed after all (see the IMU caveat below).
  - Still unverified until the camera is plugged in: device detection and IMU streams on kernel 5.15.148-tegra. ~~Amazon's return window covers this.~~ *Corrected 2026-09-24:* buying from the official store, whose returns are for unopened items only; the software-side risk was reduced instead by the RSUSB build and the udev rule (both done before ordering).
  - The Jetson image has no `pip`; needs `sudo apt install python3-pip python3-venv` before installing the wheel.
- A used unit can be checked numerically: On-Chip Calibration Health-Check and the Depth Quality Tool (subpixel RMS < 0.1).
- Model names: **i = IMU, f = IR-pass filter**. The D435f has no IMU.
- **2026-09-23 official lineup and prices** (read directly from realsenseai.com/compare-all-cameras and store.realsenseai.com):
  - The official store sells the **D435i new for $334** — cheaper than Amazon (used $409.99, new $499–519). Buy from the official store, not Amazon (check shipping/tax at checkout).
  - **D435if, $354 (new)**: same 0.3–3 m range, FOV, global-shutter depth and IMU as the D435i, plus an IR-pass filter that the official page says reduces false detections from light reflections and repetitive patterns — the glare problem from our camera research. Was the pick until the D436 check below.
  - **D436 ($354) — current pick as of 2026-09-24 (order pending)**: store page confirms an IMU; identical depth engine, range and dimensions to the D435i; RGB is a 1 MP **global-shutter** sensor with the same 87°×58° FOV as depth. Chosen because the core measurement (AprilTag pose from RGB on a moving, rotating robot) is where rolling shutter hurts; the IR-pass filter only helps the depth stream. Costs: 1 MP RGB (use 20–25 cm tags for 3 m range), a 2026 product with few community reports, and not yet on NVIDIA's Isaac ROS tested list (D435i/D455 are). SDK support since 2.57.7 (we run 2.58.4). Store returns are for **unopened** items only.
  - **JetPack 6 IMU caveat (all IMU models)**: the JP6 kernel lacks HID sensor support (`CONFIG_HID_SENSOR_HUB` unset), so the pip `pyrealsense2` wheel (kernel path) cannot deliver IMU data. Two routes exist, both the same for D435i/D436/D455:
    - **Route A (installed 2026-09-24)**: librealsense built from source with `FORCE_RSUSB_BACKEND=ON` — talks to the camera over libusb, no kernel changes. Caveat: a JP6.0 / SDK 2.55.1 report (librealsense issue #13020, Orin NX, D455) had 80% RGB frame drops and crashes with the IMU enabled under RSUSB, unresolved; we run JP6.2.1 / SDK 2.58.4, which added JP6 fixes. Test first when the camera arrives.
    - **Route B (fallback, documented)**: add the missing HID sensor kernel modules (`hid-sensor-hub`, `hid-sensor-accel-3d`, `hid-sensor-gyro-3d`) and use the native kernel backend (pip wheel or Debian packages). JetsonHacks publishes prebuilt modules for JP6.2 / L4T 36.4.3 / kernel 5.15.148-tegra (our kernel string; ABI match with 36.4.7 unverified), or build them from source (~37 min; a May 2026 write-up on JP6.2.2 got a clean 200 Hz IMU this way with no frame drops).
    - Decision rule: camera arrives → test Route A (depth, RGB, IMU at 200 Hz, frame drops over 10 min). Any drops or IMU crash → switch to Route B.
  - **SDK 2.58.4 notes (2026-09-24, from the release highlights)**: adds zero-copy GPU frame access on Jetson for CUDA/TensorRT (needs a build with `BUILD_WITH_CUDA=ON`; ours is OFF for simplicity — rebuild later if YOLO latency matters) and improved timestamp/hardware-clock accuracy (helps the timestamped-logging foundation). The new Perception framework's on-camera object detection is largely D555 firmware, not D436.
  - Not suited: D405 (7–50 cm only), D455/D455f (0.6–6 m, blind under 60 cm), D456/D457/D555 (industrial, IP65, GMSL or PoE), D585 Pro (10 m+ flagship, not in the store), D421 (bare module).
  - Orbbec Gemini 335 is a different company's competitor (0.15 m minimum range, `pyorbbecsdk2` 2.1.2 has an aarch64 cp310 wheel). At official RealSense prices the saving is small, so the better-documented RealSense path wins.

## Move the OS to NVMe now: SD image copy + boot-config edit, microSD kept as fallback (2026-09-23)

Reverses the "stay on microSD" decision made earlier the same day (kept below for the record).

- The NVIDIA devkit guide (`reference/2026-09-23-nvidia-devkit-guide-review.md`) has no JetPack 6 + NVMe path without an Ubuntu host. The method used is a community one: write the same SD image to the NVMe, change `root=` in the SSD copy's `extlinux.conf`, set `TEGRA_BOOT_STORAGE` to match. "Undocumented" means higher risk to be managed, not a ban.
- Why it is acceptable — the L4T code shipped *in the image itself* handles NVMe root (all read on the device, see `preflight.md`):
  - The initrd `init` script has an explicit `root=/dev/nvme*` branch: loads the PCIe and `nvme` modules, waits up to 10 s for the device node, mounts it.
  - `nvresizefs.sh` (first-boot partition resize) explicitly accepts `/dev/nvme*` root devices.
  - `nv-l4t-bootloader-config.sh` (run at every boot and by the bootloader package upgrade) detects the boot device from UEFI `BootCurrent` and writes `TEGRA_BOOT_STORAGE nvme0n1` itself when booted from NVMe; its own comment says the key "is deprecated and it is not used in this script or any other script in L4T". Our edit matches what it would write.
  - The image is designed to be written to a device larger than itself (24 GB image → 64 GB SD worked, APP grew to 58 GB); the NVMe is just a larger device with a different name.
- Fallback: the microSD is never written. UEFI boot order is SD first, so reinserting the SD restores the current system. Never keep both inserted after the move (the copies share filesystem UUIDs).
- Remaining unknown: how the `nvidia-l4t-kernel` package upgrade locates the `A_kernel` partition on NVMe (binary updater). QSPI is already 36.4.7, so a failed bootloader stage would leave the firmware at the target version anyway.
- Official recovery if anything breaks later: Ubuntu 22.04 on the Windows PC → `l4t_initrd_flash.sh --external-device nvme0n1p1` (option B).

### Superseded: stay on microSD for now; NVMe via an official path later (2026-09-23, earlier)

- Reasoning at the time: no official method; interaction with bootloader upgrades unknown → not used. Superseded once the on-device L4T scripts were read (above).
- Still true: `apt upgrade` 36.4.4 → 36.4.7 is NVIDIA's documented point-release path; `nvpmodel` mode persists across reboots (NVIDIA docs); RealSense is not mentioned anywhere in NVIDIA's devkit guide — check Intel's docs.
- Options kept for later: B (Ubuntu 22.04 on the Windows PC → SDK Manager / initrd flash, keeps JetPack 6) or C (JetPack 7.2.1 USB installer from the Mac, re-check RealSense / Isaac ROS).

## Storage (2026-09-23)

- **NVMe as the OS disk**: robots lose power abruptly; microSD filesystems corrupt easily.
- **Gen4 SSD bought only for price**: the Jetson 2280 slot is PCIe Gen3 x4; the Gen4 drive was cheaper than the Gen3 option.
- **No A2 microSD premium**: A2 command queuing needs host support; community reports (not verified by us) show no difference vs. A1 on Raspberry Pi 4 and earlier. Jetson support unconfirmed, so we did not pay for it. Moot since the move to NVMe.
- Two M.2 Key M slots: 2280 (x4) and 2242 (x2). The SSD is in the 2280 slot. Avoid B+M-key drives (fewer lanes).
- NVMe is not detected at all with firmware < 36.0.

## Networking (2026-09-23)

- The dev kit ships with **no WiFi card and no antennas**.
- Chose Waveshare AC8265 (lists Orin Nano/NX, antennas included). Intel 8265NGW chip.
- In-store USB adapters were mostly Realtek, which often need an out-of-tree Linux driver build → avoided.
- Initial setup over wired Ethernet.

## Webcam (2026-09-23)

- Brio 100: fixed focus (good on a robot), registered in the Linux hardware DB as UVC device `046d:094c`.
- Manual exposure is documented only for BRIO 4K / MX Brio; unconfirmed for Brio 100 → check with `v4l2-ctl --list-ctrls` on arrival.
- If it fails, the design still holds: the main measurement is AprilTag (black and white, robust to lighting).
- Fallback order: fix the lighting → AprilTag only → switch to C922.

## Robot base: wheeled, built from parts — no Roomba (2026-09-24)

- Paul's call: a parts build with wheels. Reasons: a used Roomba or a stair-climbing consumer robot makes it hard to swap in the Jetson as the brain, and the point of the project is to own the sensor → filter → control chain.
- Consequence: the parts list needs a chassis, two motors with **quadrature encoders**, a motor driver, a microcontroller for the 50–100 Hz wheel loop, and a battery + DC-DC converter for the Jetson. Candidates in `reference/2026-09-22-parts-build-bom.md`; the choice is the next decision.
- **Candidate found 2026-09-24: Waveshare UGV Rover PT Jetson Orin AI Kit, "Acce" version (no Jetson), $339.99 at waveshare.com.** An integrated version of the same parts list, designed to carry the Orin Nano developer-kit board. Facts read from Waveshare's pages and from the open-source ESP32 firmware (`waveshareteam/ugv_base_ros`, GPL-3, Arduino, reflashable over USB):
  - 6 wheels, 4 driven, skid-steer; wheel diameter 80 mm; track width 0.172 m; **660 encoder pulses per wheel revolution** (≈0.38 mm per pulse); one encoder per side; ESP32 runs PID speed control (`PID_v2`, default kp 20 / ki 2000 / kd 0); max 1.3 m/s.
  - Jetson ↔ ESP32 over UART at 115200, JSON: `{"T":1,"L":0.5,"R":0.5}` sets left/right speed in m/s; continuous feedback `{"T":1001,"L","R","gx","gy","gz","ax","ay","az","mx","my","mz","odl","odr","v"}` = wheel speeds, 9-axis IMU (ICM-20948), **per-side odometry in metres**, battery voltage; `{"T":131,"cmd":0/1}` toggles the stream. Exactly the control input + base IMU the filter needs.
  - 2-DOF pan-tilt (ST3215 serial-bus servos, 30 kg·cm), 5 MP 160° USB camera (redundant with the D436), OLED, 3S 18650 UPS module (cells not included, ≥2200 mAh 4C recommended, charge while running), 2 mm aluminium body, 2.5 kg.
  - Open points before buying: the listing says "Orin Nano 4GB Kit" — the Super developer kit uses the same carrier board, so it should fit (INFERENCE; confirm with Waveshare or on arrival); how the driver board feeds the Jetson's DC jack (ROS2 wiki mentions a 12.6 V cable; the devkit accepts 9–20 V). Trade-off accepted knowingly: skid-steer slips in turns, so wheel odometry is worse than a two-wheel differential drive — the filter and per-surface noise learning are there for exactly that.
  - Course rules (Ed #50/#51/#52, read 2026-09-24): any platform is allowed, "premade kits, drones, and robots are allowed assuming you can directly access the sensors and actuators via your own custom code"; collaboration and code sharing are encouraged for the Hardware Challenges. A JSON-controlled ESP32 base with open firmware qualifies.

## Camera alternatives considered before the D436 pick (2026-09-24)

Criteria in order: depth accuracy at 0.3–3 m indoors; a global-shutter RGB image while the robot moves (AprilTag pose is the core measurement); IMU with synchronized timestamps; SDK, ROS 2 and community depth. "Newest" is not a criterion.

| Camera | Price seen | Why not |
|---|---|---|
| D435i | $334 | rolling-shutter RGB (most community precedent, Isaac ROS-listed — the safe alternative) |
| D436 | $354 | **picked**: same depth engine, global-shutter RGB matched to the depth FOV, IMU; risks = 1 MP RGB (use 20–25 cm tags), 2026 product with little precedent, not yet on the Isaac ROS list |
| D455 | ~$420 | 0.6 m minimum range — blind to near obstacles indoors |
| Stereolabs ZED 2i | $499 | computes depth on the Jetson GPU (competes with on-robot models), rolling shutter, proprietary SDK; ZED X is global shutter but needs a GMSL capture card |
| Orbbec Gemini 336 | ~$300 | IMU + IR-pass filter and cheaper, but a smaller ecosystem and no Isaac ROS listing |

Sources: store.realsenseai.com product pages, stereolabs.com, OpenELAB Orbbec-vs-RealSense comparisons, Isaac ROS forum threads (all read 2026-09-24).

## Voice input/output: far-field USB mic array, local STT/TTS (2026-09-24, planned)

- Hardware: **Seeed reSpeaker XVF3800 USB mic array** (4 mics, XMOS DSP: beamforming, noise suppression, acoustic echo cancellation, direction of arrival up to ~5 m, USB Audio Class = no driver) plus a small speaker. Chosen over conference speakerphones (Jabra Speak 510, Anker PowerConf S3) because of motor/fan noise next to the mic, 2–3 m talking distance, hearing while the robot speaks (AEC), and DoA so the robot can turn toward the speaker. Price to be checked at purchase.
- Software, all local on the Orin Nano Super (2026 write-ups exist for this exact board): whisper.cpp with CUDA or faster-whisper for speech-to-text (≈1–2 s for 20 s of audio), Piper for text-to-speech (sub-second), optionally a small local LLM through Ollama for command understanding.
- Order: after the camera and the base.

## On-robot LLM: size before novelty (2026-09-24, planned)

- The 8 GB is shared by CPU and GPU (5.4 GB free with the desktop up) and decode speed is bound by memory bandwidth (102 GB/s), so 2–4B-parameter models at 4-bit are the ceiling if YOLO and Whisper run alongside; 4B-class models fail under concurrent requests on this board; 7–9B models run alone only.
- Candidates as of 2026-09: **Qwen3.5-4B** (3.4 GB via Ollama, text + image input, tool calling, multilingual incl. Korean) first; Gemma 4 E2B (3.6 GB, 25.5 tok/s measured on the Orin Nano GPU) second; Nemotron 3 Nano 4B (NVIDIA, Jetson AI Lab-listed) third. GLM family models are server-class and do not fit. Re-research at install time; this changes monthly.
- Ollama on Jetson: a plain install has been reported to miss the GPU (JetPack 6 CUDA library path); use the Jetson AI Lab Ollama tutorial (container method). llama.cpp or MLC are faster when needed.
- Jev (TypeSafe AI, released 2026-09-15): a hosted "decision model" that returns calibrated probabilities/scores/choices, not text; very cheap but API-only, early access, one week old. Not for the on-robot loop; a possible candidate for Mac-side auto-labelling later. Watch only.
- Training and the LLM tuning loop stay on the Mac or cloud; the Jetson GPU is for real-time inference.
