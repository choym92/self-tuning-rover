# Runbook: day-to-day operation

How to run the rover from the Mac, in order. Facts behind each step live in the linked files;
this page only says what to do. Jetson address and SSH: `AGENTS.md`. Current state: `docs/STATUS.md`.

## 1. Power on

1. Charger unplugged, D436 cable plugged into the Jetson (it reconnects on its own), wheels clear.
2. Plug the battery DC lead. The OLED should show `s 22` (UGV Rover PT). WiFi takes about a minute.
3. From the Mac: `ssh paulcho@192.168.1.238` (key login). If it fails, wait and retry; the address is
   DHCP (`docs/STATUS.md` has the last one).

## 2. Start the services (manual after every boot)

```sh
ssh paulcho@192.168.1.238 'docker start rover-control rover-eyes; docker ps --format "{{.Names}} {{.Status}}"'
```

Add `rover-llm rover-stt rover-tts-st` to the `docker start` list when voice is wanted. The containers
have no restart policy yet (`docs/STATUS.md`, open decision 1). Container run commands, if one is
missing: `jetson/control/README.md`, `jetson/eyes/README.md`, `jetson/llm/README.md`, `jetson/tts/README.md`.

## 3. Open the console

```sh
ssh -N -L 8091:127.0.0.1:8091 paulcho@192.168.1.238
```

Leave that running and open http://localhost:8091. The header should read `LINK ok`, `UART ok`,
`CAM on`. Keys and safety behaviour: `jetson/control/README.md`. Nothing is exposed on the network;
the page exists only through this tunnel.

## 4. Drive

- W/A/S/D while held; Space = emergency stop (latched; "Reset E-stop" on the page clears it).
- Arrow keys or the Head buttons move the head; Center returns to 0/0.
- `[` / `]` lower / raise the speed cap by 10 (default 80, maximum 120).
- Stop driving at the 10.5 V warning; the server refuses to drive below 9.6 V.

## 5. One spoken turn (optional)

From the repository on the Mac: `python3 jetson/voice/talk.py` (records 5 s on the rover microphone)
or `python3 jetson/voice/talk.py --text "Hi"`. Needs `rover-stt`, `rover-llm`, `rover-tts-st` running.

## 6. Charge

1. Shut the Jetson down first (section 7). Plugging the charger into a running rover has rebooted it.
2. Unplug the D436 cable: it collides with the charger plug at the DC jack.
3. Plug the 12.6 V charger. Full is about 12.6 V; a charge from the 10.5 V warning gives about 2 h of
   driving (`docs/rover-hardware.md`).

## 7. Shut down

Paul types the password himself:

```sh
ssh -t paulcho@192.168.1.238 'sudo shutdown -h now'
```

Wait until SSH drops, then pull the DC lead. The silver button on the body does not power the
system off.

## 8. When something is wrong

| Symptom | Do |
|---|---|
| Page shows `LINK lost` or every field `--` | The tunnel or the rover is down. Check the `ssh -N -L` process; `ssh` to the rover; after a reboot run section 2, then reload the page |
| Page loads but stays dead (`LINK --`, "No camera") with the API fine | Served page may be torn: `curl -s http://127.0.0.1:8091/ \| diff - jetson/control/index.html` must print nothing; otherwise copy `index.html` to `~/control/` on the Jetson again |
| `UART 0 Hz` / `UART lost` | ESP32 feedback stream stopped. The stream toggle is `{"T":131,"cmd":1}` (`docs/decisions.md`, robot base); a power cycle of the rover also restores it |
| `D436 off` | Cable unplugged or dropped off the bus; re-seat it, the eyes service reconnects within seconds (`jetson/eyes/README.md`) |
| `D436 standby` | Someone pressed "D436 Off"; press "D436 On" |
| Speaker "Device or resource busy" | Should not recur (udev rule, `docs/preflight.md` 2026-11-07); `talk.py` retries for 10 s anyway |
| Rover reboots when a cable is touched | Power the rover off and inspect the cabling near the DC jack (`docs/setup-log.md` 2026-11-07) |
| Previous boot's logs needed | They are gone: journald is not persistent (open decision 2) |
