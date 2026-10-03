#!/usr/bin/env python3
"""Live person detection + distance + bearing with the D436 and YOLO26n (TensorRT FP16).

For every person box: distance = median of valid depth pixels in the central 40% of the box
(aligned to color), bearing = horizontal angle from the color camera's optical axis
(negative = left of center). Prints a line per second, times every stage, and saves one
annotated frame.

Run (Jetson), mounting our RSUSB librealsense build and the USB devices into the container:
  docker run --rm --runtime nvidia --ipc host \
    -v /home/paulcho/yolo:/work -w /work \
    -v /home/paulcho/src/librealsense/build/Release:/rs:ro -e PYTHONPATH=/rs \
    -v /dev/bus/usb:/dev/bus/usb --device-cgroup-rule='c 189:* rmw' \
    ultralytics/ultralytics:latest-jetson-jetpack6 python3 person_distance.py --seconds 20
"""
import argparse
import math
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
import pyrealsense2 as rs
from ultralytics import YOLO

ap = argparse.ArgumentParser()
ap.add_argument("--seconds", type=float, default=20)
ap.add_argument("--engine", default="yolo26n.engine")
ap.add_argument("--conf", type=float, default=0.4)
ap.add_argument("--out", default="person_distance.jpg")
ap.add_argument("--all-classes", action="store_true", help="detect all 80 COCO classes, not only person")
ap.add_argument("--owner", default="", help="owner file from face_enroll_guided.py, e.g. owner/paul_guided.npz")
ap.add_argument("--face-detector", choices=["scrfd", "yunet"], default="scrfd")
ap.add_argument("--face-every", type=int, default=3, help="run face recognition every N frames")
ap.add_argument("--stream-port", type=int, default=0,
                help="if > 0, serve a live MJPEG view (color with boxes | depth) on this port")
args = ap.parse_args()

latest_jpeg = [None]
if args.stream_port:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path != "/stream":
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body style='margin:0;background:#111'>"
                                 b"<img src='/stream' style='width:100%'></body></html>")
                return
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while True:
                    jpg = latest_jpeg[0]
                    if jpg is not None:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n")
                    time.sleep(0.04)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("0.0.0.0", args.stream_port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"live view on port {args.stream_port}", flush=True)

W, H, FPS = 848, 480, 30
cfg = rs.config()
cfg.enable_stream(rs.stream.depth, W, H, rs.format.z16, FPS)
cfg.enable_stream(rs.stream.color, W, H, rs.format.bgr8, FPS)
pipe = rs.pipeline()
prof = pipe.start(cfg)
scale = prof.get_device().first_depth_sensor().get_depth_scale()
intr = prof.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
align = rs.align(rs.stream.color)
print(f"color intrinsics fx {intr.fx:.1f} cx {intr.ppx:.1f}; depth scale {scale}")

fid = None
if args.owner:
    from face_owner import FaceID
    fid = FaceID("models", detector=args.face_detector)
    fid.load_owner(args.owner)
    print(f"face detector {args.face_detector}, ArcFace threshold {fid.threshold}", flush=True)
    print(f"owner: {fid.owner_name} ({len(fid.owner_samples)} samples)", flush=True)
owner_box, owner_sim, owner_seen = None, 0.0, 0.0
face_scores = []  # (x-centre px, similarity) of every face in the last face check, for the log

model = YOLO(args.engine, task="detect")
PERSON = [k for k, v in model.names.items() if v == "person"][0] if hasattr(model, "names") and model.names else 0

timing = {"wait": [], "align": [], "yolo": [], "post": []}
frames = 0
t0 = time.time()
next_print = t0 + 1
saved = False
try:
    while time.time() - t0 < args.seconds:
        a = time.perf_counter()
        fs = pipe.wait_for_frames(timeout_ms=2000)
        b = time.perf_counter()
        fs = align.process(fs)
        d_frame, c_frame = fs.get_depth_frame(), fs.get_color_frame()
        if not d_frame or not c_frame:
            continue
        depth = np.asanyarray(d_frame.get_data()).astype(np.float32) * scale
        img = np.asanyarray(c_frame.get_data())
        c = time.perf_counter()
        res = model(img, imgsz=640, conf=args.conf, classes=None if args.all_classes else [PERSON],
                    device=0, verbose=False)[0]
        d = time.perf_counter()

        people = []
        for (x1, y1, x2, y2), conf, cls in zip(res.boxes.xyxy.cpu().numpy(), res.boxes.conf.cpu().numpy(),
                                               res.boxes.cls.cpu().numpy()):
            w, h = x2 - x1, y2 - y1
            cx1, cx2 = int(x1 + 0.3 * w), int(x2 - 0.3 * w)
            cy1, cy2 = int(y1 + 0.3 * h), int(y2 - 0.3 * h)
            patch = depth[max(cy1, 0):max(cy2, 1), max(cx1, 0):max(cx2, 1)]
            valid = patch[patch > 0]
            dist = float(np.median(valid)) if valid.size > 20 else float("nan")
            u = (x1 + x2) / 2
            bearing = math.degrees(math.atan2(u - intr.ppx, intr.fx))
            people.append((dist, bearing, float(conf), (int(x1), int(y1), int(x2), int(y2)), res.names[int(cls)]))
        # Owner: find faces, give the owner label to the person box that contains the owner's face.
        if fid is not None and frames % args.face_every == 0:
            matches = fid.match(img)
            face_scores = [(int(f[0] + f[2] / 2), round(sim, 2)) for f, sim, _ in matches]
            # Only one owner exists: consider only the best-scoring face, and only if it passes the threshold.
            best_face = max(matches, key=lambda m: m[1], default=None)
            for f, sim, is_owner in ([best_face] if best_face else []):
                if not is_owner:
                    continue
                fx, fy = f[0] + f[2] / 2, f[1] + f[3] / 2
                for p in people:
                    x1, y1, x2, y2 = p[3]
                    if p[4] == "person" and x1 <= fx <= x2 and y1 <= fy <= y2:
                        owner_box, owner_sim, owner_seen = p[3], sim, time.time()
        if owner_box is not None and time.time() - owner_seen < 1.5:
            # keep the label on the person box that overlaps the last owner box most (simple persistence)
            def iou(a, b):
                ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
                inter = ix * iy
                return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter + 1e-9)
            best = max((p for p in people if p[4] == "person"), key=lambda p: iou(p[3], owner_box), default=None)
            if best is not None and iou(best[3], owner_box) > 0.3:
                i = people.index(best)
                people[i] = best[:4] + (f"{fid.owner_name} (owner) {owner_sim:.2f}",)
                owner_box = best[3]
        e = time.perf_counter()

        if args.stream_port:
            view = img.copy()
            for dist, bearing, conf, (x1, y1, x2, y2), name in people:
                color = (0, 215, 255) if "(owner)" in name else (0, 255, 0)
                cv2.rectangle(view, (x1, y1), (x2, y2), color, 3 if "(owner)" in name else 2)
                cv2.putText(view, f"{name} {conf:.0%} {dist:.2f} m {bearing:+.0f} deg", (x1, max(y1 - 8, 15)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            dvis = cv2.applyColorMap(cv2.convertScaleAbs(np.clip(depth, 0, 4.0), alpha=255 / 4.0), cv2.COLORMAP_TURBO)
            dvis[depth == 0] = 0
            fps_now = frames / max(time.time() - t0, 1e-6)
            cv2.putText(view, f"{fps_now:.1f} fps", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            ok, jpg = cv2.imencode(".jpg", np.hstack([view, dvis]), [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                latest_jpeg[0] = jpg.tobytes()

        timing["wait"].append((b - a) * 1000)
        timing["align"].append((c - b) * 1000)
        timing["yolo"].append((d - c) * 1000)
        timing["post"].append((e - d) * 1000)
        frames += 1

        if time.time() >= next_print:
            desc = ", ".join(f"{p[4]} {p[0]:.2f} m @ {p[1]:+.0f} deg ({p[2]:.2f})" for p in sorted(people, key=lambda q: q[0])) or "nothing"
            extra = f"  faces(x px: score) {face_scores}" if fid is not None else ""
            print(f"t={time.time() - t0:5.1f}s  {len(people)} object(s): {desc}{extra}", flush=True)
            next_print += 1

        if people and not saved and time.time() - t0 > 2:
            for dist, bearing, conf, (x1, y1, x2, y2), name in people:
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(img, f"{dist:.2f} m {bearing:+.0f} deg", (x1, max(y1 - 8, 15)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.imwrite(args.out, img)
            saved = True
finally:
    pipe.stop()

el = time.time() - t0
print(f"\n{frames} frames in {el:.1f} s = {frames / el:.1f} fps end-to-end")
for k, v in timing.items():
    v = np.array(v)
    print(f"  {k:5s} median {np.median(v):6.2f} ms  p90 {np.percentile(v, 90):6.2f} ms")
print(f"annotated frame: {args.out if saved else 'none (no person seen after 2 s)'}")
