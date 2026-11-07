# Rover hardware map

Where each physical thing is, what the OS calls it, and the traps around it. This is an
index: it states the short fact and links to the canonical record (`docs/verify.md`,
`docs/setup-log.md`, `docs/decisions.md`, `docs/preflight.md`, `jetson/control/README.md`,
`jetson/tts/README.md`). Do not add measurements here. Live state is not recorded here;
re-read it on the device. Last reviewed 2026-11-07; device names below were read live that day.

Platform: Jetson Orin Nano Super 8 GB mounted in a Waveshare UGV Rover PT Acce (6-wheel
skid-steer, ESP32 driver board, pan-tilt, 5 MP camera, audio board, 3S 18650 UPS). Choice and
alternatives: `docs/decisions.md` ("Robot base"). Parts and purchase status: `docs/build-spec.md`.

## 1. Tour, top to bottom

| Zone | What is there | Notes and link |
|---|---|---|
| Head, top | RealSense D436 (depth, colour, IMU), fixed by the kit's 1/4"-20 screw through the head plate; the head's accessory rail was removed | DECIDED by Paul: `docs/decisions.md` ("D436 on the pan-tilt head"); assembly: `docs/setup-log.md` 2026-10-31 |
| Head, below the D436 | 5 MP 160 degree "Xitech USB Camera" with a built-in microphone | Fisheye view; the D436 underside is not visible in it (`docs/verify.md`, console stage 2) |
| Head, pan-tilt | Two ST3215 serial-bus servos driven by the ESP32 | Console limits: pan +-120 degrees, tilt -30 to 60 degrees (`jetson/control/server.py`; rules in `jetson/control/README.md`). The tilt bracket blocks the lower right of the D436 image: `docs/verify.md` (console stage 2); fix deferred by Paul |
| Body (exact placement not documented) | OLED showing ESP32 state, 3.5 mm speaker jack, a silver button, WiFi antennas on the chassis (SMA) | Placement of each is not recorded in the repository; button and antenna details: sections 3 and 4 |
| Inside the body | Jetson devkit on the rover's standoffs; ESP32 driver board with the UPS module; audio board (SSS1629 USB codec, speaker header, fan header, USB hub) under the Jetson carrier | Assembly: `docs/setup-log.md` 2026-10-31; audio board location: 2026-11-07 |
| Inside, on the audio board | 4-position DIP switch, legend "earphone MIC / MIC" | Silences the board microphones as shipped; Paul: leave it unless the camera microphone proves inadequate (`docs/setup-log.md` 2026-11-07) |
| Underside | Battery compartment (four M3x6 hex screws), 3-slot 18650 holder; wheels (6, four driven) | Cells: 3 x Molicel P30B, unprotected flat-top (`docs/build-spec.md`); compartment notes: `docs/setup-log.md` 2026-10-31 |
| Rear | Ethernet port blocked by the chassis; USB-C device-mode port | Section 2 |

## 2. Connectors and device names

USB topology, read live with `lsusb -t` on 2026-11-07:

| Device | Where it enumerates | Speed |
|---|---|---|
| RealSense D436 | Bus 2, under the Jetson's internal 10 Gbps hub (port 2-1.3), `uvcvideo` | 5000 Mbps (USB 3) |
| 5 MP camera (`0abd:8050`) with its microphone | Bus 1, via the internal hub | 480 Mbps |
| Audio board (JMTek `0c76:1229`, "USB PnP Audio Device") | Bus 1, behind its own hub, which sits behind the Jetson hub | the kernel lists the card as "full" speed (12 Mbps) |
| CH343-class serial adapter (`1a86:55d3`), `/dev/ttyACM0` | Bus 1, behind the same hub as the audio board | 12 Mbps; silent, owner unresolved (`docs/setup-log.md` 2026-11-06) |
| Realtek Bluetooth (`rtk_btusb`) | Bus 1 | 12 Mbps |
| Jetson USB-C port | Device mode, not a host port: Jetson `192.168.55.1`, Mac `192.168.55.100` | fallback link |

| Thing | Name | Notes |
|---|---|---|
| ESP32 UART | `/dev/ttyTHS1`, 115200, JSON lines | Only the control server opens it (`docs/decisions.md`, "Console control server owns the UART") |
| 5 MP camera | `/dev/v4l/by-id/usb-Xitech_USB_Camera_20250606105-video-index0` (index0 is the video stream) | Use the by-id name. `/dev/video0` was its number on 2026-11-07 and can move when the D436 is attached (`jetson/control/README.md`) |
| D436 | several `/dev/video*` nodes (video2-5 on 2026-11-07) | Do not read through V4L2. Use librealsense, RSUSB build at `~/src/librealsense/build/Release` (`docs/setup-log.md` 2026-09-24) |
| Sound card 0 | the 5 MP camera microphone | Used for capture by `jetson/voice/talk.py` (`plughw:0,0`) |
| Sound card 1 | audio board: speaker out `plughw:1,0`; its microphones are silent (DIP switch) | Evidence: `docs/verify.md` (console stage 1) and `docs/setup-log.md` 2026-11-07 |
| Cards 2 and 3 | Jetson HDA and APE (DisplayPort audio, internal) | not used |
| Network | home 2.4 GHz WiFi, DHCP, last seen `192.168.1.238`; USB-C fallback `192.168.55.1` | Ethernet blocked. WiFi setup and the clock issue: `docs/setup-log.md` 2026-11-06 |
| Keyboard | Logitech USB receiver, used for local login and the boot menu | The boot menu no longer needs a keypress (`DEFAULT uart-pio`) |

Services on the Jetson (all published on loopback unless noted; the Mac reaches them through SSH tunnels):

| Port | Service | Canonical home |
|---|---|---|
| 8091 | control console (`rover-control`) | `jetson/control/README.md` |
| 8080 | llama-server (Gemma) | `jetson/llm/README.md` |
| 8090 | Whisper STT (`rover-stt`) | `docs/verify.md` (Whisper) |
| 8093 | Supertonic 3 TTS (`rover-tts-st`) | `jetson/tts/README.md` |
| 8092 | Kokoro TTS: installed, off | `jetson/tts/README.md` |

## 3. Known traps (one line each)

- UART: R36.5.2 `serial-tegra` DMA bug; the boot entry `uart-pio` fixes it and is DEFAULT, but any `nvidia-l4t-kernel` update resets DEFAULT to `primary`. `docs/preflight.md` (UART1 boot test entries).
- ESP32 ships set to UGV Beast (`s 30`); the rover needs `{"T":900,"main":2,"module":2}` before driving. Whether the setting survives an ESP32 power cycle is not yet checked. `docs/setup-log.md` 2026-11-06.
- `T:0` also releases torque on every bus servo and would drop the head; emergency stop uses PWM 0 plus a `T:1` zero-speed hold. `docs/decisions.md`, `jetson/control/README.md`.
- One lingering drive request was seen on 2026-11-06; a maximum continuous-drive time is the planned guard, not yet built. `docs/setup-log.md` 2026-11-06.
- `/dev/video` numbers move when the D436 is attached; use `/dev/v4l/by-id/`. `jetson/control/README.md`.
- The D436 USB cable flexes with the head and it dropped off the bus once while handled; keep slack, expect a log line. `docs/verify.md` (console stage 2), `docs/decisions.md`.
- Tilt bracket blocks the lower right of the D436 image and reads as a permanent 0.2-0.5 m obstacle in depth until moved or masked. `docs/verify.md` (console stage 2).
- Audio board microphones are silent because of the DIP switch; the camera microphone is the capture device. `docs/setup-log.md` 2026-11-07.
- PulseAudio (the gdm login-screen session) used to grab the speaker for a few seconds after each `aplay` ("Device or resource busy"). Fixed 2026-11-07 with a udev rule that marks the audio board `PULSE_IGNORE=1` (`scripts/jetson-audio-board-pulse-ignore.sh`, undo with `--undo`); `talk.py` keeps a 10 s retry as a safety net. `docs/setup-log.md` 2026-11-07, `docs/verify.md`.
- Speaker is at its hardware maximum (mixer 100%, clips normalised); mixer settings are runtime only, not persisted. `docs/setup-log.md` 2026-11-06.
- WiFi: two drops on 2026-11-07 (SSH tunnel reset while the Jetson stayed up); WiFi power saving not yet checked. The Jetson boots at 1969 until WiFi time sync arrives, so early logs have wrong timestamps. `docs/setup-log.md`.
- Ethernet is physically blocked by the chassis; use WiFi or the USB-C link. `docs/setup-log.md` 2026-11-06.
- Power: low-voltage thresholds in the console are 10.5 V warn and 9.6 V refuse drive/reset. `jetson/control/README.md`. Charge from the kit's 12.6 V charger. Cells fall to about 10.2 V under drive load (`docs/setup-log.md` 2026-11-06).
- Charging: the charger plug and the D436 cable collide at the DC5521 jack, so unplug the D436 to charge (it reconnects by itself). Plugging the charger has rebooted the running rover; a servo-bus cable routed past the jack cut power when touched until Paul fixed it on 2026-11-07. `docs/setup-log.md` 2026-11-07.
- Power-off (2026-11-07, `docs/setup-log.md`): the silver button did not power the system off (what it is remains unresolved); shut down with `sudo shutdown -h now`, then pull the DC plug.
- Power draw by workload (module rail only, not the whole robot): `docs/verify.md` ("Jetson power draw by workload").
- Memory: Gemma + Whisper + Supertonic use about 5.6 GB of 8 GB; vision on top is tight. `docs/STATUS.md`, `docs/verify.md`.
- Never insert the fallback microSD while the NVMe system runs (identical filesystem UUIDs). `AGENTS.md`.
- The Mac is not a usable live RealSense host. `docs/STATUS.md`.

## 4. Still unknown

- What the silver button does (identity unresolved).
- Whether the rover's WiFi pigtails are fully latched or a different connector size (`docs/setup-log.md` 2026-10-31, OPEN).
- Whether the Ethernet blocker is the DC5521 port (UNVERIFIED, photo was blurred).
- Which board carries the CH343 serial adapter (`/dev/ttyACM0`): INFERENCE, probably a lidar bridge.
- Whether the `T:900` rover setting survives an ESP32 power cycle.
- UART behaviour under vision load (soak not done) and the cause of the 1.5 degree pan undershoot.
- Whether the D436 mount screw length is adequate (a longer one was being sourced) and whether the 5 MP camera sees the D436 underside.
- Real wall power draw (only the module rail was measured).
- Whether the DIP switch needs flipping (depends on voice recognition through the camera microphone, a Paul decision).
