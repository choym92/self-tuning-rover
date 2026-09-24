# Preflight Checks

Every step that changes the device (flashing, partitioning, boot config, firmware, installing tools, upgrades) gets a preflight entry here **before** any command is run. Read-only checks and research do not need one.

## Checklist

1. **Official source** — the vendor doc for the exact version in use (NVIDIA Orin Nano user guide / JetPack docs for the installed JetPack, not only "latest"). Cite the page.
2. **Known issues** — search the tool + version for known bugs before using it.
3. **Device facts** — verify every assumption on the device, read-only. Record the command and output.
4. **Label claims** — VERIFIED (with evidence) or INFERENCE.
5. **Reversibility** — what happens if it fails, and the exact fallback.
6. **Adversarial review** — for hard-to-reverse steps, an independent reviewer tries to refute the plan against the official docs.
7. **Commands** — guarded scripts (refuse if the target is wrong) with built-in verification.

Why this exists: on 2026-09-23 three avoidable mistakes happened (Etcher's known Apple Silicon bug, misdiagnosing it as a zip problem, planning to re-download an image the Mac already had), and a required config edit (`nv_boot_control.conf`) was almost missed.

---

## Template

```
## <step name> (<date>)

Goal:
Official source(s):
Known-issues search:

| Assumption | Evidence (command → output, or doc URL) | VERIFIED / INFERENCE |
|---|---|---|

Reversibility / fallback:
Adversarial review result:
Commands (guarded):
Outcome:
```

---

## Move the OS from microSD to NVMe (2026-09-23)

Goal: boot JetPack 6.2.1 from the 512 GB NVMe instead of the microSD, without an Ubuntu host.

Official source(s): the NVIDIA devkit guide (`../research/nvidia-user-guide.md`) documents NVMe only via the JetPack 7.2+ ISO installer, SDK Manager (Ubuntu host) or `l4t_initrd_flash.sh` (Ubuntu host). The method below (write the SD image to NVMe, edit the SSD copy's boot config) is a **community method**. The evidence that it is sound comes from the L4T scripts shipped inside the image, read on the device (paths below).

Known-issues search: community reports of JetPack 6.2 NVMe boot failures with `root=PARTUUID=...` after initrd flash ("can't find PARTUUID"); our `extlinux.conf` uses a device path (`/dev/nvme0n1p1`), which the initrd handles by a separate branch (see table).

History: first marked PAUSED the same day ("no official method") — reversed after reading the on-device scripts. Lesson: "undocumented" means find the specific risk and a fallback, not stop.

| Assumption | Evidence (read on the Jetson over SSH, 2026-09-23) | Status |
|---|---|---|
| NVMe is `/dev/nvme0n1`, 476.9 GB, empty, model `T-FORCE TM8FFE512G` | `lsblk`; `/sys/class/block/nvme0n1/device/model` | VERIFIED |
| Running root is the SD (`/dev/mmcblk0p1`), so writing the NVMe is safe | `findmnt -no SOURCE /` | VERIFIED |
| The image is self-contained: 15 partitions incl. `esp` (UEFI loader) and `APP` | `lsblk` of the SD written from the same image | VERIFIED |
| UEFI already lists the NVMe as a boot entry after the SD | `efibootmgr`: BootOrder 0001 (SD), 0008 (`UEFI T-FORCE TM8FFE512G`) | VERIFIED (entry); actual boot untested |
| `root=/dev/nvme0n1p1` is handled by NVIDIA's own initrd | `/boot/initrd` → `init`: branch `rootdev == nvme*` loads `pcie-tegra194`, `phy-tegra194-p2u`, `nvme`, waits up to 10 s for the node, mounts it. Kernel: `CONFIG_BLK_DEV_NVME=m`, `nvme.ko` present in the initrd | VERIFIED |
| First boot grows `APP` to the full NVMe | `/usr/lib/nvidia/resizefs/nvresizefs.sh` line 91–92 accepts `/dev/nvme*` root; same code grew the SD's APP from 24 GB image to 58 GB | VERIFIED (code); NVMe run untested |
| `TEGRA_BOOT_STORAGE nvme0n1` is the right value | `/opt/nvidia/l4t-bootloader-config/nv-l4t-bootloader-config.sh` `find_and_save_active_boot_storage_node()`: sets `nvme0n1` when `BootCurrent` is the NVMe entry (matched by EUI `A8-43-97-00-20-10-77-32`, which equals `/sys/class/block/nvme0n1/eui`). Comment at line 730: "TEGRA_BOOT_STORAGE is deprecated and it is not used in this script or any other script in L4T." | VERIFIED |
| Nothing else in the image depends on the device name `mmcblk0` | `grep -rIl mmcblk0 /etc /boot /opt/nvidia /usr/lib/nvidia /var/lib/dpkg/info` → `extlinux.conf`, `nv_boot_control.conf`, `nv.sh` (read-ahead only, guarded by `if -e`), `nv-l4t-bootloader-config.sh` (the detector above) | VERIFIED |
| Package upgrades (kernel, bootloader) work on NVMe | `nvidia-l4t-kernel.postinst` → `/usr/sbin/nv_bootloader_payload_updater --part A_kernel`; the binary references `/dev/disk/by-partlabel/%s` (device-name independent) and reads only `TEGRA_CHIPID`, `TEGRA_OTA_BOOT_DEVICE`, `TEGRA_OTA_GPT_DEVICE` (`/dev/mtdblock0` = QSPI, same for SD and NVMe) from `nv_boot_control.conf` | VERIFIED (strings); upgrade untested |
| QSPI already at the upgrade target | service log: "System version(deb version): 2360324, BSP version(QSPI version): 2360327" = 36.4.4 vs 36.4.7 | VERIFIED |
| SD and NVMe copies share filesystem UUIDs → never keep both inserted | `/etc/fstab` mounts `/boot/efi` by `UUID=4EA2-9257`; `by-partlabel` lookups would also be ambiguous | VERIFIED (mechanism); consequence is INFERENCE |
| Source zip on the Jetson is intact | 11,725,610,175 bytes, SHA-256 `3cfaa834…9916d` identical on the Mac and on the Jetson | VERIFIED |
| Tools present: `unzip`, `dd`, `sha256sum`, `partprobe`, `sgdisk` | `command -v` | VERIFIED |

Reversibility / fallback: the SD card is never written. If the NVMe does not boot, reinsert the SD — BootOrder puts SD first. If the write is interrupted (e.g. SSH drops), the NVMe is partially written and the script is simply re-run. Official recovery path if the NVMe system breaks later: Ubuntu 22.04 on the Windows PC + `l4t_initrd_flash.sh --external-device nvme0n1p1`.

Adversarial review result: not run as a separate reviewer — the step is reversible (empty SSD, untouched SD). The `--check` mode caught one real bug in the script before any write: the model guard compared against `TM8FFE512G` while sysfs reports `T-FORCE TM8FFE512G`.

Commands (guarded): `scripts/jetson-nvme-install.sh`, copied to `~/jetson-nvme-install.sh` on the Jetson.
- Guards: device exists and is a disk; model = `T-FORCETM8FFE512G` (spaces removed); size 450–520 GB; running root is `/dev/mmcblk0p1`; nothing on the NVMe mounted; zip size and SHA-256 match; zip lists `sd-blob.img` at 24,086,839,296 bytes; user must type `yes`.
- Write: `unzip -p … | dd of=/dev/nvme0n1 bs=4M oflag=direct conv=fsync`; `partprobe`; expect 15 partitions with p1 = `APP`; refuse if anything got auto-mounted.
- Verify: SHA-256 of the first 24,086,839,296 bytes read back with `iflag=direct` (bypasses the cache) must equal `f9a4a320…e67894`; on mismatch nothing is edited.
- Edit (SSD copy only, originals kept as `.orig`): `extlinux.conf` `root=/dev/mmcblk0p1` → `/dev/nvme0n1p1`; `nv_boot_control.conf` `TEGRA_BOOT_STORAGE mmcblk0` → `nvme0n1`; each edit re-checked with `grep -c`.
- `--check` run 2026-09-23 22:5x: all guards passed, stopped before any write.

Outcome (2026-09-23 23:40): **booted from the NVMe.** `findmnt /` → `/dev/nvme0n1p1` (467.8 GB, 429 GB free); `BootCurrent 0008` (T-FORCE); `TEGRA_BOOT_STORAGE nvme0n1` and the `/boot/efi` fstab line were added by NVIDIA's first-boot script as predicted; `nv-l4t-bootloader-config` ran without errors; MAXN_SUPER active. Two script bugs were found on the way (SIGPIPE in the verify pipeline; wrong assumption that the fresh image contains a `TEGRA_BOOT_STORAGE` line) — details in `setup-log.md`. First NVMe boot stalled at the GUI wizard; a power cycle fixed it. `BootOrder` is now `0008,…` with the SD entry absent while the card is out — reinserting the SD re-adds it, position unverified, so keep the "never both" rule.

---

## `apt upgrade` 36.4.4 → 36.4.7 on the NVMe system (2026-09-23/24)

Goal: apply the 517 pending package updates, including `nvidia-l4t-bootloader`, `nvidia-l4t-kernel`, `nvidia-l4t-initrd` 36.4.4 → 36.4.7, on the system that now boots from the NVMe with a hand-edited `extlinux.conf`.
Exact versions: L4T R36.4.4 → R36.4.7 (kernel 5.15.148-tegra both), QSPI already 36.4.7.
Official source(s): NVIDIA Orin Nano user guide, How-to Guides → `apt` package updates; JetPack 6.x Update Path page (point release via `apt`).
Known-issues search: the community SD→NVMe method's open question was "what do the package scripts do to a hand-edited boot config" — answered below from the scripts on the device.

| Assumption | Evidence (read on the Jetson) | Status |
|---|---|---|
| The upgrade does not reset `root=` in `extlinux.conf` | `nvidia-l4t-bootloader.postinst` `check_and_update_APPEND()`: if an `APPEND … root=` line exists it prints "Root device is set in the extlinux.conf" and leaves it; only fills bootargs from `/proc/cmdline` when missing. `check_and_update_FDT()` acts only on an `FDT` line (none). `nvidia-l4t-kernel.postinst` calls `nv-update-extlinux generic -r net.ifnames=0` (Python): edits the existing entry's APPEND only by adding/removing the named params, or creates a new entry that inherits the default entry's APPEND — `root=` preserved either way. `extlinux.conf` is owned by no package and is not a conffile | VERIFIED |
| Kernel/bootloader partition updates find the NVMe partitions | `nv_bootloader_payload_updater` uses `/dev/disk/by-partlabel/%s`; QSPI via `/dev/mtdblock0` | VERIFIED (earlier entry) |
| No interactive prompts will stall a detached run | `needrestart` not installed; run with `DEBIAN_FRONTEND=noninteractive` and `--force-confold`; no locally modified conffiles | VERIFIED (needrestart absent); prompts INFERENCE |
| Enough disk | `df /` → 430 GB free | VERIFIED |
| Held back packages are harmless | `apt-get -s upgrade`: kept back `fwupd libaudit-common libaudit1 ubuntu-advantage-tools` (plain `upgrade` never removes/adds packages) | VERIFIED |
| The bootloader step happens at the next reboot as a UEFI capsule update with an on-screen progress bar, then the board reboots by itself | NVIDIA guide (`update_firmware.html`: do not remove power during a firmware update) | VERIFIED (doc); behaviour on this board untested |

Reversibility / fallback: the only irreversible window is the firmware write during the reboot — never cut power then. If the NVMe system fails to boot afterwards, the microSD (36.4.4, untouched) still boots. If dpkg is interrupted mid-run: `sudo dpkg --configure -a` then re-run.
Adversarial review result: not run separately; the specific risk (boot config overwrite) was checked directly in the package scripts.
Commands: `sudo apt update`, then detached so an SSH drop cannot interrupt dpkg: `sudo bash -c "DEBIAN_FRONTEND=noninteractive setsid nohup apt-get -y -o Dpkg::Options::=--force-confold upgrade > /home/paulcho/apt-upgrade.log 2>&1 < /dev/null &"`. Progress watched from the Mac by reading the log.
Outcome (2026-09-23 23:54): **done.** `apt-get upgrade` finished with no errors (`dpkg --audit` clean; 4 packages left = the normally held-back ones). L4T packages 36.4.7; `/etc/nv_tegra_release` R36.4.7; `root=/dev/nvme0n1p1` untouched (bootloader postinst printed nothing about root, kernel postinst used the existing entry); kernel partitions written via `/dev/disk/by-partlabel/A_kernel` ("Write successfully"); NVIDIA initrd regenerated with the NVMe branch intact. Reboot: down 23:51:38, firmware screen "36.4.7 update in progress", back 23:54:05. After reboot: `nv-l4t-bootloader-config` reports deb 2360327 = QSPI 2360327 (36.4.7 both), capsule consumed, root still NVMe, MAXN_SUPER persisted. Harmless warning seen: `W: Couldn't identify type of root file system for fsck hook` from Ubuntu's `update-initramfs` (fstab lists `/dev/root`); the board boots NVIDIA's `/boot/initrd`, not that file.
