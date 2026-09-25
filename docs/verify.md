# Verification Procedures

Check each layer separately, cheaply, against a reference. "The robot doesn't move" is an end-to-end symptom and does not point to a cause.
Record measured values here with dates.

## Per-layer checks

| What | How | Compare against | Measured |
|---|---|---|---|
| Motor | Drive one wheel at a fixed output | Spin direction matches the command | |
| Encoder scale | Turn a wheel by hand exactly 10 revolutions | Is counts ÷ 10 consistent? | |
| Distance | Push the robot exactly 1 m on the floor | Tape measure | |
| IMU | Rotate 90° in place | Tape marks on the floor | |
| Camera range | Tag at 1 m / 2 m / 3 m, 100 detections each | Tape measure (also yields R) | |
| Kalman filter | Replay recorded logs offline | Taped ground-truth path | |

## Initial hardware checks

| Item | Command / method | Pass criterion | Result |
|---|---|---|---|
| Firmware | Press Esc during boot | ≥ 36.0 | **36.4.7 pass** (2026-09-23) |
| SSD detection | UEFI shell mapping table | NVMe listed | **pass** (2026-09-23) |
| SD card write | `scripts/flash-jetson-sd-mac.sh` | SHA-256 of image == SHA-256 read back from card | **pass** `f9a4a320…e67894` (2026-09-23) |
| Boot from SD | Power on with the card inserted | Ubuntu first-boot setup appears | **pass** (2026-09-23) |
| SSH key login | `ssh -o BatchMode=yes paulcho@192.168.1.234` | Logs in without a password | **pass** (2026-09-23) |
| Super mode | `nvpmodel -q` | `MAXN_SUPER` (ID 2) | **pass** — MAXN_SUPER, no reboot needed; 6 CPU cores online; GPU max 1,020 MHz (= NVIDIA's Super spec) (2026-09-23). Persistence across reboot: check after next reboot |
| Available memory | `free -h` | — | 5.4 GiB of 7.4 GiB with desktop (2026-09-23) |
| OpenCV + AprilTag | `python3 -c "import cv2; print(cv2.__version__, hasattr(cv2,'aruco'))"` | aruco present | **pass** — OpenCV 4.8.0, aruco available (2026-09-23) |
| RealSense Python wheel for this board | PyPI JSON for `pyrealsense2` | aarch64 + cp310 wheel exists | **pass** — 2.58.4.10922 manylinux2014_aarch64 cp310 (2026-09-23) |
| pip on the Jetson | `python3 -m pip --version` | installed | **missing** — needs `sudo apt install python3-pip python3-venv` |
| Webcam exposure control | `v4l2-ctl --list-ctrls -d /dev/video0` | `exposure_absolute` or `exposure_time_absolute` present | |
| LLM speed | Run a small model | Llama 3.2 3B: 43.1 tok/s in Super mode, MLC INT4 (NVIDIA JetPack 6.2 blog, 2025-01-16); ~30 tok/s for 3B models via ollama Q4 (community, 2026) | |

## The most important habit

Log sensor values **to CSV with timestamps**, so filter tuning can be repeated on a laptop without the robot.

## Checks after the NVMe move and the 36.4.7 upgrade (2026-09-24) — all pass

| Check | Command (on the Jetson) | Result |
|---|---|---|
| Root on the SSD | `findmnt -no SOURCE /` | `/dev/nvme0n1p1`, 467.8 GB, 428 GB free |
| Booted via the SSD UEFI entry | `efibootmgr` → `BootCurrent` | `0008` = UEFI T-FORCE TM8FFE512G |
| SSD image integrity before boot | SHA-256 of the first 24,086,839,296 bytes, O_DIRECT read | `f9a4a320…e67894` = image hash |
| Software = firmware version | `journalctl -b -u nv-l4t-bootloader-config` | deb 2360327 = QSPI 2360327 (36.4.7) |
| L4T release | `head -1 /etc/nv_tegra_release` | R36.4.7, GCID 42132812 |
| Boot config survived the upgrade | `grep root= /boot/extlinux/extlinux.conf` | `root=/dev/nvme0n1p1` |
| Kernel partitions updated | `/opt/ota_package/A_kernel.log` | "Write successfully to individual partition A_kernel" via `by-partlabel` |
| Power mode persists across reboot | `nvpmodel -q` | MAXN_SUPER |
| Package state | `dpkg --audit`; `apt list --upgradable` | clean; 4 held back (fwupd, libaudit*, ubuntu-advantage-tools) |
| Python | `python3 --version`; `python3 -m pip --version` | 3.10.12; pip 22.0.2 |
| pyrealsense2 import | `~/venvs/robot/bin/python -c "import pyrealsense2 as rs; print(rs.__version__)"` | 2.58.4; 0 devices (no camera yet) |
| Screen blanking | `gsettings get org.gnome.desktop.session idle-delay` | 0 (disabled; see setup-log for why) |

Pending checks: D436 detection + IMU streams on kernel 5.15.148-tegra (when the camera arrives; D436 replaced the D435if as the pick on 2026-09-24); WiFi — resolved 2026-09-25, see below (the kit already has a working card); SD reinsert behaviour of `BootOrder` (not tested — never insert both).

## RealSense software path without a camera (2026-09-24) — pass

| Check | Command (on the Jetson, venv `~/venvs/robot`) | Result |
|---|---|---|
| Kernel HID sensor support (why RSUSB is needed) | `zcat /proc/config.gz \| grep HID_SENSOR_HUB` | `# CONFIG_HID_SENSOR_HUB is not set` |
| Source build completed | `grep BUILD_OK ~/librealsense-build.log` | 1; no `make: ***` / `CMake Error` lines |
| Module import | `python -c "import pyrealsense2 as rs; print(rs.__version__, rs.__file__)"` | `2.58.4`, from `~/src/librealsense/build/Release/` |
| Backend is RSUSB | `rs.log_to_console(rs.log_severity.debug); rs.context()` | only `context-libusb.cpp` lines; no `backend-v4l2.cpp` line |
| Shared library resolution | `ldd pyrealsense2.cpython-310-aarch64-linux-gnu.so` | `librealsense2.so.2.58` → build tree; `libusb-1.0.so.0` → system |
| Tools run | `rs-enumerate-devices` | "No device detected. Is it plugged in?" |

Pending (needs the camera): USB enumeration, depth/RGB streams, **IMU streams**, Depth Quality Tool RMS. Pending (needs sudo): udev rule install.

## Checks with the Jetson on again (2026-09-25) — read-only

| Check | Command (on the Jetson) | Result |
|---|---|---|
| WiFi driver modules in this kernel | `modinfo -n rtl8822ce`; `modinfo -n rtk_btusb`; `modinfo -n iwlwifi` | `rtl8822ce.ko` and `rtk_btusb.ko` present under `/lib/modules/5.15.148-tegra/updates/`; `iwlwifi` **not found** (confirms: Intel cards would need the backport) |
| WiFi card physically present | `lspci -nn` | `0001:01:00.0 Network controller: Realtek RTL8822CE 802.11ac PCIe Wireless Network Adapter [10ec:c822]` — **the dev kit already has the card**; the 2026-09-23 note "no WiFi card" was wrong |
| Driver loaded, interface up | `lsmod`; `ip -br link`; `rfkill list` | `rtl8822ce` loaded; `wlP1p1s0` UP/NO-CARRIER (not connected); not blocked |
| Antennas work | `nmcli device wifi list --rescan yes` | 32 networks seen; home 2.4 GHz AP signal 100, several 5 GHz APs at 70 |
| Bluetooth | `hciconfig -a`; `lsusb` | `hci0` UP RUNNING (USB `13d3:3549` IMC Networks, the card's BT half) |
| Docker | `docker --version`; `dpkg -l docker-ce` | 29.8.1 (`docker-ce 5:29.8.1-1~ubuntu.22.04~jammy`) — newer than the 28.2.2 noted before the apt upgrade; `nvidia-container-toolkit` 1.16.2; daemon active; `paulcho` **not** in the `docker` group |
| Memory / swap baseline (desktop on, nothing else) | `free -h`; `swapon --show` | 1.5 GiB used, 5.7 GiB available of 7.4 GiB; swap = 6 × 635 MB zram (3.7 GiB), 0 used |
| Node.js / Ollama | `node --version`; `which ollama` | neither installed |
| CUDA allocation limit (R36.4.7 regression) | Python + `ctypes` on `/usr/local/cuda/lib64/libcudart.so.12`: `cudaMalloc` 1…6 GiB, free after each | 1, 2, 3 GiB ok; **4 GiB fails** (rc 2 out of memory, `NvMapMemAllocInternalTagged … error 12`) with 5.36 GiB reported free → the bug is present here; re-run after the 36.5.2 upgrade (preflight.md) |

Consequence: no WiFi card purchase is needed; connecting is `nmcli device wifi connect <SSID>` (needs sudo) when the robot leaves the desk.

## Checks after the R36.4.7 → R36.5.2 upgrade (2026-09-25) — all pass

| Check | Command (on the Jetson) | Result |
|---|---|---|
| Kernel / release | `uname -r`; `head -1 /etc/nv_tegra_release` | `5.15.199-tegra`; R36.5.2 (GCID 46426093, 2026-07-16) |
| Firmware = packages | `journalctl -b -u nv-l4t-bootloader-config` | deb 2360578 = QSPI 2360578 |
| Boot config survived | `grep root= /boot/extlinux/extlinux.conf`; `diff` against `~/backup-36.4.7/extlinux.conf` | `root=/dev/nvme0n1p1`; identical |
| Power mode / GPU clock | `nvpmodel -q`; `cat /sys/class/devfreq/17000000.gpu/max_freq` | MAXN_SUPER; 1,020,000,000 Hz (no 624 MHz cap) |
| WiFi / Bluetooth drivers | `lsmod`; `nmcli device wifi list --rescan yes` | `rtl8822ce`, `rtk_btusb` loaded; 47 networks |
| Docker | `docker --version`; `systemctl is-active docker` | 29.8.1; active |
| RealSense library | venv `import pyrealsense2`; `rs-enumerate-devices` | 2.58.4; "No device detected" (camera not here yet) |
| **CUDA allocation** | same `ctypes` `cudaMalloc` test as before | **1–4 GiB succeed** (4 GiB failed on 36.4.7). After `drop_caches` (Paul, by hand): 5 GiB ok, 6 GiB fails. Later with 2.4 GB in use: 4 GiB ok, 5 GiB fails. Rule of thumb: one GPU allocation must fit in the RAM `free` shows at that moment; the GPU cannot use swap or wait for cache reclaim. With the desktop on that is about 4–5 GiB; a 6 GiB block never fits on this 8 GB board (7.43 GiB usable minus the OS) |
| Memory baseline | `free -m` | 1,605 MB used, 5,759 MB available |

## LLM on the Jetson, llama.cpp v0.5.0 built in a container (2026-09-25)

Setup: image `rover/llama_cpp:v0.5.0` (built from `jetson/llm/Dockerfile` on the NVIDIA `l4t-jetpack:r36.4.0` base, CUDA 12.6, `GGML_CUDA_NO_VMM=ON`), run with `--runtime nvidia`, model files in `~/models`, caches dropped before each run, desktop running. Host untouched.

| Model (file) | Size | pp512 tok/s | tg128 tok/s | Reference | Note |
|---|---|---|---|---|---|
| Nemotron 3 Nano 4B Q4_K_M (`NVIDIA-Nemotron3-Nano-4B-Q4_K_M.gguf`, 3.97 B params) | 2.63 GiB | 581.6 ± 10.0 | **19.63 ± 0.04** | NVIDIA: 18 tok/s with llama.cpp on this board | GPU confirmed: `ggml_cuda_init: found 1 CUDA devices … Device 0: Orin, compute capability 8.7, VMM: no` |

`VMM: no` is the device's own answer: the Orin does not support CUDA virtual memory management, so building with `GGML_CUDA_NO_VMM=ON` changes nothing at run time (this was an inference in the preflight; now measured).

Pending for each model: RAM at 4k / 16k context (`tegrastats`), max temperature, and the chat + tool-call harness (see preflight, step 9).
