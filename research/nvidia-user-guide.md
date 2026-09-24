# NVIDIA Jetson Orin Nano Developer Kit — Official Documentation Review

Research pass over NVIDIA's official Jetson Orin Nano Developer Kit User Guide ("latest" = JetPack 7.2.1) plus the JetPack 6.2.1 / L4T r36.4.4 Jetson Linux Developer Guide pages it links to. Goal: check the plan to move our JetPack 6.2.1 install from a 64GB microSD to a 512GB NVMe (T-FORCE G50, M.2 2280) **without an Ubuntu host**, by writing the same JetPack 6.2.1 SD card image to `/dev/nvme0n1`, hand-editing `extlinux.conf` and `nv_boot_control.conf`, then booting from NVMe and running `apt full-upgrade`.

All statements below are paraphrased in my own words. Quoted fragments are NVIDIA's exact wording (under 20 words) with the source URL. Anything not read directly and instead inferred is marked **[INFERENCE]**.

---

## 1. Page index

### The Orin Nano Developer Kit User Guide ("latest", written for JetPack 7.2.1 / L4T r39.2.1)

Base URL: `https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/`. All 12 table-of-contents pages were fetched successfully; none failed.

1. **index.html** — Landing/overview page. Introductory manual for the Orin Nano Super Developer Kit; frames the guide around vision transformers, LLMs, VLMs, robotics, and Vision AI. Links out to all 11 other pages below. Does not state a single target version for the whole guide (the version is stated per-page).
2. **quick_start.html** — Quick Start Guide. First-time setup flow using the **Jetson ISO** USB installer method (JetPack 7.2.1 / L4T r39.2.1 only). Written for JetPack 7.2.1.
3. **setup_bsp.html** — BSP Setup. Explains the three BSP install options (Jetson ISO, SDK Manager, flash script) and when to use each. Written for JetPack 7.2.1, but the SDK Manager and flash-script options are the same tooling used for JetPack 6.x.
4. **update_firmware.html** — "JetPack 6.x Update Path." The one page in this guide actually written for the JetPack 5.1.3→6.x firmware-bridge flow relevant to our device. Covers checking/updating QSPI firmware without an Ubuntu host.
5. **setup_docker.html** — Docker Setup. Docker + NVIDIA Container Toolkit install/config/test steps. Version-agnostic (JetPack 6.x or 7.x), no explicit version stated.
6. **setup_cuda.html** — CUDA Setup. Container-based vs. native `nvidia-jetpack` CUDA setup and a PyTorch verification snippet. Uses JetPack 6.x / CUDA 13.0.0 / Ubuntu 24.04 in its examples.
7. **setup_jetpack.html** — JetPack SDK Setup. Three install paths for JetPack components: pre-flashed SD image, `apt install nvidia-jetpack`, or SDK Manager from an Ubuntu host. Doesn't explicitly separate JetPack 6 vs 7 guidance.
8. **hardware_layout.html** — Physical layout: microSD slot, two M.2 Key-M slots (2280 PCIe3x4, 2230 PCIe3x2), M.2 Key-E Wi-Fi slot, USB-C (host/device/recovery, no video out), 4× USB-A, GbE, DisplayPort-only video out, 40-pin header, 2× MIPI-CSI. Version-agnostic hardware reference.
9. **supported_hardware.html** — Supported Hardware. Very thin page; points to the Jetson Download Center's "Supported Component List" rather than listing components itself.
10. **howto.html** — How-to Guides. Power on/off, Force Recovery Mode entry (3 methods), power-mode switching via `nvpmodel`, `tegrastats` monitoring, CSI camera bring-up, `apt` package updates, swapping the microSD base image, and using Orin NX modules on the same carrier board.
11. **interim_solutions.html** — Interim Solutions. A near-empty stub page; its only content is a pointer to `update_firmware.html` for JetPack 6.x firmware compatibility guidance. No hidden or additional content on this page (confirmed against raw HTML).
12. **troubleshoot.html** — Troubleshooting Guide. Five issue categories: Jetson ISO not booting, no display output, installer not detecting storage, "firmware update is needed," and Docker socket permission errors.
13. **additional_docs.html** — Additional Docs. Link list only: JetPack SDK page, Jetson Linux Developer Guide, SDK Manager docs, Jetson Download Center, Jetson AI Lab, NVIDIA Jetson Forums, Jetson Ecosystem.

**Version flag:** every page in this "latest" guide defaults to JetPack 7.2.1 / L4T r39.2.1 language and workflow (Jetson ISO installer, no SD card support) *except* `update_firmware.html`, which is explicitly the JetPack 6.x-era flow. Where the other pages give commands (`apt install nvidia-jetpack`, Docker setup, `nvpmodel`, Force Recovery pin-shorting), those commands are identical on JetPack 6.x — only the *installation/flashing* workflow differs by version.

### Related Jetson Linux Developer Guide pages (L4T r36.4.4, which is what JetPack 6.2.1 actually ships)

Fetched because the Orin Nano user guide's "BSP Setup" and "JetPack 6.x Update Path" pages point to the Jetson Linux Developer Guide for flashing/target-name details, and because `nv_boot_control.conf` / boot-storage internals aren't covered in the devkit guide at all.

14. **`.../archives/r36.4.4/DeveloperGuide/SD/FlashingSupport.html`** — General flashing-tools reference: `flash.sh` and `l4t_initrd_flash.sh` usage, required directory layout, and the requirement to connect the flashing host to the Jetson's recovery port over USB.
15. **`.../archives/r36.4.4/DeveloperGuide/IN/QuickStart.html`** — Jetson Linux (not devkit-guide) Quick Start: confirms Ubuntu 20.04/22.04 host requirement, gives `l4t_initrd_flash.sh --external-device nvme0n1p1` example for NVMe.
16. **`.../archives/r36.4.4/DeveloperGuide/SD/PlatformPowerAndPerformance/JetsonOrinNanoSeriesJetsonOrinNxSeriesAndJetsonAgxOrinSeries.html`** — Power-mode table (10W/7W_AI/7W_CPU for 4GB, 15W/7W for 8GB, MAXN_SUPER on Super configs) and `nvpmodel` usage.
17. **`.../archives/r36.4.4/DeveloperGuide/SD/SoftwarePackagesAndTheUpdateMechanism.html`** — `apt upgrade` vs `apt dist-upgrade` guidance, role of `nvidia-l4t-core` in blocking incompatible/partial upgrades.
18. **`.../archives/r36.4.4/DeveloperGuide/SD/RootFileSystem.html`** — Rootfs generation and A/B (`APP`/`APP_b`) redundancy partitions. No mention of `nv_boot_control.conf`, `TEGRA_BOOT_STORAGE`, `extlinux.conf`, or `root=`.
19. **`.../archives/r36.4.4/DeveloperGuide/SD/Bootloader/UpdateAndRedundancy.html`** — Bootloader A/B slot mechanism, `nvbootctrl` commands. No mention of `nv_boot_control.conf`; no instructions for manually moving the boot storage device from SD to NVMe.
20. **`.../archives/r36.4.4/DeveloperGuide/SD/Bootloader/UEFI.html`** — UEFI Boot Order behavior and the three *documented* ways to change default boot priority (none of them is "edit a runtime config file after imaging").

All of these are JetPack 6.2.1-generation docs (L4T r36.4.4), i.e. they match our actual installed release, not the "latest" 7.2.1 guide.

---

## 2. What NVIDIA officially says about installing to or booting from NVMe

| Method | JetPack versions | Host required | What it does with NVMe |
|---|---|---|---|
| **Jetson ISO USB installer** | JetPack 7.2 and later only | Windows, macOS, or Linux PC (only to burn the ISO to USB with Balena Etcher) — **no Ubuntu host needed** | Boots the Jetson itself from the USB stick and installs Jetson Linux directly onto whichever target storage (microSD *or* NVMe) you select at the install screen. `setup_bsp.html`: "USB installation media that installs Jetson Linux to microSD or NVMe SSD... Best for JetPack 7.2.1, for first-time setup without an Ubuntu host PC." Explicitly **not supported** on JetPack 6.x — this is a JetPack 7.2+-only path. |
| **NVIDIA SDK Manager** | JetPack 6.x and 7.x (all current releases) | Ubuntu 20.04 or 22.04 x86-64 PC, mandatory | GUI flashing tool. During the "Flash" step you explicitly pick "Select NVMe to flash Jetson Linux to a NVMe SSD, or select SD Card to flash to a microSD card" (`setup_bsp.html`). This is the officially recommended way to get JetPack 6.x onto NVMe directly. |
| **Flash script (`flash.sh`)** | Any L4T/JetPack release | Ubuntu x86-64 host, mandatory, connected via USB to the Jetson's recovery port | Command-line flashing; `<rootdev>` argument selects target (e.g. `mmcblk0p1`, or NVMe device names per the Jetson Linux Developer Guide's Flashing Support page). Requires the target device to be in Force Recovery Mode and physically tethered to the host. |
| **`l4t_initrd_flash.sh` (initrd flash)** | Any current L4T/JetPack release | Ubuntu 18.04+ host, mandatory | Described on the Jetson Linux Developer Guide's Flashing Support page as **"the official method of flashing Jetson Orin NX series and Jetson Orin Nano series with NVMe as the external storage device."** Uses `--external-device nvme0n1p1` and a matching flash config XML. NVIDIA additionally states production systems **must** use initrd flashing (vs. plain `flash.sh`) for reliable OTA updates on Orin Nano/NX. |
| **Swapping the microSD card itself** | Any | Another computer with an SD card reader — the Jetson does not do this to itself | `howto.html`: "To change the base image, power off the developer kit, remove the microSD card, write the new image from another computer, and reinsert it before powering on." This is about swapping *SD card* images, not migrating to NVMe. |

**On copying/dd'ing the SD-card image directly to an NVMe drive, or hand-editing `extlinux.conf` / `nv_boot_control.conf`: NVIDIA says nothing.** This is stated explicitly, not by omission-guessing:

- The Jetson Linux Developer Guide's Flashing Support page never mentions writing the SD-card `.img`/SD-card-image file to an NVMe block device; every NVMe path it documents goes through `flash.sh` or `l4t_initrd_flash.sh` from a tethered Ubuntu host in Force Recovery Mode.
- `RootFileSystem.html` and `UpdateAndRedundancy.html` (the two most likely places for boot-device internals) do not mention `nv_boot_control.conf` or `TEGRA_BOOT_STORAGE` at all — I checked both directly.
- `UEFI.html` documents exactly three supported ways to change boot device priority (interactive Boot Manager selection, editing/rebuilding `L4TConfiguration.dts`'s `DefaultBootPriority`, or the `ADDITIONAL_DTB_OVERLAY` flash-time flag) — "manually edit a runtime boot-control file after copying the OS image" is not one of them.
- `update_firmware.html`'s only NVMe sentence is a redirect: "To install Jetson Linux directly to a NVMe SSD, use the Jetson ISO or NVIDIA SDK Manager path described in BSP Setup" — i.e., NVIDIA's own guide for JetPack 6.x/NVMe points you back to SDK Manager (Ubuntu host) or Jetson ISO (JetPack 7.2+ only, not usable on our JetPack 6.2.1 install).

So: `nv_boot_control.conf` is a real file the system uses internally (it's what the QSPI-update service and `nvbootctrl` read to know which physical device holds which boot slot), but NVIDIA's own developer documentation does not walk through editing it by hand, and does not describe or endorse the dd-the-SD-image-to-NVMe approach anywhere in the pages that exist for this purpose (Flashing Support, BSP Setup, JetPack 6.x Update Path, Root File System, Update and Redundancy, UEFI). This is silence, not a soft caveat — every doc that talks about getting Jetson Linux onto NVMe routes through an actual flashing tool, not image duplication.

---

## 3. Checks against our plan

Plan step by step, against what the docs actually say:

**Step: "Write the same JetPack 6.2.1 SD card image to `/dev/nvme0n1` from the running SD system."**
- **Silent/contradicted.** No official page describes writing the SD-card image to an NVMe device. Every documented NVMe path (SDK Manager's NVMe flash target in `setup_bsp.html`; initrd flash's `--external-device nvme0n1p1` on the Jetson Linux Developer Guide's Flashing Support page) is a *flash*, not an image copy — it runs the Tegra flashing pipeline (bootloader, partition table matched to the actual target size, BCT, etc.) rather than duplicating a filesystem image sized/partitioned for a 64GB microSD onto a 512GB NVMe. Also, both officially documented flashing tools (`flash.sh`, `l4t_initrd_flash.sh`) explicitly require the target device to be in **Force Recovery Mode**, tethered by USB to a **separate Ubuntu host** (`https://docs.nvidia.com/jetson/archives/r36.4.4/DeveloperGuide/SD/FlashingSupport.html`: "you must connect your host computer to the Jetson device's recovery port with a USB cable"). Doing the copy from the *running* SD system onto its own internal NVMe slot is a fundamentally different mechanism than anything NVIDIA documents.

**Step: "On the NVMe copy, edit `/boot/extlinux/extlinux.conf` (`root=/dev/mmcblk0p1` → `root=/dev/nvme0n1p1`)."**
- **Silent.** `extlinux.conf`'s existence and format ("contains a section for each kernel selection... kernel boot command line") is documented in the Jetson Linux Developer Guide's Boot Architecture material, and NVIDIA confirms the `root=` kernel parameter's device string does need to match wherever the rootfs actually lives. But no official page walks through manually retargeting `root=` from `mmcblk0p1` to `nvme0n1p1` on a copied image as a supported migration step — the documented way to get a correct `extlinux.conf` for NVMe is to let `flash.sh`/`l4t_initrd_flash.sh` generate it for that target during a real flash.

**Step: "Edit `/etc/nv_boot_control.conf` (`TEGRA_BOOT_STORAGE` mmcblk0 → nvme0n1)."**
- **Completely silent — confirmed by direct search.** `nv_boot_control.conf` and `TEGRA_BOOT_STORAGE` do not appear anywhere in the Jetson Linux r36.4.4 Developer Guide pages most likely to cover it (Root File System, Update and Redundancy, Flashing Support, UEFI Adaptation), nor anywhere in the Orin Nano devkit user guide. This is an undocumented, unsupported edit as far as NVIDIA's own docs go — it may well be the correct file/key based on outside community knowledge, but there is no NVIDIA statement to check it against, positive or negative.

**Step: "Remove the SD, boot from NVMe."**
- **Partially supported by the UEFI docs, but not for this scenario.** `UEFI.html` confirms the default boot order rule — **"Removable devices (SD/USB) take precedence over non-removable (eMMC/NvME/UFS) devices in the default boot order"** — which is exactly why the devkit currently boots SD-first, NVMe-second, matching what was observed. Removing the SD card would let UEFI fall through to NVMe next in that order, which is consistent with documented boot-order behavior *in general*. But this presumes the NVMe already has a bootable, correctly configured system on it — which is precisely the unsupported part above.

**Step: "Redo oem-config, then `apt full-upgrade` (517 packages, including `nvidia-l4t-bootloader` 36.4.4→36.4.7 and kernel packages)."**
- **Supported in principle, with one important caveat.** `oem-config` is the documented first-boot flow (`quick_start.html` step 6, `setup_bsp.html` step 5: "Complete the initial software setup, also called oem-config"). For the upgrade itself, `SoftwarePackagesAndTheUpdateMechanism.html` explicitly covers point-release updates via `sudo apt update && sudo apt upgrade`, and states `nvidia-l4t-core` "prevents package installation on an incompatible Jetson platform" and "prevents a partial upgrade." **Going 36.4.4→36.4.7 is a point-release bump within the same major/minor L4T generation (36.x), which is the case NVIDIA's `apt upgrade` guidance is written for** — it is not the unsupported case they warn about ("Upgrading from release 35.x to release 36.x is not supported"). So the upgrade step is fine *if* the system it's being run on is actually a correctly-configured NVMe boot — which again depends on the two undocumented edits above having worked.

**Explicit warnings the plan would risk violating:**
- `update_firmware.html`: **"Do not remove power while a firmware update is in progress"** and a general warning against "repeatedly booting an incompatible JetPack image or leaving the device at a black screen for an extended time" — relevant if the hand-edited NVMe boot doesn't come up cleanly and gets power-cycled repeatedly while troubleshooting.
- The Flashing Support / initrd docs' Force-Recovery-Mode + tethered-host requirement is not a "warning" so much as a structural precondition the plan skips entirely — NVIDIA's documented flashing tools assume the target is being flashed *from outside* while inert in recovery mode, not edited *from within* while it's the running root filesystem.

---

## 4. Other things in the guide worth doing / knowing for this setup

- **Firmware update behavior (`update_firmware.html`):** Our kit is already past this — QSPI 36.4.7 is newer than the 36.0 threshold the update path checks for, so no QSPI/JetPack 5.1.3 bridge step is needed. Good to know if firmware ever needs re-checking: press **Esc** repeatedly right after the boot splash to reach the UEFI setup menu and read the firmware version line, or use a USB-to-TTL serial cable on the Button Header (RXD=pin 3, TXD=pin 4, GND=pin 7) for headless checks.
- **`apt` upgrade guidance for JetPack 6.x:** `sudo apt update && apt list --upgradable && sudo apt upgrade` is the documented point-release path; `nvidia-l4t-core` is the safety net against incompatible/partial upgrades. NVIDIA explicitly advises against mixing packages from different L4T releases.
- **Power modes / `nvpmodel`:** Default is 25W on JetPack 6.2+ devkit configs (per `setup_bsp.html`/`howto.html`); Orin Nano Super unlocks **MAXN SUPER** (only available "when flashing with the jetson-orin-nano-devkit-super configurations," per the Jetson Linux power/performance page). Switch via Ubuntu's top-bar Power Mode menu, or `sudo /usr/sbin/nvpmodel -q` to check and `sudo /usr/sbin/nvpmodel -m <mode_id>` to set; the mode persists across reboots. `tegrastats` (not `nvidia-smi`) is the monitoring tool.
- **CUDA and Docker setup:** Two paths for both — container-based (pull from NGC, e.g. `nvcr.io/nvidia/pytorch:25.08-py3` or `nvcr.io/nvidia/cuda:13.0.0-devel-ubuntu24.04`) or native (`sudo apt install nvidia-jetpack`). Docker needs the NVIDIA Container Toolkit set as the default runtime via `nvidia-ctk runtime configure --runtime=docker` and a `daemon.json` edit; add your user to the `docker` group to avoid `sudo` on every command.
- **Camera support:** Guide covers MIPI-CSI cameras via the two 22-pin/0.5mm-pitch connectors (CAM0: up to 2-lane; CAM1: 2-lane or 4-lane), with a worked example for the Raspberry Pi Camera Module v2 (15-pin-to-22-pin adapter cable, `v4l2-ctl --list-devices`, a `gst-launch-1.0`/`nvarguscamerasrc` capture command). USB cameras are only covered generically ("USB cameras and other USB peripherals supported by Ubuntu and Jetson Linux" — `supported_hardware.html`). **RealSense is never named anywhere in the guide** — support for it isn't confirmed or denied by NVIDIA's own docs; that would need checking against Intel's own RealSense-on-Jetson guidance separately.
- **Troubleshooting items relevant to us:** for "installer doesn't see storage," the guide's advice is purely physical — reseat the NVMe SSD in its carrier-board connector and confirm it's secured, then reboot into the installer (`troubleshoot.html`). This assumes the *Jetson ISO installer* context (JetPack 7.2+), which we're not using, but reseating advice is generically useful if NVMe ever isn't detected.
- **Force Recovery Mode entry (dev kit specific):** three ways — from a terminal already logged in (`sudo reboot --force forced-recovery`); powered off (short pins 9–10 of the Button Header, then apply power, then remove the jumper once the host detects the device); or already powered on (short pins 9–10, briefly short pins 7–8 to reset, then remove jumpers once detected). This matters if we ever need to fall back to SDK Manager/initrd flash properly (from a borrowed Ubuntu machine or a VM on the Windows PC) instead of the in-place edit approach.
- **Do-not-unplug warnings:** explicit for firmware/QSPI updates ("Do not remove power while a firmware update is in progress" and don't leave the device "at a black screen for an extended time" repeatedly rebooting an incompatible image). No equivalent explicit warning exists for the in-place SD→NVMe edit scenario simply because NVIDIA doesn't document that scenario at all — treat it as at least as risk-sensitive as a firmware update, if not more.
- **UEFI boot order mechanics:** default rule is removable media (SD/USB) before non-removable (eMMC/NVMe/UFS); this is a first-boot-after-flash default only — "if additional storage devices are added in subsequent boots, those storage devices will be appended to the top or the bottom boot order" (paraphrased from `UEFI.html`). Good to know if boot order behaves unexpectedly after removing the SD card.

---

## 5. Open questions the guide does not answer

1. **Does the JetPack 6.2.1 SD-card image even contain a valid, generic `nv_boot_control.conf` template that just needs its storage key changed, or does that file get generated/patched by the flashing tool at flash time in a way that a raw copy can't reproduce?** Not covered anywhere in the pages read.
2. **What is the correct, complete set of edits beyond `extlinux.conf` and `nv_boot_control.conf`** — e.g., does the ESP/UEFI partition, the `APP`/`APP_b` redundancy metadata, or partition UUIDs referenced by `RootFileSystem.html`'s "use partition UUID rather than device name" redundancy feature also need to be touched when the rootfs moves to a different physical device? The guide doesn't say what breaks or doesn't when only two files are edited.
3. **Will `apt full-upgrade`'s planned `nvidia-l4t-bootloader` 36.4.4→36.4.7 bump work correctly on a hand-edited NVMe boot**, given the bootloader package upgrade path assumes it's the one that manages the A/B slot / boot-control state that we've bypassed by hand-editing it? Not addressed.
4. **Is there an official, lighter-weight way to get JetPack 6.2.1 onto NVMe without an Ubuntu host** other than: (a) initrd flash / SDK Manager (needs Ubuntu), or (b) waiting for/upgrading to JetPack 7.2.1's Jetson ISO (needs abandoning JetPack 6.x, which we deliberately chose not to do)? The guide presents only those two paths and is silent on any third option — meaning our exact constraint (JetPack 6.x + NVMe + no Ubuntu host) has no first-party documented solution at all.
5. **Does the Windows PC option (dual-boot Ubuntu, WSL2, or a VM) actually satisfy the "Ubuntu 20.04/22.04 x86-64 host" requirement for SDK Manager or initrd flash**, particularly for USB passthrough to the Jetson's recovery port? Host-OS requirements are stated as bare "Ubuntu x86-64," with no discussion of virtualized/WSL2 setups, in any page read.
6. **Is RealSense camera support confirmed for the Orin Nano Super under JetPack 6.2.1** — not mentioned in `supported_hardware.html` or anywhere else in the devkit guide; would require checking Intel's documentation or the forums, which were out of scope for this pass.

---

*Sources: NVIDIA Jetson Orin Nano Developer Kit User Guide (docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/, all 12 TOC pages) and NVIDIA Jetson Linux Developer Guide r36.4.4 (docs.nvidia.com/jetson/archives/r36.4.4/DeveloperGuide/), read directly on 2026-09-23.*
