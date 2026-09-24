# Setup and Progress Log

What was done and checked, by date. Reasons live in [decisions.md](decisions.md); parts in [build-spec.md](build-spec.md).

---

## 2026-09-23 (Tue) — Jetson first boot

### Checked

| Item | Value | Result |
|---|---|---|
| Jetson System firmware | **36.4.7** (gcid-42132012, built 2025-09-18) | ≥ 36.0 → pass |
| SSD detection | UEFI shell mapping shows `BLK0 ... NVMe` | pass |
| Display output | DisplayPort → HDMI adapter works | pass |

First boot tried HTTP/PXE network boot, failed, and dropped into the UEFI shell → expected with no OS installed. The network boot attempt also shows the Ethernet link is up.

### Board ports

No power button: the board powers on when DC is applied. To power off: shut down the OS first, then unplug. (With no OS installed, unplugging is safe. Never unplug during a firmware update.)

| Port | Role | Our plan |
|---|---|---|
| 19V DC jack | Power in | On the robot: battery → DC-DC converter → here (9–20 V) |
| DisplayPort | Only video output | Setup only; remote access afterwards |
| Ethernet | Gigabit wired | Initial setup |
| USB 3.2 Type-A × 4 | Peripherals | Webcam / D435i (USB 3 required) / motor controller or Roomba adapter / keyboard |
| USB Type-C (UFP) | Jetson acts as a **device** to a host computer | Re-flashing from a PC; not for peripherals |
| MIPI CSI × 2 (22-pin) | Ribbon-cable cameras | Unused for now; stereo possible |
| microSD | Storage | First boot |
| 40-pin header | GPIO / I2C / SPI / UART | **3.3 V logic. Never connect 5 V signals directly** → Roomba (5 V TTL) goes through a USB-serial adapter |

### Install method

- NVIDIA's quick start doc (`.../user-guide/latest/`) now targets **JetPack 7.2.1** (USB ISO installer; "SD card images no longer supported from 7.2"). We are installing JetPack 6, so we do not follow it.
- NVIDIA's firmware update page (`update_firmware.html`) is for boards with firmware < 36.0. Ours is 36.4.7, so it does not apply.
- With only a Mac, the supported way to install JetPack 6 is the **SD card image**. (SDK Manager needs an Ubuntu host.)
- The USB flash drive is not used on this path.

Image:
- File: `jetson-orin-nano-devkit-super-SD-image_JP6.2.1.zip`
- Source: `developer.download.nvidia.com/embedded/L4T/r36_Release_v4.4/`
- Linked from the JetPack SDK 6.2.2 page: "Use the SD card image of JetPack 6.2.1 / Jetson Linux 36.4.4 and APT upgrade to JetPack 6.2.2 / Jetson Linux 36.5."

### Install steps

1. [x] Download the SD card image — 11,725,610,175 bytes, matches the server's Content-Length. Contains one file, `sd-blob.img`, 24,086,839,296 bytes (dated 2025-06-18).
2. [x] Install Balena Etcher (`brew install --cask balenaetcher`, v2.1.7 arm64).
3. [ ] Write the image to microSD.
   - **Etcher 2.1.7 unusable**: `Error opening source ... (0 , h.requestMetadata) is not a function` for both the .zip and the extracted .img.
     - Known bug on Apple Silicon Macs (balena-io/etcher GitHub #4672, "Error Opening Source - Version 2.1.7 MacOS ARM").
     - Lesson: search a tool version's known issues before installing it.
     - Removed Etcher (`brew uninstall --cask balenaetcher`).
   - **Replacement: write with macOS `dd`** — `~/Downloads/flash-jetson-sd.sh` (kept in this repo as `scripts/flash-jetson-sd-mac.sh`).
     - Guards: SD protocol + removable + 60–70 GB + not the system disk + typed `yes`. Any mismatch aborts.
     - After writing, compares a SHA-256 of the source image with a SHA-256 of the same number of bytes read back from the card (the same job as Etcher's "Validating" step).
     - Dry run (answer `no`): identified disk4 as the 63,864,569,856-byte SD card and stopped before writing.
   - Write result: 24,086,839,296 bytes in 723.4 s (33.3 MB/s, steady). Partition table changed from FDisk to GUID.
   - Verification: **passed**. SHA-256 of source and card both `f9a4a32021cee3b45af5fc2015d044eb99dc2adbc0640bb46202dc8865e67894`. Card ejected by the script.
   - Script messages rewritten in English after the run (never edit a script while it is executing).
4. [x] After writing, macOS may show "The disk you inserted was not readable" → click **Ignore** or **Eject**. Never **Initialize**.
5. [x] Insert the microSD into the slot on the **underside of the Jetson module** (contacts facing up toward the module, no adapter), power on, press no key → booted from SD into Ubuntu first-boot setup.
6. [x] Super mode: `ssh -t paulcho@192.168.1.234 'sudo nvpmodel -m 2'` (ID 2 = MAXN_SUPER, read from `/etc/nvpmodel.conf`). Switched without a reboot; `nvpmodel -q` → MAXN_SUPER; GPU max frequency 1,020,000,000 Hz.
7. [ ] `sudo apt update && sudo apt full-upgrade` — deferred until after the NVMe move (faster, less SD wear).
8. [ ] Move the system to NVMe.
   - Research (2026-09-23): copying the running SD rootfs to NVMe on-device is unreliable (multiple partitions, security features; JetPack 6.2 "can't find PARTUUID" boot failures reported). The most reliable official route is SDK Manager, which needs an Ubuntu host.
   - Mac-only route documented by the community: write the **same JetPack SD card image** to the NVMe, then edit `/boot/extlinux/extlinux.conf` on NVMe partition 1, changing `root=/dev/mmcblk0p1` to `root=/dev/nvme0n1p1`, remove the SD card, and boot.
   - Plan: do this from the Jetson itself while it runs from SD (NVMe is a separate disk, so writing it is safe): download the image on the Jetson, write it to `/dev/nvme0n1`, verify with SHA-256, edit extlinux.conf, power off, remove SD, boot.
   - Consequence: the NVMe is a **fresh install** → redo first-boot setup, `ssh-copy-id` (host key changes → Mac warning), and `nvpmodel -m 2`. Install pip only after the move.
   - Safety: the SD card stays untouched and remains a known-good fallback.
   - Sources: Cyberwave docs (Prepare your Jetson Orin Nano), NVIDIA forum threads on JetPack 6.2 NVMe boot.
   - Correction: the image does not need to be downloaded again — the Mac already has it (`~/Downloads/jetson-orin-nano-devkit-super-SD-image_JP6.2.1.zip`, `sd-blob.img`). Copy it over the LAN instead.
   - **Pre-flight inspection over SSH (read-only, 2026-09-23):**

     | Check | Finding | Action |
     |---|---|---|
     | NVMe | `nvme0n1`, 476.9 GB, no partitions | Safe to write while running from SD |
     | SD layout | 15 partitions incl. `APP` (root, ext4), A/B kernel+dtb, recovery, `esp` (vfat, `/boot/efi`), `esp_alt`, `UDA` | Same image on NVMe gives it its own ESP → can boot on its own |
     | UEFI BootOrder | `0001` UEFI SD Device, then `0008` UEFI T-FORCE (the NVMe) | SD removed → boots NVMe. SD inserted → SD wins (fallback) |
     | `/boot/extlinux/extlinux.conf` | `root=/dev/mmcblk0p1` | Edit on NVMe copy → `root=/dev/nvme0n1p1` |
     | `/etc/nv_boot_control.conf` | `TEGRA_BOOT_STORAGE mmcblk0`; OTA boot device `/dev/mtdblock0` (QSPI) | Edit on NVMe copy → `nvme0n1` (inference: an official NVMe install would say nvme0n1). Verify after first NVMe boot, **before** the 517-package upgrade (it includes kernel + bootloader packages) |
     | `/etc/systemd/nv.sh` | Only sets mmcblk0 read-ahead, guarded by an existence check | No change |
     | `/etc/fstab` | `/dev/root /`, and `/boot/efi` by `UUID=4EA2-9257` | Same image → SD and NVMe share partition UUIDs. After the move, **do not keep the SD inserted** |
     | `/dev/nvme0n1` perms | `root:disk 660`; user not in `disk` | Writing needs sudo |
     | SD free space | 34 GB | Enough to stage the 11.7 GB zip |

   - Open questions (only answerable by doing it): does first-boot resize grow the APP partition correctly on a 512 GB disk (GPT backup header sits at the image end, not the disk end; `sgdisk -e` fixes it if not)? Is the `nv_boot_control.conf` edit correct?

### First-boot setup choices (oem-config)

| Screen | Choice | Reason |
|---|---|---|
| NVIDIA EULA | Accepted | Required to use JetPack |
| Language / keyboard | English / English (US) | Error messages searchable in English |
| Time zone | New York | |
| User | name `Paul`, hostname `paul-cho-jetson`, username `paulcho` | Same username as the Mac → shorter SSH |
| Login | Require password (no auto-login) | Robot programs will start as system services, not via desktop login |
| APP partition | 59412 MB (maximum) | Use the whole card |
| Power mode | Not offered by the wizard | Set later with `nvpmodel` |
| Chromium | Not installed | Needs a download; uses RAM; work is done remotely from the Mac |
| Ubuntu "send system info" / location services | Off | No benefit; privacy |
| Ubuntu software updater popup | Remind me later | Upgrade from the terminal after the NVMe move |

First login: the mouse froze on the login screen while the keyboard still worked; it recovered on its own. Cause: first-boot background jobs saturating the microSD. Not a hardware fault.

### Remote access (SSH)

- Jetson IP: **192.168.1.234** (DHCP; Mac is 192.168.1.235, router 192.168.1.1). Ping ~7 ms.
- `paul-cho-jetson.local` does **not** resolve from the Mac even though `avahi-daemon` is active on the Jetson → use the IP for now. Consider a DHCP reservation on the router so the IP never changes.
- SSH server is on by default (port 22 open).
- Key login: Mac's existing `~/.ssh/id_ed25519.pub` installed with `ssh-copy-id paulcho@192.168.1.234`. Jetson host key fingerprint: `SHA256:6D1M+9YAi+0stXwG/Ns1HBL68dAdSoGHpj5LjhKRa1s` (will change after a reflash — expect a "REMOTE HOST IDENTIFICATION HAS CHANGED" warning then).
- Passwordless login verified from Claude's Bash tool (`ssh -o BatchMode=yes`). Commands that need `sudo` must be run by the user in a terminal: `ssh -t paulcho@192.168.1.234 'sudo ...'`.

### System state after first boot (read over SSH)

| Item | Value |
|---|---|
| L4T | R36.4.4 (JetPack 6.2.1), GCID 41062509, built 2025-06-16 |
| Kernel | 5.15.148-tegra |
| CUDA | 12.6 at `/usr/local/cuda-12.6` |
| `nvidia-jetpack` meta-package | not installed |
| Root filesystem | `/dev/mmcblk0p1` 57G, 20G used, 35G free |
| Memory | 7.4 GiB total, 5.4 GiB available with the desktop running |
| Power mode | 25W (ID 1, the default). Modes: 0 = 15W, 1 = 25W, 2 = MAXN_SUPER, 3 = 7W |
| Pending upgrades | 517, including `nvidia-l4t-bootloader` 36.4.4 → 36.4.7 (matches the factory QSPI firmware 36.4.7). Expect a firmware-update screen on the next reboot after upgrading — do not unplug |

## 2026-09-23 (evening) — moved the system to the NVMe SSD

Preflight (`preflight.md`): the earlier "no official method → pause" decision was reversed after reading the L4T scripts inside the image on the device — the initrd, `nvresizefs.sh` and `nv-l4t-bootloader-config.sh` all handle an NVMe root explicitly, and the kernel/bootloader package updaters find partitions by label, not by device name.

### Steps and what actually happened

1. **Image to the Jetson**: `scp` of the 11.7 GB JetPack zip into the SD system's home. SHA-256 `3cfaa834…9916d` identical on the Mac and the Jetson.
2. **Write + verify + edit** with `scripts/jetson-nvme-install.sh` (guards, `yes` prompt, O_DIRECT read-back hash, config edits with `.orig` backups).
   - Run 1: `--check` passed; full run wrote 24,086,839,296 bytes at ~121 MB/s, then the script **died silently at the verify step**. Cause: `dd | head -c N | sha256sum` — `head` closes the pipe early, `dd` dies of SIGPIPE, and `set -eo pipefail` exits the script with no message (the SSH session then closes normally, which looked like a dropped connection). Reproduced on `/dev/zero`: exit 141. Fix: read exactly 22,971 MiB with `dd count=`, no `head`. The NVMe write counter (`/sys/block/nvme0n1/stat`) showed exactly the image size written, so the write itself was complete.
   - Run 2 (`--verify-only`, added so the 24 GB write is not repeated): read-back hash `f9a4a320…e67894` matched (184 MB/s); `extlinux.conf` edited to `root=/dev/nvme0n1p1`; then **refused** on `nv_boot_control.conf` because the fresh image has no `TEGRA_BOOT_STORAGE` line at all — the line seen on the SD had been added by NVIDIA's first-boot script. Checked with `debugfs` (read-only); no edit needed. Script updated to accept the missing line.
   - Also caught by `--check` before any write: the model guard compared against `TM8FFE512G`, sysfs reports `T-FORCE TM8FFE512G`.
3. **Swap**: `shutdown -h now`, power unplugged, microSD removed and stored, power on with the SD out.
   - Kernel and systemd came up from the NVMe (console log on screen), then the screen went black at `Starting End-user configuration after initial OEM installation (GUI)...`. `Ctrl+Alt+F3` showed `localhost login:`; the Jetson answered ping; sshd not yet up. After ~10 min: power cycle → the setup wizard appeared on the second boot.
   - Wizard answers as on the SD (Paul / paul-cho-jetson / paulcho). APP partition: current 21,468 MB, maximum **486,893 MB** (= 512 GB SSD minus the 14 other partitions) — kept the maximum.
4. **Verification over SSH** (after `ssh-copy-id`):

| Item | Value |
|---|---|
| Root filesystem | `/dev/nvme0n1p1` ext4, 467.8 GB total, 19.4 GB used, 429 GB free |
| UEFI | `BootCurrent 0008` = `UEFI T-FORCE TM8FFE512G`; `BootOrder 0008,0004,…` (SD entry absent while the card is out) |
| `/dev/mmcblk0` | not present (SD is out) |
| `extlinux.conf` | `root=/dev/nvme0n1p1` |
| `nv_boot_control.conf` | `TEGRA_BOOT_STORAGE nvme0n1`, `TNSPEC 3767-302-0005-J.1-1-0-…` — both written by NVIDIA's first-boot script |
| `/etc/fstab` | `/boot/efi` line (UUID 4EA2-9257) added by the same script; esp mounted |
| `nv-l4t-bootloader-config` | ran clean; deb 36.4.4 (2360324) vs QSPI 36.4.7 (2360327) as before |
| L4T / kernel / hostname | R36.4.4, 5.15.148-tegra, paul-cho-jetson |
| Power mode | MAXN_SUPER (ID 2) |
| Memory | 7.4 GiB total, 5.4 GiB available |
| SSH host key | `SHA256:cU543Q2JGcfmaqht73UDE96gXlPQq+oruRb1Z6FNi8A` (new system; old key removed from the Mac's known_hosts) |

Rules going forward: never insert the microSD while the SSD system is in use (identical UUIDs and partition labels). The SD stays as the fallback until the SSD system has survived the 517-package upgrade.

### Package upgrade 36.4.4 → 36.4.7 (2026-09-23 23:45–23:54)

- Preflight (`preflight.md`): read `nvidia-l4t-bootloader.postinst`, `nvidia-l4t-kernel.postinst` and `nv-update-extlinux` on the device — none of them reset `root=` in `extlinux.conf`.
- Run: `sudo apt update` (517 upgradable) then `apt-get -y upgrade` detached with `setsid nohup`, log in `~/apt-upgrade.log`, watched from the Mac. Install phase ~6 min. No errors; `dpkg --audit` clean. Left: `fwupd libaudit-common libaudit1 ubuntu-advantage-tools` (held back by plain `upgrade`, expected).
- Kernel partitions updated through `/dev/disk/by-partlabel/A_kernel` and `A_kernel-dtb` ("Write successfully"). UEFI capsule staged at `/boot/efi/EFI/UpdateCapsule/`.
- Reboot 23:51: firmware screen "36.4.7 update in progress" (QSPI write, a few minutes), automatic second reboot, SSH back 23:54. After: L4T R36.4.7, deb version = QSPI version (2360327), root `/dev/nvme0n1p1`, MAXN_SUPER kept, capsule consumed.
- Warning `W: Couldn't identify type of root file system for fsck hook` — from Ubuntu's `update-initramfs`; not the initrd the board boots. Ignore.
- Ubuntu's GUI "Software Updater" popup was declined in favour of the terminal run. Never accept a release upgrade (22.04 → 24.04) — JetPack 6 is tied to 22.04.

### Python tooling and RealSense library (2026-09-24 00:05–00:20)

- `sudo apt install -y python3-pip python3-venv` (user). pip 22.0.2, python3-venv 3.10.6.
- Venv on the Jetson: `~/venvs/robot` (system Python 3.10.12 — the version JetPack 6 libraries and ROS 2 Humble target; no pyenv/conda on the Jetson).
- `pip install pyrealsense2` → 2.58.4.10922 (aarch64 cp310 wheel, no source build). Import test: `import pyrealsense2 as rs; rs.context().query_devices()` → 0 devices (no camera yet). Pinned in `src/requirements.txt`.
- Display: after 5 min idle the DP→HDMI output blanked and did not come back; kernel logged `nvidia-modeset: Failed to setup Rgline active session for vrr` at the wake attempt. Remote `xset dpms force on` + the user re-logging in restored it. Fix applied: `gsettings set org.gnome.desktop.session idle-delay 0` (screen never blanks). Lock screen left enabled. The first-boot black wizard screen is probably the same VRR/adapter issue.
- Side note for the log reader: a `pgrep -c apt` probe matched the kernel threads `[capture]` — use `pgrep -x apt-get` / `ps` with full args instead.

**OS setup complete**: JetPack 6.2.1 / L4T 36.4.7 on the NVMe, SSH keys, MAXN_SUPER, pip/venv, pyrealsense2 importable.

### librealsense RSUSB build for the camera IMU (2026-09-24 00:30–00:42)

Why: NVIDIA forum threads report that RealSense IMU models (D435i/D455/D436) lose the IMU on JetPack 6 because the kernel is built without HID sensor support. Checked on our kernel: `CONFIG_HID_SENSOR_HUB is not set`. The pip wheel's debug log showed the kernel path in use (`backend-v4l2.cpp` line), so the IMU would not work through it. RealSense's own Jetson guide offers a source build with the RSUSB (libusb) backend that "bypasses kernel patching".

- Build tools (user, sudo): `git cmake build-essential libusb-1.0-0-dev libssl-dev pkg-config python3-dev`.
- Source: `~/src/librealsense`, tag `v2.58.4` (same version as the wheel). Configure: `-DFORCE_RSUSB_BACKEND=ON -DBUILD_PYTHON_BINDINGS=ON -DPYTHON_EXECUTABLE=~/venvs/robot/bin/python -DBUILD_EXAMPLES=OFF -DBUILD_GRAPHICAL_EXAMPLES=OFF -DBUILD_WITH_CUDA=OFF -DBUILD_UNIT_TESTS=OFF -DCHECK_FOR_UPDATES=OFF -DCMAKE_BUILD_TYPE=Release`; `make -j6` detached (`setsid nohup`, log `~/librealsense-build.log`). ~8 min compile + a few minutes of LTO link. No errors.
- Outputs in `build/Release`: `librealsense2.so.2.58.4`, `pyrealsense2.cpython-310-aarch64-linux-gnu.so`, `rs-enumerate-devices`, `rs-fw-update`.
- Venv wiring: `pip uninstall pyrealsense2`, then `site-packages/librealsense-rsusb-build.pth` pointing at `build/Release` (the module's RPATH already resolves `librealsense2.so.2.58` from there; `ldd` confirmed). `src/requirements.txt` documents this.
- Verified: `import pyrealsense2` → 2.58.4 from the build tree; debug log at context creation shows only `context-libusb.cpp` lines and **no `backend-v4l2` line** (the pip wheel printed one) → RSUSB backend in use; `rs-enumerate-devices` runs ("No device detected", no camera yet).
- Still needed: udev rule `config/99-realsense-libusb.rules` → `/etc/udev/rules.d/` (sudo) so a normal user can open the camera over USB. Real IMU stream test waits for the camera.
- Camera decision context (same night): D436 ($354) chosen over D435if — same depth engine and IMU, global-shutter RGB with FOV matched to depth (better for AprilTag measurements while moving), supported since SDK 2.57.7; not yet on the Isaac ROS tested list. Official-store returns are for unopened items only.

### Note added 2026-09-24 01:10 — second route for the IMU, and an RSUSB caveat

Further reading after the RSUSB build: (1) librealsense issue #13020 (June 2024, JP6.0, SDK 2.55.1, Orin NX + D455) reports 80% RGB frame drops and crashes when the IMU is enabled under the RSUSB backend, unresolved — older SDK/JetPack than ours, but it means Route A must be tested for frame drops, not assumed. (2) JetsonHacks `jetson-orin-librealsense` ships prebuilt kernel modules (UVC/HID patches, incl. HID sensor support) for JP6.2 / L4T 36.4.3 / kernel 5.15.148-tegra — our kernel version string, but built against 36.4.3, so loading on 36.4.7 is unverified. (3) A May 2026 write-up (JP6.2.2, D455) built `HID_SENSOR_HUB/ACCEL_3D/GYRO_3D` modules from source (~37 min), installed six `.ko` files, and got a clean 200 Hz IMU with the native backend. Recorded in `decisions.md` as Route B. Sources: https://github.com/realsenseai/librealsense/issues/13020 , https://github.com/jetsonhacks/jetson-orin-librealsense , https://danieljordanviraytech.substack.com/p/getting-the-realsense-d455-imu-working
