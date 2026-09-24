# Parts List

Prices as of 2026-09-22/23. Reasons in [decisions.md](decisions.md).

## Micro Center (bought 2026-09-23)

| SKU | Item | Price |
|---|---|---|
| 812057 | NVIDIA Jetson Orin Nano Super Developer Kit (19 V adapter included) | $399.00 |
| 999276 | TeamGroup T-FORCE G50 512GB NVMe M.2 2280 | $99.99 |
| 053744 | SanDisk 64GB Ultra Plus microSDXC | $34.99 |
| 414169 | Inland DisplayPort (M) → HDMI (F) 4K adapter | $12.99 |
| 974170 | Verbatim 64GB ToughMAX USB flash drive | $8.99 |
| — | Ethernet cable | — |

## Amazon

| Item | Price | Status |
|---|---|---|
| Waveshare AC8265 WiFi module (lists Orin Nano/NX, antennas included) | $28.99 | Ordered |
| Logitech Brio 100 webcam | $35.99 | Ordered |
| ~~Intel RealSense D435i~~ | $409.99 used / $499–519 new on Amazon | Removed — the official store is cheaper |

## RealSense official store (store.realsenseai.com)

| Item | Price (new) | Status |
|---|---|---|
| **RealSense D435if** (IMU + IR-pass filter) | $354.00 | **Current pick** — pending the pip/import check on the Jetson |
| RealSense D435i (IMU) | $334.00 | Alternative if saving $20 |

## Not bought yet (after choosing the robot base)

Base options: [../research/roomba-route.md](../research/roomba-route.md), [../research/bom-diy.md](../research/bom-diy.md).

- Chassis, motors (**quadrature encoders required**), motor driver, battery
- Microcontroller (e.g. Arduino Nano Every) for encoder counting and wheel PID
- IMU (not needed if we buy the D435i)
- Battery + DC-DC converter for the Jetson (9–20 V input, separate from motor power)

## Do not buy

- 4K webcams: vision models downscale inputs to ~224–384 px
- D435**f**: no IMU
- Cheap car kits with single-channel "encoders": they cannot tell direction
- Roomba i/j/s series, Combo, Create 3: no serial Open Interface port
