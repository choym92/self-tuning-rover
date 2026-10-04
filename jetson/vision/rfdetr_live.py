#!/usr/bin/env python3
"""Live view of an RF-DETR COCO model with the D436, to look at it next to YOLO26s.

Runs the model in PyTorch (rfdetr.predict), not TensorRT, so the frame rate is lower than an
integrated engine would give; see docs/verify.md for the TensorRT times. Seg models also draw masks,
and the distance of a segmented object is the median depth inside its mask.

Run (Jetson; rfdetr in ~/yolo/pylib_rfdetr, checkpoints cached in ~/yolo/rfdetr/home):
  docker run --rm --runtime nvidia --ipc host -p 127.0.0.1:8090:8090 -u $(id -u):$(id -g) \
    -e HOME=/work/rfdetr/home -e USER=paulcho -v /home/paulcho/yolo:/work -w /work \
    -v /home/paulcho/src/librealsense/build/Release:/rs:ro -e PYTHONPATH=/rs:/work/pylib_rfdetr \
    -e LD_LIBRARY_PATH=/rs -v /dev/bus/usb:/dev/bus/usb --device-cgroup-rule='c 189:* rmw' \
    ultralytics/ultralytics:latest-jetson-jetpack6 python3 rfdetr_live.py --model RFDETRSegNano
"""
import argparse
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
import pyrealsense2 as rs
import rfdetr
from PIL import Image
from rfdetr.assets.coco_classes import COCO_CLASSES

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="RFDETRSegNano", help="RFDETRNano, RFDETRSmall, RFDETRSegNano, RFDETRSegSmall")
ap.add_argument("--threshold", type=float, default=0.5)
ap.add_argument("--stream-port", type=int, default=8090)
ap.add_argument("--seconds", type=float, default=600)
args = ap.parse_args()

latest = [None]


class Handler(BaseHTTPRequestHandler):
    timeout = 10

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path != "/stream":
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(b"<html><body style='margin:0;background:#111'><img src='/stream' style='width:100%'></body></html>")
            return
        self.send_response(200); self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame"); self.end_headers()
        try:
            while True:
                if latest[0] is not None:
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + latest[0] + b"\r\n")
                time.sleep(0.04)
        except OSError:
            pass


model = getattr(rfdetr, args.model)()
# 0.0.0.0 inside the container; docker run -p 127.0.0.1:... keeps it off the LAN
threading.Thread(target=ThreadingHTTPServer(("0.0.0.0", args.stream_port), Handler).serve_forever, daemon=True).start()

cfg = rs.config()
cfg.enable_stream(rs.stream.color, 848, 480, rs.format.bgr8, 30)
cfg.enable_stream(rs.stream.depth, 848, 480, rs.format.z16, 30)
pipe = rs.pipeline()
prof = pipe.start(cfg)
scale = prof.get_device().first_depth_sensor().get_depth_scale()
align = rs.align(rs.stream.color)
rng = np.random.default_rng(0)
colors = {c: tuple(int(v) for v in rng.integers(60, 255, 3)) for c in COCO_CLASSES}
print(f"{args.model} live on port {args.stream_port}", flush=True)

t0 = time.time()
next_print, frames, ms_hist = t0 + 1, 0, []
try:
    while time.time() - t0 < args.seconds:
        fs = align.process(pipe.wait_for_frames(timeout_ms=2000))
        img = np.asanyarray(fs.get_color_frame().get_data())
        depth = np.asanyarray(fs.get_depth_frame().get_data()).astype(np.float32) * scale
        t = time.perf_counter()
        det = model.predict(Image.fromarray(img[:, :, ::-1]), threshold=args.threshold)
        ms_hist = (ms_hist + [(time.perf_counter() - t) * 1000])[-30:]
        view = img.copy()
        masks = getattr(det, "mask", None)
        found = []
        for i, ((x1, y1, x2, y2), cid, conf) in enumerate(zip(det.xyxy.astype(int), det.class_id, det.confidence)):
            name, col = COCO_CLASSES.get(int(cid), str(cid)), colors.get(int(cid), (0, 255, 0))
            if masks is not None:
                m = masks[i].astype(bool)
                view[m] = (0.5 * view[m] + 0.5 * np.array(col)).astype(np.uint8)
                region = depth[m]
            else:
                w, h = x2 - x1, y2 - y1
                region = depth[max(y1 + int(0.3 * h), 0):y2 - int(0.3 * h), max(x1 + int(0.3 * w), 0):x2 - int(0.3 * w)]
            v = region[region > 0]
            dist = float(np.median(v)) if v.size > 20 else float("nan")
            found.append(f"{name} {dist:.2f} m ({conf:.2f})")
            cv2.rectangle(view, (x1, y1), (x2, y2), col, 2)
            cv2.putText(view, f"{name} {conf:.0%} {dist:.2f} m", (x1, max(y1 - 8, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
        frames += 1
        fps = frames / max(time.time() - t0, 1e-6)
        cv2.putText(view, f"{args.model} (PyTorch) {np.median(ms_hist):.0f} ms/frame  {fps:.1f} fps", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        dvis = cv2.applyColorMap(cv2.convertScaleAbs(np.clip(depth, 0, 4.0), alpha=255 / 4.0), cv2.COLORMAP_TURBO)
        dvis[depth == 0] = 0
        ok, jpg = cv2.imencode(".jpg", np.hstack([view, dvis]), [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            latest[0] = jpg.tobytes()
        if time.time() >= next_print:
            print(f"t={time.time() - t0:5.1f}s  {np.median(ms_hist):.0f} ms  {', '.join(found) or 'nothing'}", flush=True)
            next_print = time.time() + 1
finally:
    pipe.stop()
