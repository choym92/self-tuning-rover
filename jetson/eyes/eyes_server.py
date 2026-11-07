#!/usr/bin/env python3
"""Eyes service: the one process that owns the RealSense D436 and hands its pictures out.

  D436 --librealsense--> colour (BGR8) + depth (Z16) at 848x480, 30 fps
       --> /color.mjpg, /depth.mjpg (JPEG, encoded only while someone watches; ?fps=N thins the stream)
       --> /color.jpg, /depth.jpg (newest frame), /api/state (fps, valid depth, centre distance)

The control server proxies these under /d436/ for the console page. Later the same process will
record the raw frames and feed the vision models, so nothing else should open the camera.
Standard library plus pyrealsense2, numpy and OpenCV (all present in the JetPack container).

Run on the Jetson (see README.md): in the control container's network namespace, with the RSUSB
librealsense build and the USB bus mounted.
"""
import argparse
import json
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SIZE, FPS = (848, 480), 30
JPEG_QUALITY = 80
DEPTH_NEAR, DEPTH_FAR = 0.3, 4.0      # metres mapped onto the colour scale for the depth picture
DEPTH_PICTURE_FPS = 15                # default rate of /depth.mjpg; the raw stream stays at 30 fps
DEPTH_PICTURE_SCALE = 0.5             # the depth picture is drawn at half size (a colour map needs no more)


class RealSenseSource:
    """Opens the D436 and returns (colour BGR array, depth uint16 array) per frame."""

    def __init__(self, size=SIZE, fps=FPS):
        self.size, self.fps = size, fps
        self.pipeline = None
        self.depth_scale = 0.001
        self.info = {}

    def start(self):
        import pyrealsense2 as rs
        cfg = rs.config()
        cfg.enable_stream(rs.stream.depth, self.size[0], self.size[1], rs.format.z16, self.fps)
        cfg.enable_stream(rs.stream.color, self.size[0], self.size[1], rs.format.bgr8, self.fps)
        self.pipeline = rs.pipeline()
        profile = self.pipeline.start(cfg)
        dev = profile.get_device()
        self.depth_scale = dev.first_depth_sensor().get_depth_scale()
        self.info = {"serial": dev.get_info(rs.camera_info.serial_number),
                     "firmware": dev.get_info(rs.camera_info.firmware_version),
                     "usb": dev.get_info(rs.camera_info.usb_type_descriptor)}

    def read(self):
        import numpy as np
        frames = self.pipeline.wait_for_frames(timeout_ms=2000)
        c, d = frames.get_color_frame(), frames.get_depth_frame()
        if not c or not d:
            return None
        return np.asanyarray(c.get_data()).copy(), np.asanyarray(d.get_data()).copy()

    def stop(self):
        if self.pipeline is not None:
            try:
                self.pipeline.stop()
            except Exception:
                pass
            self.pipeline = None


class CvEncoder:
    """JPEG for the browser and a few numbers from the depth image. OpenCV + numpy."""

    def __init__(self, quality=JPEG_QUALITY):
        self.quality = quality

    def color_jpeg(self, bgr):
        import cv2
        ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality])
        return buf.tobytes() if ok else b""

    def depth_jpeg(self, depth, scale):
        """Near = blue, far = red (the same convention as d436_check.py); no data = black.
        Drawn at half size with OpenCV's saturating 16-to-8-bit conversion: no float image."""
        import cv2
        import numpy as np
        if DEPTH_PICTURE_SCALE != 1.0:
            depth = cv2.resize(depth, None, fx=DEPTH_PICTURE_SCALE, fy=DEPTH_PICTURE_SCALE, interpolation=cv2.INTER_NEAREST)
        near, span = DEPTH_NEAR / scale, (DEPTH_FAR - DEPTH_NEAR) / scale
        idx = cv2.convertScaleAbs(np.maximum(depth, int(near)), alpha=255.0 / span, beta=-near * 255.0 / span)
        img = cv2.applyColorMap(idx, cv2.COLORMAP_JET)
        img[depth == 0] = 0
        ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality])
        return buf.tobytes() if ok else b""

    def depth_stats(self, depth, scale):
        import numpy as np
        valid = depth > 0
        h, w = depth.shape
        block = depth[h // 2 - 2:h // 2 + 3, w // 2 - 2:w // 2 + 3]
        block = block[block > 0]
        return {"valid": round(float(valid.mean()), 3),
                "center_m": None if block.size == 0 else round(float(np.median(block)) * scale, 3)}


class Eyes:
    """Keeps the newest frame pair, encodes on demand (once per frame per kind) and serves waiters."""

    def __init__(self, source=None, encoder=None):
        self.source, self.encoder = source, encoder
        self._cond = threading.Condition()
        self._color = self._depth = None
        self._seq, self._t = 0, 0.0
        self._times = deque()
        self._cache = {}            # kind -> (seq, jpeg bytes)
        self._stats = {}
        self.enabled = True              # False = standby: the camera is released, nothing is read
        self.connected, self.error, self.clients = False, None if source else "no camera", 0
        if source is not None:
            threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        while True:
            if not self.enabled:
                self.connected, self.error = False, "standby"
                time.sleep(0.5)
                continue
            try:
                self.source.start()
                self.error = None
                while self.enabled:
                    pair = self.source.read()
                    if pair is not None:
                        self.push(*pair)
            except Exception as e:          # camera unplugged, USB reset, no device yet
                self.connected, self.error = False, str(e).strip().split("\n")[0][:120]
            self.source.stop()
            self.connected = False
            if self.enabled:
                time.sleep(2.0)

    def set_enabled(self, on):
        """Standby releases the D436 (no USB traffic, no reader CPU); waking takes a few seconds."""
        self.enabled = bool(on)
        if not self.enabled:
            self.connected, self.error = False, "standby"
        with self._cond:
            self._times.clear()

    def push(self, color, depth):
        now = time.monotonic()
        with self._cond:
            self._color, self._depth = color, depth
            self._seq, self._t = self._seq + 1, now
            self._times.append(now)
            while self._times and now - self._times[0] > 2.0:
                self._times.popleft()
            self.connected = True
            if self._seq % 10 == 1 and self.encoder is not None:     # a few numbers, not every frame
                self._stats = self.encoder.depth_stats(depth, self.source.depth_scale if self.source else 0.001)
            self._cond.notify_all()

    def wait(self, seq, timeout=2.0):
        with self._cond:
            if self._seq <= seq:
                self._cond.wait(timeout)
            return self._seq if self._seq > seq else None

    def jpeg(self, kind):
        """Newest frame of `kind` ("color" or "depth") as JPEG, encoded at most once per frame."""
        with self._cond:
            seq, color, depth = self._seq, self._color, self._depth
            cached = self._cache.get(kind)
            if cached and cached[0] == seq:
                return cached[1], seq
        if seq == 0 or self.encoder is None:
            return b"", seq
        scale = self.source.depth_scale if self.source else 0.001
        data = self.encoder.color_jpeg(color) if kind == "color" else self.encoder.depth_jpeg(depth, scale)
        with self._cond:
            if not self._cache.get(kind) or self._cache[kind][0] < seq:
                self._cache[kind] = (seq, data)
        return data, seq

    def state(self):
        with self._cond:
            s = {"connected": self.connected, "enabled": self.enabled, "fps": round(len(self._times) / 2.0, 1),
                 "size": "%dx%d" % tuple(SIZE), "age_s": None if not self._t else round(time.monotonic() - self._t, 2),
                 "clients": self.clients, "error": self.error, "frames": self._seq}
            s.update(self._stats)
        if self.source is not None:
            s.update(self.source.info)
        return s


def make_handler(eyes):
    class Handler(BaseHTTPRequestHandler):
        server_version = "rover-eyes/0.1"

        def log_message(self, fmt, *args):
            if self.path.startswith(("/api/state", "/color.jpg", "/depth.jpg")):
                return
            sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

        def _send(self, code, ctype, body):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path, _, query = self.path.partition("?")
            params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
            if path in ("/", "/health", "/api/state"):
                self._send(200, "application/json", json.dumps(eyes.state()).encode())
            elif path in ("/color.jpg", "/depth.jpg"):
                data, _ = eyes.jpeg(path[1:-4])
                if data:
                    self._send(200, "image/jpeg", data)
                else:
                    self._send(503, "application/json", json.dumps({"error": eyes.error or "no frame yet"}).encode())
            elif path in ("/color.mjpg", "/depth.mjpg"):
                kind = path[1:-5]
                try:
                    interval = 1.0 / max(1.0, min(30.0, float(params.get("fps", DEPTH_PICTURE_FPS if kind == "depth" else FPS))))
                except ValueError:
                    interval = 1.0 / FPS
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                eyes.clients += 1
                seq, last = 0, 0.0
                try:
                    while True:
                        new = eyes.wait(seq)
                        if new is None:
                            continue
                        seq = new
                        if time.monotonic() - last < interval:
                            continue
                        data, _ = eyes.jpeg(kind)
                        if not data:
                            continue
                        last = time.monotonic()
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(data))
                        self.wfile.write(data + b"\r\n")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return
                finally:
                    eyes.clients -= 1
            else:
                self._send(404, "application/json", b'{"error": "not found"}')

        def do_POST(self):
            if self.path.split("?")[0] == "/api/camera":
                n = int(self.headers.get("Content-Length") or 0)
                try:
                    body = json.loads(self.rfile.read(n)) if 0 < n <= 4096 else {}
                except ValueError:
                    body = {}
                if "on" not in body:
                    self._send(400, "application/json", json.dumps({"error": "expected {\"on\": true|false}"}).encode())
                    return
                eyes.set_enabled(body["on"])
                self._send(200, "application/json", json.dumps(eyes.state()).encode())
            else:
                self._send(404, "application/json", b'{"error": "not found"}')

    return Handler


def serve(eyes, host, port):
    httpd = ThreadingHTTPServer((host, port), make_handler(eyes))
    httpd.daemon_threads = True
    return httpd


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", default="0.0.0.0", help="inside the container; the control server proxies it")
    ap.add_argument("--port", type=int, default=8094)
    ap.add_argument("--quality", type=int, default=JPEG_QUALITY)
    args = ap.parse_args()
    eyes = Eyes(RealSenseSource(), CvEncoder(args.quality))
    httpd = serve(eyes, args.host, args.port)
    print("rover-eyes on %s:%d, D436 %dx%d @ %d fps, JPEG q%d" % (args.host, args.port, SIZE[0], SIZE[1], FPS, args.quality), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
