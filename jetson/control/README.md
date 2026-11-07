# Rover control console (stage 1)

A browser page on the Mac drives the rover over an SSH tunnel; a small server on the Jetson
owns the ESP32 UART and enforces the safety rules. Standard library only on both sides, so
nothing is installed on the Jetson host; the server runs in the existing JetPack container.

Design and the rules it implements: the design boards (artifact "Self-Tuning Rover Boards",
boards 5 and 6) and `docs/decisions.md`.

| File | Purpose |
|---|---|
| `server.py` | UART reader, 20 Hz control loop, JSON API, serves the page |
| `index.html` | The console page: WASD hold-to-drive, emergency stop, telemetry |
| `test_safety.py` | Unit tests for the controller and the API with a fake UART |

## Safety rules (server side)

- Drive commands are refused unless the server was started with `--allow-drive`.
- A drive command is valid for 0.3 s; the page repeats it every 0.1 s while a key is held and
  sends zero on release, on tab blur and when the SSE link is lost. Expiry sends PWM 0.
- Emergency stop latches: PWM 0, then `{"T":1,"L":0,"R":0}` (zero-speed hold); drive is
  refused until `/api/reset`. Reset is refused below 9.6 V.
- PWM cap: 80 by default, at most 120 from the page in stage 1.
- Below 9.6 V drive is refused; 9.6-10.5 V is shown as a warning.
- The firmware's own 3 s heartbeat stop remains as the last resort.
- T:0 is not used: in this firmware it also releases torque on every bus servo, which
  would let the pan-tilt head drop.

## Local validation (Mac, no Jetson)

```sh
python3 -B -m unittest discover -s jetson/control -p 'test_*.py' -v
```

## Run on the Jetson

Copy the files, then start the container. The port is published on the Jetson's loopback
only; `/timesync` lets the server see whether the clock is synchronised.

```sh
scp jetson/control/server.py jetson/control/index.html paulcho@192.168.1.238:control/
```

Telemetry only (default; drive refused):

```sh
docker run -d --name rover-control --device /dev/ttyTHS1 -p 127.0.0.1:8091:8091 \
  -v /home/paulcho/control:/work:ro -v /run/systemd/timesync:/timesync:ro \
  nvcr.io/nvidia/l4t-jetpack:r36.4.0 python3 /work/server.py --port 8091
```

With driving enabled, after Paul's go, add `--allow-drive` (and optionally `--cap 60`).
Stop with `docker rm -f rover-control`; the server sends a stop on exit.

## Open the page on the Mac

```sh
ssh -N -L 8091:127.0.0.1:8091 paulcho@192.168.1.238
```

Then open http://localhost:8091. Keys: W/A/S/D while held, Space = emergency stop.

## API

| Call | Effect |
|---|---|
| `GET /api/state` | current snapshot (battery, feedback, UART rate, flags) |
| `GET /api/events` | the same snapshot as server-sent events at 5 Hz |
| `POST /api/drive {"l":-1..1,"r":-1..1}` | drive request, scaled by the cap; 403 when refused |
| `POST /api/estop` | latch the emergency stop |
| `POST /api/reset` | clear it (403 below 9.6 V) |
| `POST /api/cap {"pwm":0..120}` | change the cap |
