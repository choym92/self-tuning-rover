#!/usr/bin/env python3
"""Rover control server, stage 2: hold-to-drive and the camera views from a browser, with the safety rules on the Jetson.

The server is the only process that opens the ESP32 UART. It reads the T:1001 feedback
stream, serves the console page and a small JSON API, and runs a 20 Hz control loop that
decides what the wheels get:

  emergency stop latched        -> stop (PWM 0, then a zero-speed hold with T:1)
  no drive command for CMD_TTL  -> stop (covers key release, a closed tab and a lost link)
  battery below LOW_V_STOP      -> drive refused
  otherwise                     -> T:11 with the browser's -1..1 request scaled by the PWM cap

Drive commands are refused until the server is started with --allow-drive, so the telemetry
side can be tested without any risk of motion. Python standard library, plus OpenCV (already in
the JetPack container) to read the camera's native MJPEG frames for /video.mjpg without decoding.

Run on the Jetson (see README.md):
  docker run --rm --name rover-control --device /dev/ttyTHS1 --device /dev/video0 -p 127.0.0.1:8091:8091 \
    -v /home/paulcho/control:/work:ro -v /run/systemd/timesync:/timesync:ro \
    nvcr.io/nvidia/l4t-jetpack:r36.4.0 python3 /work/server.py --port 8091
"""
import argparse
import json
import os
import select
import sys
import termios
import threading
import time
import urllib.request
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CAP_DEFAULT = 80          # PWM out of 255; Paul's first limit
CAP_MAX = 120             # the page cannot raise the cap above this in stage 1
CMD_TTL = 0.3             # seconds a drive command stays valid
TICK = 0.05               # control loop period
LOW_V_WARN = 10.5         # volts
LOW_V_STOP = 9.6
PAN_LIMIT = 120           # degrees each way; keeps the D436 USB cable from wrapping
TILT_MIN, TILT_MAX = -30, 60   # firmware allows -30..90; 60 keeps the head clear of the body
HEAD_SPD, HEAD_ACC = 40, 15    # T:133 speed/acceleration, moderate
HEAD_MIN_INTERVAL = 0.1   # seconds between head commands
SYNC_FILE = "/timesync/synchronized"   # systemd-timesyncd touches this after the first sync
VIDEO_SIZE, VIDEO_FPS = (1280, 720), 20   # the 5 MP camera delivers this as MJPEG at 20 fps (verify.md)
HERE = os.path.dirname(os.path.abspath(__file__))


class SerialLink:
    """Reads JSON lines from the ESP32 and writes commands. Thread-safe."""

    def __init__(self, path, baud=termios.B115200):
        self.path = path
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        attrs = termios.tcgetattr(self.fd)
        attrs[0] = 0
        attrs[1] = 0
        attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        attrs[3] = 0
        attrs[4] = attrs[5] = baud
        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        self._lock = threading.Lock()
        self._latest = {}
        self._latest_t = 0.0
        self._times = deque()
        self._bad = 0
        self._sent = 0
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        buf = b""
        while True:
            ready, _, _ = select.select([self.fd], [], [], 0.2)
            if not ready:
                continue
            try:
                buf += os.read(self.fd, 4096)
            except BlockingIOError:
                continue
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    with self._lock:
                        self._bad += 1
                    continue
                if msg.get("T") == 1001:
                    now = time.monotonic()
                    with self._lock:
                        self._latest = msg
                        self._latest_t = now
                        self._times.append(now)
                        while self._times and now - self._times[0] > 2.0:
                            self._times.popleft()

    def send(self, obj):
        data = json.dumps(obj, separators=(",", ":")).encode() + b"\n"
        with self._lock:
            os.write(self.fd, data)
            self._sent += 1

    def latest(self):
        with self._lock:
            return dict(self._latest)

    def stats(self):
        with self._lock:
            age = time.monotonic() - self._latest_t if self._latest_t else None
            return {"rate_hz": round(len(self._times) / 2.0, 1), "feedback_age_s": None if age is None else round(age, 2),
                    "bad_lines": self._bad, "sent": self._sent}


class Controller:
    """Turns browser requests into wheel commands under the safety rules."""

    def __init__(self, link, cap=CAP_DEFAULT, allow_drive=False, clock=time.monotonic, synced=None):
        self.link = link
        self.cap = cap
        self.allow_drive = allow_drive
        self.clock = clock
        self.synced = synced or (lambda: os.path.exists(SYNC_FILE))
        self._lock = threading.Lock()
        self.estop = False
        self.target = (0.0, 0.0)
        self.target_t = -1e9
        self.last_pwm = (0, 0)
        self.moving = False
        self.last_reason = "idle"
        self.head = (0.0, 0.0)          # target pan, tilt in degrees
        self.head_dirty = False
        self.head_sent_t = -1e9

    def voltage(self):
        v = self.link.latest().get("v")
        return None if v is None else v / 100.0

    def drive(self, l, r):
        try:
            l = max(-1.0, min(1.0, float(l)))
            r = max(-1.0, min(1.0, float(r)))
        except (TypeError, ValueError):
            return "bad_request"
        with self._lock:
            if not self.allow_drive:
                return "disabled"
            if self.estop:
                return "estop"
            v = self.voltage()
            if v is not None and v < LOW_V_STOP:
                return "low_voltage"
            self.target = (l, r)
            self.target_t = self.clock()
            return "ok"

    def set_cap(self, cap):
        try:
            cap = int(cap)
        except (TypeError, ValueError):
            return "bad_request"
        if not 0 <= cap <= CAP_MAX:
            return "out_of_range"
        with self._lock:
            self.cap = cap
        return "ok"

    def emergency_stop(self):
        with self._lock:
            self.estop = True
            self.target = (0.0, 0.0)
            self._send_stop(hold=True)

    def reset(self):
        with self._lock:
            v = self.voltage()
            if v is not None and v < LOW_V_STOP:
                return "low_voltage"
            self.estop = False
            self.target = (0.0, 0.0)
            self.target_t = -1e9
            return "ok"

    def move_head(self, pan=None, tilt=None, dpan=0.0, dtilt=0.0):
        """Absolute pan/tilt (degrees) or a relative nudge; clamped to the limits."""
        try:
            with self._lock:
                p = float(self.head[0] if pan is None else pan) + float(dpan)
                t = float(self.head[1] if tilt is None else tilt) + float(dtilt)
                if self.estop:
                    return "estop"
                self.head = (max(-PAN_LIMIT, min(PAN_LIMIT, p)), max(TILT_MIN, min(TILT_MAX, t)))
                self.head_dirty = True
                return "ok"
        except (TypeError, ValueError):
            return "bad_request"

    def _send_head(self):
        self.link.send({"T": 133, "X": round(self.head[0], 1), "Y": round(self.head[1], 1), "SPD": HEAD_SPD, "ACC": HEAD_ACC})
        self.head_dirty = False
        self.head_sent_t = self.clock()

    def _send_stop(self, hold=False):
        self.link.send({"T": 11, "L": 0, "R": 0})
        if hold:
            self.link.send({"T": 1, "L": 0, "R": 0})
        self.last_pwm = (0, 0)
        self.moving = False

    def tick(self):
        """One control step. Called every TICK by the loop thread."""
        with self._lock:
            now = self.clock()
            if self.head_dirty and not self.estop and now - self.head_sent_t >= HEAD_MIN_INTERVAL:
                self._send_head()
            if self.estop:
                desired, reason = (0, 0), "estop"
            elif now - self.target_t > CMD_TTL:
                desired, reason = (0, 0), "expired" if self.moving else "idle"
            else:
                desired = (int(round(self.target[0] * self.cap)), int(round(self.target[1] * self.cap)))
                reason = "drive"
            self.last_reason = reason
            if desired == (0, 0):
                if self.moving:
                    self._send_stop()
                return
            if desired != self.last_pwm or not self.moving:
                self.link.send({"T": 11, "L": desired[0], "R": desired[1]})
                self.last_pwm = desired
                self.moving = True

    def snapshot(self):
        fb = self.link.latest()
        v = None if fb.get("v") is None else fb["v"] / 100.0
        with self._lock:
            return {
                "allow_drive": self.allow_drive,
                "estop": self.estop,
                "cap": self.cap,
                "pwm": list(self.last_pwm),
                "moving": self.moving,
                "reason": self.last_reason,
                "head": {"pan": round(self.head[0], 1), "tilt": round(self.head[1], 1),
                         "pan_limit": PAN_LIMIT, "tilt_min": TILT_MIN, "tilt_max": TILT_MAX},
                "battery_v": v,
                "battery_state": None if v is None else ("stop" if v < LOW_V_STOP else "warn" if v < LOW_V_WARN else "ok"),
                "clock_synced": bool(self.synced()),
                "server_time": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                "feedback": {k: fb.get(k) for k in ("L", "R", "odl", "odr", "pan", "tilt", "ax", "ay", "az", "gx", "gy", "gz")},
                "uart": self.link.stats(),
            }


class Camera:
    """Hands out the camera's own JPEG frames (no decode, no re-encode) to any number of stream clients.

    A reader thread keeps the newest frame; `wait(seq)` blocks a client until a frame newer than
    `seq` exists, so slow clients simply skip frames. With device=None nothing is opened and
    frames come from `push()` (unit tests)."""

    def __init__(self, device=None, size=VIDEO_SIZE, fps=VIDEO_FPS):
        self.device, self.size, self.fps_req = device, size, fps
        self._cond = threading.Condition()
        self._frame, self._seq, self._t = b"", 0, 0.0
        self._times = deque()
        self.ok, self.error, self.clients = False, None if device else "no camera", 0
        if device:
            threading.Thread(target=self._reader, daemon=True).start()

    def _open(self):
        import cv2   # Jetson container only
        cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        if not cap.isOpened():
            return None
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.size[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.size[1])
        cap.set(cv2.CAP_PROP_FPS, self.fps_req)
        cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
        cap.set(cv2.CAP_PROP_FORMAT, -1)     # raw buffer: the JPEG exactly as the camera sent it
        return cap

    def _reader(self):
        while True:
            try:
                cap = self._open()
            except Exception as e:          # missing cv2, wrong device type
                cap, self.error = None, str(e)
            if cap is None:
                self.ok, self.error = False, self.error or "cannot open %s" % self.device
                time.sleep(2.0)
                continue
            self.error = None
            while True:
                ok, frame = cap.read()
                if not ok or frame is None:
                    break
                data = frame.tobytes()
                if data[:2] == b"\xff\xd8":
                    self.push(data)
            cap.release()
            self.ok, self.error = False, "read failed; reopening"
            time.sleep(1.0)

    def push(self, data):
        now = time.monotonic()
        with self._cond:
            self._frame, self._seq, self._t = data, self._seq + 1, now
            self._times.append(now)
            while self._times and now - self._times[0] > 2.0:
                self._times.popleft()
            self.ok, self.error = True, None
            self._cond.notify_all()

    def wait(self, seq, timeout=2.0):
        """(frame, seq) of the first frame newer than `seq`, or (None, seq) after `timeout`."""
        with self._cond:
            if self._seq <= seq:
                self._cond.wait(timeout)
            return (self._frame, self._seq) if self._seq > seq else (None, seq)

    def latest(self):
        with self._cond:
            return self._frame

    def stats(self):
        with self._cond:
            return {"ok": self.ok, "fps": round(len(self._times) / 2.0, 1), "size": "%dx%d" % tuple(self.size),
                    "age_s": None if not self._t else round(time.monotonic() - self._t, 2),
                    "clients": self.clients, "error": self.error}


class EyesLink:
    """Talks to the eyes service (the D436 owner, jetson/eyes/): polls its state once a second and
    opens its streams for the /d436/ proxy, so the page needs one origin and one tunnel."""

    def __init__(self, base=None):
        self.base = base.rstrip("/") if base else None
        self.state = {"connected": False, "error": "eyes service not configured" if not base else "not reached yet"}
        if self.base:
            threading.Thread(target=self._poll, daemon=True).start()

    def _poll(self):
        while True:
            try:
                with urllib.request.urlopen(self.base + "/api/state", timeout=1.0) as r:
                    self.state = json.loads(r.read())
            except Exception:
                self.state = {"connected": False, "error": "eyes service unreachable"}
            time.sleep(1.0)

    def open(self, path):
        return urllib.request.urlopen(self.base + path, timeout=5)


def control_loop(controller):
    while True:
        controller.tick()
        time.sleep(TICK)


def make_handler(controller, page_path, camera=None, eyes=None):
    camera = camera or Camera()
    eyes = eyes or EyesLink()

    def state():
        s = controller.snapshot()
        s["camera"] = camera.stats()
        s["d436"] = eyes.state
        return s

    class Handler(BaseHTTPRequestHandler):
        server_version = "rover-control/0.2"

        def log_message(self, fmt, *args):
            if self.path.startswith(("/api/events", "/api/drive", "/api/head", "/frame.jpg")):
                return
            sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

        def _bytes(self, code, ctype, body):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > 4096:
                return {}
            try:
                return json.loads(self.rfile.read(n))
            except ValueError:
                return {}

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                with open(page_path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            elif self.path.startswith("/api/state"):
                self._json(200, state())
            elif self.path.startswith("/api/events"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    while True:
                        self.wfile.write(("data: %s\n\n" % json.dumps(state())).encode())
                        self.wfile.flush()
                        time.sleep(0.2)
                except (BrokenPipeError, ConnectionResetError):
                    return
            elif self.path.startswith("/d436/"):
                # Pass-through to the eyes service; streams are copied chunk by chunk as they arrive.
                if not eyes.base:
                    self._json(503, {"error": "eyes service not configured"})
                    return
                try:
                    up = eyes.open(self.path[len("/d436"):])
                except Exception:
                    self._json(503, {"error": "eyes service unreachable"})
                    return
                try:
                    self.send_response(up.status)
                    for h in ("Content-Type", "Content-Length"):
                        if up.headers.get(h):
                            self.send_header(h, up.headers[h])
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    while True:
                        chunk = up.read1(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return
                finally:
                    up.close()
            elif self.path.startswith("/frame.jpg"):
                frame = camera.latest()
                if frame:
                    self._bytes(200, "image/jpeg", frame)
                else:
                    self._json(503, {"error": camera.error or "no frame yet"})
            elif self.path.startswith("/video.mjpg"):
                # Motion JPEG: each camera frame is one multipart body part; <img src="/video.mjpg"> plays it.
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                camera.clients += 1
                seq = 0
                try:
                    while True:
                        frame, seq = camera.wait(seq)
                        if frame is None:       # camera reopening: keep the connection, send nothing
                            continue
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(frame))
                        self.wfile.write(frame + b"\r\n")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return
                finally:
                    camera.clients -= 1
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            body = self._body()
            if self.path == "/api/drive":
                result = controller.drive(body.get("l"), body.get("r"))
                self._json(200 if result == "ok" else 403 if result in ("disabled", "estop", "low_voltage") else 400,
                           {"result": result})
            elif self.path == "/api/estop":
                controller.emergency_stop()
                self._json(200, {"result": "ok"})
            elif self.path == "/api/reset":
                result = controller.reset()
                self._json(200 if result == "ok" else 403, {"result": result})
            elif self.path == "/api/head":
                result = controller.move_head(body.get("pan"), body.get("tilt"), body.get("dpan", 0), body.get("dtilt", 0))
                self._json(200 if result == "ok" else 403 if result == "estop" else 400, {"result": result, "head": controller.snapshot()["head"]})
            elif self.path == "/api/cap":
                result = controller.set_cap(body.get("pwm"))
                self._json(200 if result == "ok" else 400, {"result": result, "cap": controller.cap})
            else:
                self._json(404, {"error": "not found"})

    return Handler


def serve(controller, host, port, page_path, camera=None, eyes=None):
    threading.Thread(target=control_loop, args=(controller,), daemon=True).start()
    httpd = ThreadingHTTPServer((host, port), make_handler(controller, page_path, camera, eyes))
    httpd.daemon_threads = True
    return httpd


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--serial", default="/dev/ttyTHS1")
    ap.add_argument("--host", default="0.0.0.0", help="inside the container; publish on 127.0.0.1 only")
    ap.add_argument("--port", type=int, default=8091)
    ap.add_argument("--cap", type=int, default=CAP_DEFAULT, help="PWM cap, 0-%d" % CAP_MAX)
    ap.add_argument("--allow-drive", action="store_true", help="accept drive commands (off: telemetry only)")
    ap.add_argument("--camera", default="/dev/video0", help="V4L2 device for /video.mjpg; 'none' to run without video")
    ap.add_argument("--eyes", default="http://127.0.0.1:8094", help="eyes service (D436) proxied under /d436/; 'none' to disable")
    args = ap.parse_args()
    if not 0 <= args.cap <= CAP_MAX:
        sys.exit("--cap must be 0-%d" % CAP_MAX)
    link = SerialLink(args.serial)
    controller = Controller(link, cap=args.cap, allow_drive=args.allow_drive)
    camera = Camera(None if args.camera == "none" else args.camera)
    eyes = EyesLink(None if args.eyes == "none" else args.eyes)
    httpd = serve(controller, args.host, args.port, os.path.join(HERE, "index.html"), camera, eyes)
    print("rover-control on %s:%d, serial %s, cap %d, drive %s, camera %s, eyes %s" % (
        args.host, args.port, args.serial, args.cap, "ALLOWED" if args.allow_drive else "disabled", args.camera, args.eyes), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        controller.emergency_stop()


if __name__ == "__main__":
    main()
