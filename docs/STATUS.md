# Current project status

Last reviewed: 2026-11-07 EST

This is the short cross-agent handoff. It records current direction, not the
full evidence. Follow its links for measurements and history. Re-check live
processes and hardware instead of assuming this snapshot is still running.

## Platform

- VERIFIED: Jetson Orin Nano Super 8 GB, JetPack 6.2.3 / L4T R36.5.2, kernel
  5.15.199-tegra, CUDA 12.6, root on the 512 GB NVMe, MAXN_SUPER, boot default
  `uart-pio` (the `primary` entry still has the UART DMA bug; a kernel update
  resets DEFAULT to it, `docs/preflight.md`).
- VERIFIED: SSH from the Mac at `paulcho@192.168.1.238` (home 2.4 GHz WiFi, DHCP)
  with key login; USB-C fallback `192.168.55.1`; Ethernet physically blocked.
- DECIDED: experimental GPU workloads remain containerized; models live under
  `/home/paulcho/models`, builds and logs under `/home/paulcho/llm`. One host
  change exists outside containers: the udev rule that keeps PulseAudio off the
  audio board (`docs/preflight.md` 2026-11-07, undo script in `scripts/`).
- TEMPORARY: `paulcho` is in the Docker group (since 2026-09-25); removal
  (`sudo gpasswd -d paulcho docker`) is still pending, Paul's call.
- Journald is not persistent and the containers have no restart policy: after a
  reboot, logs of the previous boot are gone and the five containers must be
  started by hand (`docker start rover-control rover-eyes rover-brainlink rover-stt rover-tts-st`).
  Both are open decisions (below).

Read-only live checks:

```sh
ssh paulcho@192.168.1.238 'hostname; uptime; free -m; docker ps --format "{{.Names}} {{.Status}}"'
curl -s http://127.0.0.1:8091/api/state | head -c 300      # through the tunnel: ssh -N -L 8091:127.0.0.1:8091 paulcho@192.168.1.238
```

## Active focus: driving the rover from the Mac (console stage 2 done)

- VERIFIED on the rover (2026-11-07): `jetson/control/` serves the console on
  Jetson loopback 8091. WASD hold-to-drive (PWM cap 80, maximum 120, `[`/`]`
  change it), latched emergency stop, link-loss stop, low-voltage refusal,
  pan-tilt with settle correction (lands within 0.3 deg; 56 deg/s), 5 MP camera
  MJPEG passthrough at 1280x720 20 fps, D436 colour and depth through the eyes
  service (`jetson/eyes/`, standby button, auto-reconnect), camera-first steering.
  Measurements: `docs/verify.md` (console stage 1 and 2, eyes service, settle).
- The page: instrument-rail look, English only, numbers shown only when something
  is off (`jetson/control/README.md`). Deploy = copy the file and check
  `curl -s http://127.0.0.1:8091/ | diff - jetson/control/index.html` is empty
  (a torn copy killed the page once, `docs/setup-log.md` 2026-11-07).
- Calibration trim (`--pan-trim/--tilt-trim`) is still 0: the true forward
  direction has not been measured (needs the D436 and a target).
- Not implemented: a maximum continuous-drive time (one lingering drive request
  on 2026-11-06), remote access from outside the home LAN (candidate: Tailscale
  on the home Mac mini as a jump host, the Jetson untouched; needs a low-rate
  video mode and a security review before anything is installed).

## Next big piece: the logging / replay / tuning loop (not started)

The project's thesis (`README.md`): every stream logged with timestamps,
replayed on the Mac against AprilTag ground truth, scored (RMSE, NIS), and the
filter/controller parameters tuned by hand, search or an LLM on held-out logs.
Nothing of `tools/` exists yet. Agreed first slice (2026-11-07, Paul: "next
time"): a logger inside `rover-control` (feedback packets, commands, frame
timestamps), AprilTags at measured positions, and a Mac script that plots
dead reckoning against the tag fixes. Known data caveats: `odl`/`odr` are integer
centimetres, wheel speeds are firmware-smoothed, the IMU occasionally repeats
samples (`docs/decisions.md`).

## Voice and LLM (working, on hold)

- VERIFIED: `jetson/voice/talk.py` runs one spoken turn in English or Korean:
  camera microphone → Whisper (`rover-stt`, English model) → Gemma with thinking
  off (`rover-llm`) → Supertonic 3 voice M1 (`rover-tts-st`) → rover speaker.
  Kokoro is installed but off. Audio8 TTS was tried and removed (9x slower,
  `docs/verify.md`).
- Open: Korean speech input (Whisper multilingual), sentence-by-sentence TTS
  playback, wake word, a louder external speaker. Design notes:
  `docs/voice-orchestration.md`, `jetson/voice/README.md`.
- LLM moved 2026-11-07: Gemma now runs on the home Mac mini (`macmini/`), reached through the
  rover-side tunnel `rover-brainlink` at the same `127.0.0.1:8080` (`docs/preflight.md`, `docs/decisions.md`).
  `rover-llm` is stopped, not removed. Jetson memory available rose to about 4.5 GB, enough for vision.
  If the Mac mini is down, speech generation stops; driving is unaffected. Model candidates for the mini are
  being researched.

## Hardware

- Rover: Waveshare UGV Rover PT with the Jetson, ESP32 driver (`s 22`), 3 x Molicel
  P30B (about 2 h of driving, warn 10.5 V, stop 9.6 V), 5 MP camera and the D436 on
  the pan-tilt head. Layout, device names and traps: `docs/rover-hardware.md`.
- D436: works on the rover over USB 3 (spare long cable, cable ties planned). The
  tilt bracket blocks the lower right of its view (Paul: fix later, move the camera
  forward or add a spacer). Unplug it to charge: the plug collides with the
  charger at the DC jack. The eyes service reconnects on its own.
- Power incidents 2026-11-07: plugging the charger rebooted the rover several times
  and a servo-bus cable past the DC jack cut power when touched; Paul reports the
  cable fixed (method not yet recorded). Do not hot-plug the charger. The silver
  button does not power the system off; use `sudo shutdown -h now`.
- WiFi: two link drops on 2026-11-07 with the Jetson up; one antenna reseated
  (signal 74 -> 100 %). Power saving and the u.FL pigtails not yet checked.
- Audio board microphones are silent (DIP switch under the Jetson carrier); Paul:
  leave it, the camera microphone is used. PulseAudio no longer grabs the speaker.

## Open decisions and problems (one list)

1. Docker restart policy for the containers (auto-start after a reboot or not).
2. Persistent journald (`sudo mkdir /var/log/journal`) so reboots keep their logs.
3. Continuous-drive time limit in the control server.
4. Forward-direction calibration (`--pan-trim`) and the tilt bracket.
5. Charging point: a DC5521 extension so the charger does not go near the cables.
6. WiFi reliability: power save off or 5 GHz; pigtail latching.
7. Remote access from the office (security review first).
8. (closed 2026-11-07) The Claude Design canvas was brought to this state: index
   board plus six refreshed boards. It is Paul's visual summary; the repository stays
   canonical.

## Documentation health

- `AGENTS.md` is stable policy and a task-based document router.
- `CLAUDE.md` imports `AGENTS.md`; do not duplicate it.
- This file is the only current-state handoff.
- Historical setup and research files are not mandatory reading. Search and
  open only the section relevant to the current task.
