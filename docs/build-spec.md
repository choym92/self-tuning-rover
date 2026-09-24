# Parts List

Prices as of 2026-09-22/24. Reasons in [decisions.md](decisions.md). Only the Micro Center section is actual purchases; everything else is a plan until this file says otherwise.

## Bought — Micro Center, 2026-09-23

| SKU | Item | Price |
|---|---|---|
| 812057 | NVIDIA Jetson Orin Nano Super Developer Kit (19 V adapter included) | $399.00 |
| 999276 | TeamGroup T-FORCE G50 512GB NVMe M.2 2280 | $99.99 |
| 053744 | SanDisk 64GB Ultra Plus microSDXC | $34.99 |
| 414169 | Inland DisplayPort (M) → HDMI (F) 4K adapter | $12.99 |
| 974170 | Verbatim 64GB ToughMAX USB flash drive | $8.99 |
| — | Ethernet cable | — |

## Ordered / planned

| Item | Where | Price seen | Status |
|---|---|---|---|
| **RealSense D436** (depth + IMU + global-shutter RGB) | store.realsenseai.com | $354.00 + 12% tariff surcharge $42.48 + FedEx 2 Day $25.30 = **$421.78** (no sales tax charged) | **Ordered 2026-09-24** (returns only if unopened) |
| RealSense D435if (IMU + IR-pass filter) | store.realsenseai.com | $354.00 | Alternative — was the pick before the D436 check |
| RealSense D435i (IMU) | store.realsenseai.com | $334.00 | Alternative — most community precedent, rolling-shutter RGB |
| ~~RealSense D435i on Amazon~~ | Amazon | $409.99 used / $499–519 new | Dropped — the official store is cheaper |
| **WiFi card: RTL8822CE M.2 Key E** (WiFi 5 + BT 5.0 — the chipset NVIDIA's own Orin Nano devkit shipped, driver `rtl8822ce` included in JetPack 6) | **Waveshare AW-CB375NF** on Amazon (B0C6Q9PJKT): the exact module NVIDIA fitted to its devkits; package = card + 2× IPEX-to-SMA cables + 2× antennas; listed for Orin Nano | $20.99 | **Planned — replaces the AC8265 pick (2026-09-24).** Plug-and-play on JP6 per vendor Q&A and reviews; a few forum reports of non-detection exist (fix: swap to `rtw88_8822ce`). Verify `modinfo rtl8822ce rtk_btusb` on our Jetson before ordering |
| ~~Waveshare AC8265 (Intel 8265)~~ | Amazon | $28.99 | Dropped 2026-09-24: JetPack 6 ships no `iwlwifi`; needs `backport-iwlwifi-dkms` and is slower/pricier than the 8822CE |
| USB-C data cable (Mac ↔ Jetson USB-C device-mode port) | any data-capable USB-C-to-C, e.g. a phone cable | $0–16 | Optional — not needed while Ethernet/WiFi work; only a fallback for SSH/serial console with no network or display (see setup-log, L4T-README). Decided 2026-09-24: don't buy; use a cable already at home if ever needed |
| Logitech Brio 100 webcam | Micro Center / Amazon | $35.99 | Optional — the D436's RGB stream covers it; only if a second, cheap camera is wanted |
| Seeed reSpeaker XVF3800 USB mic array (+ small speaker) | Seeed / Amazon | to be checked | Later — voice step; chosen over conference speakerphones for beamforming, AEC and direction-of-arrival |

## Planned — after choosing the robot base (wheeled, built from parts)

Base research: [reference/2026-09-22-parts-build-bom.md](reference/2026-09-22-parts-build-bom.md). The Roomba route was researched and rejected; those notes live in git history (commit 7cb3348, research/roomba-route.md).

- Chassis, two motors with **quadrature encoders**, motor driver, battery
- Microcontroller (e.g. Arduino Nano Every) for encoder counting and wheel PID at 50–100 Hz
- Base IMU: optional — the D436 has one; a base-mounted IMU is easier to sync with the encoders
- DC-DC converter for the Jetson (9–20 V input, separate from motor power)

## Do not buy

- 4K webcams: vision models downscale inputs to ~224–384 px
- D435**f**: no IMU
- Cheap car kits with single-channel "encoders": they cannot tell direction
- Any Roomba (i/j/s series, Combo, Create 3 have no serial port; the 600-series route was rejected in favour of a parts build)
- Stereolabs ZED for this board: computes depth on the Jetson GPU, which the on-robot models need
