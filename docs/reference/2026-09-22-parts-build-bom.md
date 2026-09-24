> Research snapshot written 2026-09-22. Not maintained; current decisions are in [../decisions.md](../decisions.md) and current parts in [../build-spec.md](../build-spec.md).

# Differential-Drive Robot BOM — GT OMSCS CS7638 Hardware Challenge

**Date written (price-check date): 2026-09-22** — Prices can shift on a timescale of days to weeks, so re-open the links to confirm right before actually purchasing.

**Preconditions (context taken from the requirements)**
- The Jetson Orin Nano Super (8GB) dev kit + USB webcam are already planned purchases (need separate confirmation, see below)
- Development happens on a Mac (M5 Pro 64GB), with the Jetson as the separate robot brain
- Algorithm plan: PID on wheel speed + Kalman filter (wheel odometry + IMU fusion), with camera + AprilTag as a secondary measurement
- **HARD REQUIREMENT: wheel motors with a quadrature encoder are mandatory** — without an encoder there is no odometry measurement at all to feed into the Kalman filter
- Deadline: 2026-12-10 (about 11 weeks remaining)

---

## Summary (TL;DR)

| Configuration | Total (approx.) | Notes |
|---|---|---|
| **Minimum Viable configuration** | **approx. $410–450** | Includes Jetson ($249) + webcam (~$20), based on the DFRobot Baron-4WD ready-made chassis + motors |
| **Comfortable configuration** | **approx. $650–700** | Pololu component build + upgraded motor driver/MCU/IMU/camera |
| Robot parts alone, excluding Jetson/webcam (minimum) | approx. $160–200 | |
| Robot parts alone, excluding Jetson/webcam (comfortable) | approx. $400–450 | |

**The most important flag first:** the price the user had in mind — "the Jetson Orin Nano Super is ~$399 at Micro Center" — differs from today's search results. Both JetsonHacks (2024-12-17 article) and the Micro Center search snippet showed **$249** as the MSRP, and slickdeals also had a record of a **$219.99** promotion. The Micro Center product page (microcenter.com/product/691058) could not be opened directly due to bot blocking (403), so today's real-time price could not be finally confirmed — **please re-confirm directly in-store/on the site**. The $399 figure may have been the price of the older 8GB Developer Kit (before a discount), or it could be a different SKU/bundle.

---

## 1. Chassis + DC Gearmotor (Quadrature Encoder Mandatory)

Two paths are presented. If time is short (11 weeks) and there's no mechanical-assembly experience, **Path A (ready-made)** is the safe choice; if the report needs to state the exact encoder CPR spec, **Path B (Pololu components)** is better.

### Path A — Recommended (default): DFRobot Baron-4WD Mobile Robot Platform for Arduino with Encoder (SKU ROB0025)
- **Price**: $49.90 (DFRobot official store, confirmed 2026-09-22) — https://www.dfrobot.com/product-261.html
- **Why this one**: A 4WD platform with the chassis+motors+wheels already assembled. The product page explicitly states "comes with two sets of encoder ... closed-loop PID control." Almost no assembly required, making it the fastest path for a non-mechanical-engineer.
- **Specs**: Rated voltage 4.5–6V, wheel diameter 65mm (2.6in). **The encoder CPR (pulses/revolution) and gear ratio could not be confirmed in this session** — before purchasing, be sure to open the motor datasheet PDF link on the DFRobot Wiki (https://wiki.dfrobot.com/rob0112/) and re-confirm the CPR. The Kalman filter report needs to state the odometry resolution, so this cannot get started without that number.
- Even though it's 4WD, driving the left/right motors each in parallel lets it be treated as a typical differential-drive (2-DOF control) setup.
- **Cheaper alternative**: generic Amazon-type "TT motor 2WD/4WD smart car chassis kit" (VBOTCOR and similar, acrylic chassis + L298N + TT motors + generic wheels; the price of the assembled unit itself could not be found in the search, market price roughly estimated at $20–30, unverified). **Caution**: the "encoder" on these cheap kits is often just a **single-channel speed sensor (slotted disc)** rather than a true 2-channel quadrature encoder — if it can't read rotation direction, it can't be used as an odometry measurement for the Kalman filter. Before buying, be sure to check whether the listing explicitly states "quadrature," "2-phase," or "A/B channel."
- **Better alternative**: DFRobot HCR Mobile Robot Platform with Dual Encoder DC Motors — $530–643 (DFRobot, searched 2026-09-22). 10kg payload, aluminum 3-tier chassis, good Kinect/sensor expandability. Worth considering with a generous budget, but overkill for this assignment.

### Path B — More precise (specs are explicit, good for writing up in the report): Pololu 25D mm Metal Gearmotor with 48 CPR Encoder (component combination)
Buy the individual parts and assemble them yourself (an acrylic/aluminum chassis plate must be bought separately or made yourself — Pololu doesn't sell a ready-made chassis for the 25D size).

| Part | Price (confirmed 2026-09-22) | Source |
|---|---|---|
| Pololu 99:1 Metal Gearmotor 25Dx69L mm LP 12V w/ 48 CPR Encoder (×2) | $53.95/each → $107.90 | https://www.pololu.com/product/4887 |
| Pololu 25D mm Metal Gearmotor Bracket Pair | Price unconfirmed (not found in search, typically estimated around $5) | https://www.pololu.com/product/2676 |
| Pololu Wheel 70×8mm Pair | US site list price unconfirmed (UK Pi Hut converted price approx. £5.70 ≈ $7 estimated) | https://www.pololu.com/product/1425 |
| Pololu Ball Caster (3/8" metal) | Price unconfirmed (search failed, typically estimated at $4–6) | https://www.pololu.com/product/951 |
| Generic aluminum/acrylic chassis plate (drill your own holes to match the motor-bracket screw holes, or buy an assembly-type one) | roughly $12–20 estimated, unverified | — |

- **Specs (99:1 LP 12V version, confirmed from actual measurements)**: gear ratio 98.78:1, no-load speed 57 RPM @ 12V, stall current 0.9A (extrapolated), encoder 48 CPR (at the motor shaft) → **4741.44 CPR/revolution at the gearbox output shaft**. This figure is itself already a value computed in Pololu's official datasheet, so it can be cited directly in the report.
- If faster rotation is desired, there's also a 227:1 MP 12V version ($53.95, https://www.pololu.com/product/4869, no-load current 100mA, stall 1.8A extrapolated) — the higher the gear ratio, the more torque↑ and the less speed↓.
- **Why this one**: encoder CPR, gear ratio, and stall current are all precisely documented in Pololu's official spec sheet, which makes it easy to justify the Kalman filter's measurement-noise/odometry-precision calculations in the report. If the professor/TA asks "what's the basis for the encoder resolution," you can answer immediately.
- **Downside**: the chassis isn't ready-made, so it needs assembly/fastening yourself (drilling, or buying an assembly-type aluminum channel). Takes more time than Path A for a non-mechanical-engineer.
- **Cheaper alternative**: Path A's DFRobot Baron-4WD ($49.90, ready-made).
- **Better alternative**: the Pololu 25D **HP (High Power)** 12V version + a rugged Dagu Wild Thumper 6WD chassis (price roughly in the $130–200 range, list price not searched in this session) — worth considering if rough-terrain driving/torque margin is needed. Since it's 6WD it isn't pure 2-wheel differential-drive, but the same control model applies by driving the three left and three right motors in parallel.

---

## 2. Motor Driver

| Product | Price (date confirmed) | Continuous current | Evaluation |
|---|---|---|---|
| **TB6612FNG breakout (Adafruit #2448)** | **$6.95, in stock** (2026-09-22, https://www.adafruit.com/product/2448) | 1.2A/channel continuous, 3.2A/channel peak | **Recommended.** Being MOSFET-based, it has a much smaller voltage drop than the L298N and generates less heat. Fits the Pololu LP motor (stall 0.9A) with plenty of margin. The SparkFun version has been retired — buy the Adafruit version. |
| Cytron MD10C (single-channel, 13A) | Price check failed (Amazon page 403/content not shown, cytron.io also 403). Roughly estimated at $25–30 based on historical prices — **unverified, check directly on cytron.io before purchasing** | 13A continuous (5–30V) | One is needed per motor (2 motors = buy 2 units). If using a Pololu **MP/HP** high-power version (stall in the 1.8–5A range), this has much more margin and is safer than the TB6612FNG. |
| Cytron MDD10A (2-channel, 10A) | List price unconfirmed, EU retail price €22.50 (Botland, for reference) | 10A/channel | Can control 2 motors with a single board, so wiring is simpler. If planning to use HP motors, this is a safer choice than the TB6612FNG. |
| L298N module (generic) | Not verified, typical market price $3–6/unit (general knowledge, not searched today) | Rated at 2A/channel on paper, but actual use without a heatsink is recommended to stay around ~1A | **Not recommended/outdated.** Being a bipolar-transistor H-bridge, 1.4–2V per channel is simply lost as voltage drop, giving poor heat and efficiency. It works fine for a classroom demo, but isn't used much these days. |

**Conclusion**: With a Pololu LP motor (Path B, 99:1) or the DFRobot Baron's stock motor (4.5–6V, low current), the **TB6612FNG** is sufficient. If you pick a motor with a large stall current like the Pololu MP/HP, you need to step up to the **Cytron MDD10A/MD10C**.

---

## 3. Microcontroller (real-time encoder counting + PID loop)

| Board | Price (date confirmed) | Quadrature decoding | USB serial with the Jetson |
|---|---|---|---|
| **ESP32 DevKitC — Recommended** | No single confirmed price found in search (many Amazon clones, market price roughly estimated at $8–15, **price unverified**) | **Built-in hardware PCNT (Pulse Counter) unit** — quadrature decode mode is supported directly in hardware, so the CPU doesn't have to be tied up handling interrupts. Comfortably handles 4 encoder channels (2 motors × A/B) | Built-in USB-UART bridge (CP2102/CH340), recognized directly as `/dev/ttyUSB0`. Commonly in stock at Micro Center |
| RP2040 (Raspberry Pi Pico) — cheaper alternative | Not searched, typically $4–5 (general-knowledge level, unverified) | Quadrature decode can be implemented with a PIO (Programmable I/O) state machine (official examples exist) — flexible, but the firmware work takes a bit more effort than the ESP32 | Native USB device, easy to recognize |
| Teensy 4.0 — better alternative | Not searched, typically $23–28 (general-knowledge level, unverified) | Has multiple built-in FlexPWM/eFlexPWM hardware quadrature decoder channels, and at 600MHz has plenty of margin for the PID loop | Native USB, very easy. However, it's more expensive and usually not carried at Micro Center |
| **Arduino Nano Every** | **$12.90 (Arduino official US store, 2026-09-22)** — https://store-usa.arduino.cc/products/nano-every | No hardware quadrature decoder. Being ATmega4809-based, it has enough headroom for interrupt/pin-change (PCINT) handling, so software decoding is entirely feasible (low risk of missed counts unless rotation is very fast) | Has USB-C and standard serial, very easy. Being the Arduino brand, it has by far the most community material/course examples |

**Conclusion**: If time is short and stability is the top priority, go with the **ESP32 DevKitC** (hardware quadrature, purchasable at Micro Center, and cheap). If heavy reliance on class examples/community documentation matters more, the **Arduino Nano Every** ($12.90, confirmed price) is also fine to use — at this robot's speed range (assumption: wheels at a few hundred RPM or below), software interrupt decoding is sufficient.

---

## 4. IMU — BNO055 vs BNO085 vs ICM-20948

| Product | Price (date confirmed) | Output | Evaluation |
|---|---|---|---|
| Adafruit BNO055 (STEMMA QT, #4646) | **$29.95** (the original non-STEMMA #2472 is $34.95) (searched 2026-09-22) — https://www.adafruit.com/product/4646 | Comes with Bosch's own sensor-fusion firmware built in → it already **fuses absolute orientation/quaternion onboard** and outputs it over I2C. Raw accel/gyro/mag modes can also be selected | The easiest wiring/code (4-pin STEMMA QT connector). **However, if the assignment's core point is "fuse the IMU yourself with a Kalman filter,"** just using the BNO055's built-in fusion essentially hands you the answer already, which could be academically awkward — using ACCONLY/GYROONLY mode to pull only raw values is recommended |
| Adafruit BNO085 (STEMMA QT, #4754) | The search result only said "same price as the BNO080" — **the exact current price could not be directly confirmed in this session, roughly estimated at $29.95** — https://www.adafruit.com/product/4754 | Successor to the BNO055, SH-2 firmware fixes an SPI timeout bug, adds a low-latency rotation vector for AR/VR | Same pain points/advantages as the BNO055. If buying new, this is the more current choice |
| **SparkFun ICM-20948 (Qwiic) — Recommended** | **$21.95, in stock** (2026-09-22, https://www.sparkfun.com/sparkfun-9dof-imu-breakout-icm-20948-qwiic.html) | **Provides raw 9-DOF (accel+gyro+mag) only, with no onboard sensor fusion** (a DMP exists but doesn't need to be used) | The cheapest, and best fits the intent of the assignment — "write the Kalman filter yourself" — since you can feed the raw gyro angular rate directly into the KF's process/measurement model. Qwiic connector makes wiring easy too. **The least headache-inducing choice**, and the recommended one |

**I2C wiring**: all three products use STEMMA QT/Qwiic (JST-SH 4-pin), so they're plug-and-play. It's also possible to connect directly to the Jetson Orin Nano's 40-pin header (pins 3/5, SDA/SCL bus 1) and read via Python (smbus2), but the **recommended architecture is to wire the IMU to the MCU, and have the MCU bundle the encoder counts + raw IMU data together and send them to the Jetson over USB serial** — this makes the Jetson-side Kalman filter code much simpler, since it only needs to receive a single time-synchronized packet.

---

## 5. Power

**Core principle (per the user's own requirement): the motor power rail and the Jetson power rail must be strictly separate.** If the current spike from a motor stall puts noise on the Jetson's 5V/power rail, the board could reset or the SD card/filesystem could get corrupted — share only a common GND, and keep the power paths separate.

### Motor battery
- **3S LiPo (11.1V nominal, 12.6V full charge), 5200mAh, hard case** — voltage matches well with the Pololu 12V motors. Representative brands: Zeee, GOLDBAT, Power Hobby, HOOVO, etc. (multiple listings confirmed on Amazon in a 2026-09-22 search, but **individual prices didn't appear in the snippets and are unverified** — general market price estimated at $30–45).
- A separate balance charger (iMax B6-type clone) is also needed; if not already owned, typically estimated at $20–30 (unverified).
- A LiPo low-voltage alarm (buzzer) and a fireproof LiPo storage bag are recommended — roughly $5 each, estimated.
- **Cheaper alternative**: alkaline/NiMH AA battery holders (equivalent to 2S–4S). Heavy, and the poor discharge characteristics can make PID tuning messy, so not recommended.
- **Better alternative**: 2S LiPo + a separate 5V UBEC to cleanly supply just the logic voltage separately — one more wiring step, but more noise-resistant.

### Jetson battery + converter
- The Jetson Orin Nano dev kit's barrel-jack input spec is **DC 9–20V** (confirmed across multiple NVIDIA Developer Forum threads, searched 2026-09-22). The rated adapter is typically 19V/about 3A (about 57W).
- Rather than connecting the battery directly, you **must use a buck/boost converter to produce a stable voltage between 9–20V**. An NVIDIA forum case confirmed an example of using an XL4015 buck converter to step a 24V LiPo down to 19.1V.
- Specs to check when purchasing: adjustable output of 9–20V, **at least 3A continuous current (5A margin recommended accounting for peak load)**, and low output-voltage ripple (there are multiple forum reports that the Jetson is sensitive to voltage instability).
- The prices of specific products weren't searched in this session (skipped due to time budget) — it's recommended to search Amazon for "adjustable buck converter 5A 9-24V input" and look for products in the $15–25 range, prioritizing products with reviews specifically mentioning use with a Jetson.

### Connectors/fuses
- XT60 or XT30 connectors (battery↔power board): a small pack estimated at $5–8
- Inline fuse holder + blade fuse (to protect the motor rail, rated at roughly 1.5x the motor's stall current): estimated around $5
- Rocker switch (power on/off): estimated at $3–5
- **All 5 of the power items above went entirely without real-time price search in this session — re-confirmation on Amazon is needed before purchasing.**

---

## 6. Misc

| Item | Notes |
|---|---|
| Wheels | Included with Path A (Baron-4WD). For Path B (Pololu), buy the Wheel 70×8mm Pair separately (price unconfirmed, roughly estimated at $7) |
| Caster | Pololu Ball Caster (3/8" metal, #951) — price search failed, typically estimated at $4–6. The Baron-4WD is 4WD, so no caster is needed |
| Standoffs/screw set | roughly $6–10 estimated (unverified) |
| Jumper wires (M-M/M-F/F-F sets) | Typically in stock at Micro Center stores, in the $5–8 range |
| Breadboard | Typically in stock at Micro Center stores, in the $5–10 range |
| USB cables (Jetson↔MCU, etc.) | Typically in stock at Micro Center stores, in the $5–10 range |
| USB webcam | Already planned as a purchase, per the user. Logitech C270: camelcamelcamel history shows $17.99 (2026-06-27 snapshot, out of stock at the time), typical market price $17–29 (searched 2026-09-22). If more resolution/FOV is needed for AprilTag recognition, consider the Logitech C920 (1080p), price unverified (roughly estimated at $60–70) |

---

## 7. Micro Center (US in-store) stock vs. required online orders

**Usually in stock at Micro Center** (generally known stock composition; not individually re-searched item-by-item in this session):
- Arduino Nano / Nano Every
- ESP32 dev boards (stock varies by store, recommended to check online inventory before visiting)
- Jumper wires, breadboards
- USB cables
- Jetson Orin Nano Super Developer Kit (confirmed today: $249 MSRP, **real-time stock/price should be re-confirmed directly** — see the flag in the "Summary" section above)
- USB webcams (Logitech C270/C920 and other common brands)

**Must be ordered online**:
- Pololu 25D/20D encoder gearmotors, brackets, wheels, ball casters (pololu.com)
- DFRobot Baron-4WD / Devastator / HCR platforms (dfrobot.com or Amazon)
- TB6612FNG (Adafruit), Cytron MD10C/MDD10A (cytron.io or Amazon)
- BNO055/BNO085 (Adafruit), ICM-20948 (SparkFun)
- LiPo batteries/chargers — usually not carried at Micro Center's physical stores due to hazardous-material shipping restrictions (need an RC/hobby shop that handles them, or a separate online order)
- Buck/boost converter modules

---

## 8. Full list of unverified items (must re-confirm before purchasing)

1. **Jetson Orin Nano Super real-time Micro Center price** — the microcenter.com product page couldn't be opened directly due to bot blocking (403). Search snippets confirm $249 (MSRP)/$219.99 (promotion), which doesn't match the $399 the user had in mind — confirm this first.
2. The DFRobot Baron-4WD's exact encoder CPR/gear ratio — not listed on the product page/wiki; need to check the DFRobot Wiki's motor datasheet PDF or contact support directly.
3. US list prices for the Pololu bracket (#2676), wheel (70×8mm), and ball caster (#951) — could not be pulled from search (only a UK-site converted figure was obtained), re-confirm directly on pololu.com.
4. Exact USD prices for the Cytron MD10C/MDD10A — access to the cytron.io/Amazon pages failed (403/content not shown).
5. The exact current price of the Adafruit BNO085 (#4754) — only confirmed the phrase "same price as the BNO080," the page itself wasn't directly checked.
6. The confirmed unit price for the ESP32 DevKitC — wide price spread due to many clones, official-source price unconfirmed.
7. LiPo battery, LiPo charger, buck/boost converter, XT60 connector, fuse holder, switch, standoffs — individual price searches for these couldn't all be completed within this session's search budget (≈14 searches). All figures in the table above are **general market estimates**, not actual prices.
8. Teensy 4.0, Raspberry Pi Pico (RP2040) prices — not searched, general-knowledge-level estimates.

**Summary**: items with a confirmed price/URL/date (the Pololu 99:1/227:1 motors, DFRobot Baron-4WD, Adafruit TB6612FNG, Adafruit BNO055, SparkFun ICM-20948, Arduino Nano Every, Jetson MSRP) are high-confidence. Everything else (power components, connectors, MCU clones, some Pololu accessories) is an estimate — re-confirm on each vendor's site before finalizing the shopping cart.
