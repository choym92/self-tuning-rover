# Eyes service (D436 owner)

One process owns the RealSense D436 and hands its pictures out: the console page gets JPEG
streams through the control server's `/d436/` proxy, and later the recorder (stage 4) and the
vision models get the raw frames from the same process. Nothing else should open the camera;
librealsense allows one owner at a time.

| File | Purpose |
|---|---|
| `eyes_server.py` | D436 reader thread (auto-reconnect), JPEG encode on demand, MJPEG and state endpoints |
| `test_eyes.py` | Unit tests with a fake camera and a fake encoder (no numpy needed) |

## Run on the Jetson

No image build: the JetPack container already has OpenCV and numpy, and the RSUSB librealsense
build on the host is mounted in. The container joins the control container's network namespace,
so the control server reaches it at `127.0.0.1:8094` and the Mac needs no second tunnel. Start it
after `rover-control` and restart it whenever `rover-control` is recreated.

```sh
scp jetson/eyes/eyes_server.py paulcho@192.168.1.238:eyes/
docker run -d --name rover-eyes --network container:rover-control \
  -v /home/paulcho/eyes:/work:ro -v /home/paulcho/src/librealsense/build/Release:/rs:ro \
  -e PYTHONPATH=/rs -e LD_LIBRARY_PATH=/rs \
  -v /dev/bus/usb:/dev/bus/usb --device-cgroup-rule='c 189:* rmw' \
  nvcr.io/nvidia/l4t-jetpack:r36.4.0 python3 /work/eyes_server.py --port 8094
```

Stop with `docker rm -f rover-eyes`. Unit tests on the Mac:

```sh
python3 -B -m unittest discover -s jetson/eyes -p 'test_*.py' -v
```

## API (inside the namespace; the page uses them as `/d436/...`)

| Call | Effect |
|---|---|
| `GET /color.mjpg[?fps=N]` | colour 848x480 as Motion JPEG (quality 80); `fps` thins the stream for small views |
| `GET /depth.mjpg[?fps=N]` | depth coloured blue (0.3 m) to red (4 m), black = no data; 15 fps by default (the raw stream stays at 30) |
| `GET /color.jpg`, `/depth.jpg` | newest single frame; 503 until the camera delivers |
| `GET /api/state` | connected, enabled, fps, valid depth fraction, centre distance (m), serial, firmware, USB type, clients |
| `POST /api/camera {"on": false}` | standby: the camera is released (no USB traffic, no reader CPU); `{"on": true}` reopens it in a few seconds |

Depth pictures are for eyes only: measurement and recording use the raw 16-bit frames inside this
process, never the JPEG. The tilt bracket shows in the lower right until it is moved
(`docs/rover-hardware.md`).
