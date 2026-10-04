#!/usr/bin/env python3
"""Real-use detector comparison: YOLO26s vs RF-DETR-Nano vs RF-DETR-Small on the same live frames.

The camera is pointed at a new part of the room for each scene. Every recorded frame goes through all
three models; per scene and model we report, for each COCO class, the share of frames in which it
was detected (confidence >= 0.5, and >= 0.3 in parentheses). One annotated three-panel frame per
scene is saved under rfdetr/compare/ on the Jetson so the detections can be checked by eye
(room images: never commit them).

All three run as TensorRT FP16 engines: YOLO through Ultralytics, RF-DETR through rfdetr_trt.py
(engines built by rfdetr_bench.py).

Run (Jetson):
  docker run --rm --runtime nvidia --ipc host -p 127.0.0.1:8090:8090 -u $(id -u):$(id -g) \
    -e HOME=/work/rfdetr/home -e USER=paulcho -v /home/paulcho/yolo:/work -w /work \
    -v /home/paulcho/src/librealsense/build/Release:/rs:ro -e PYTHONPATH=/rs:/work/pylib_rfdetr \
    -e LD_LIBRARY_PATH=/rs -v /dev/bus/usb:/dev/bus/usb --device-cgroup-rule='c 189:* rmw' \
    ultralytics/ultralytics:latest-jetson-jetpack6 python3 detector_compare.py
"""
import argparse
import json
import os
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
import pyrealsense2 as rs
from rfdetr.assets.coco_classes import COCO_CLASSES
from ultralytics import YOLO

from rfdetr_trt import RFDETRTRT

ap = argparse.ArgumentParser()
ap.add_argument("--scenes", type=int, default=10)
ap.add_argument("--record", type=float, default=10.0, help="seconds recorded per scene")
ap.add_argument("--move", type=float, default=6.0, help="seconds to point the camera at the next scene")
ap.add_argument("--stream-port", type=int, default=8090)
ap.add_argument("--out", default="rfdetr/compare")
args = ap.parse_args()
LOW, HIGH = 0.3, 0.5

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


yolo = YOLO("yolo26s.engine", task="detect")
rf = {"RF-DETR-Nano": RFDETRTRT("rfdetr/RFDETRNano.engine"), "RF-DETR-Small": RFDETRTRT("rfdetr/RFDETRSmall.engine")}
MODELS = ["YOLO26s"] + list(rf)


def detect(name, img):
    """[(class name, confidence, (x1, y1, x2, y2))] with confidence >= LOW."""
    if name == "YOLO26s":
        r = yolo(img, imgsz=640, conf=LOW, device=0, verbose=False)[0]
        return [(r.names[int(c)], float(p), tuple(int(v) for v in b))
                for b, p, c in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy(), r.boxes.cls.cpu().numpy())]
    boxes, scores, labels = rf[name].predict(img, threshold=LOW)
    return [(COCO_CLASSES.get(int(c), str(c)), float(p), tuple(int(v) for v in b))
            for b, p, c in zip(boxes, scores, labels)]


def panel(img, name, dets):
    v = img.copy()
    for cls, p, (x1, y1, x2, y2) in dets:
        col = (0, 255, 0) if p >= HIGH else (0, 165, 255)  # green >= 0.5, orange 0.3-0.5
        cv2.rectangle(v, (x1, y1), (x2, y2), col, 2)
        cv2.putText(v, f"{cls} {p:.2f}", (x1 + 3, max(y1 - 6, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 2)
    cv2.rectangle(v, (0, 0), (v.shape[1], 34), (0, 0, 0), -1)
    cv2.putText(v, name, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    return v


def show(views, banner, col):
    grid = np.hstack([cv2.resize(v, (424, 240)) for v in views])
    bar = np.zeros((50, grid.shape[1], 3), np.uint8)
    cv2.putText(bar, banner, (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, col, 2)
    ok, jpg = cv2.imencode(".jpg", np.vstack([bar, grid]), [cv2.IMWRITE_JPEG_QUALITY, 75])
    if ok:
        latest[0] = jpg.tobytes()
    return np.hstack(views)


# 0.0.0.0 inside the container; docker run -p 127.0.0.1:... keeps it off the LAN
threading.Thread(target=ThreadingHTTPServer(("0.0.0.0", args.stream_port), Handler).serve_forever, daemon=True).start()
os.makedirs(args.out, exist_ok=True)
cfg = rs.config()
cfg.enable_stream(rs.stream.color, 848, 480, rs.format.bgr8, 30)
pipe = rs.pipeline()
pipe.start(cfg)


def grab():
    return np.asanyarray(pipe.wait_for_frames(timeout_ms=2000).get_color_frame().get_data()).copy()


for _ in range(3):  # warm-up
    img = grab()
    for m in MODELS:
        detect(m, img)

# results[scene][model] = list of per-frame [(class, conf)]
results = defaultdict(lambda: defaultdict(list))
ms = defaultdict(list)
print(f"{args.scenes} scenes x {args.record:.0f} s; models {MODELS}", flush=True)
try:
    for s in range(1, args.scenes + 1):
        t0 = time.time()
        while time.time() - t0 < args.move:
            img = grab()
            show([img] * 3, f"Scene {s}/{args.scenes}: point the camera somewhere new - recording in "
                            f"{args.move - (time.time() - t0):.0f} s", (0, 165, 255))
        t0, mid_saved = time.time(), False
        while time.time() - t0 < args.record:
            img = grab()
            views = []
            for m in MODELS:
                t = time.perf_counter()
                dets = detect(m, img)
                ms[m].append((time.perf_counter() - t) * 1000)
                results[s][m].append([(c, p) for c, p, _ in dets])
                views.append(panel(img, m, dets))
            full = show(views, f"RECORDING scene {s}/{args.scenes} - hold still  {args.record - (time.time() - t0):.0f} s",
                        (0, 0, 255))
            if not mid_saved and time.time() - t0 > args.record / 2:
                cv2.imwrite(os.path.join(args.out, f"scene_{s:02d}.jpg"), full)
                mid_saved = True
        print(f"scene {s} recorded: {len(results[s][MODELS[0]])} frames", flush=True)
finally:
    pipe.stop()

summary = {}
for s, per_model in results.items():
    classes = sorted({c for m in MODELS for f in per_model[m] for c, _ in f})
    print(f"\nScene {s} ({len(per_model[MODELS[0]])} frames)   % of frames detected at conf>={HIGH} (>={LOW})")
    print(f"  {'class':16s}" + "".join(f"{m:>18s}" for m in MODELS))
    summary[s] = {}
    for c in classes:
        cells = []
        for m in MODELS:
            frames = per_model[m]
            hi = 100 * np.mean([any(cc == c and p >= HIGH for cc, p in f) for f in frames])
            lo = 100 * np.mean([any(cc == c for cc, _ in f) for f in frames])
            cells.append(f"{hi:5.0f}% ({lo:3.0f}%)")
            summary[s].setdefault(c, {})[m] = [round(hi), round(lo)]
        print(f"  {c:16s}" + "".join(f"{x:>18s}" for x in cells))
print("\nmodel time per frame (median, includes pre/post-processing): " +
      ", ".join(f"{m} {np.median(v):.0f} ms" for m, v in ms.items()))
json.dump(summary, open(os.path.join(args.out, "summary.json"), "w"), indent=1)
print(f"annotated scene frames and summary.json in {args.out}/")
