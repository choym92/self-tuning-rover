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

Consequence: no WiFi card purchase is needed; connecting is `nmcli device wifi connect <SSID>` (needs sudo) when the robot leaves the desk.
