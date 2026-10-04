#!/usr/bin/env python3
"""Person detection by distance: YOLO26s vs RF-DETR-Nano vs RF-DETR-Small on the same live frames.

Paul stands at guided distances (facing the camera, sideways, back turned). The distance is the
median depth in the central 40% of the most confident person box of any of the three models; a frame
in which all three miss keeps the last distance (if under 0.5 s old), so it still counts as a miss.
A frame is recorded only within +-BAND of the target. (A fixed centre strip was tried first and
measured the wall whenever Paul stood off-centre.) Per segment and model: share of
frames with a person at confidence >= 0.5 (and >= 0.3), median confidence and median box height.
One annotated frame per segment is saved under rfdetr/distance/ on the Jetson (never commit it).

Run (Jetson): as detector_compare.py, with python3 detector_distance.py
"""
import argparse
import os
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
import pyrealsense2 as rs
from ultralytics import YOLO

from rfdetr_trt import RFDETRTRT

SEGMENTS = [(1.0, "face the camera"), (2.0, "face the camera"), (3.0, "face the camera"),
            (3.0, "stand SIDEWAYS"), (2.0, "turn your BACK to the camera"), (3.0, "turn your BACK to the camera")]
BAND = 0.3
FRAMES = 90
TIMEOUT = 45
LOW, HIGH = 0.3, 0.5
PERSON_COCO = 1  # RF-DETR labels are COCO category ids

ap = argparse.ArgumentParser()
ap.add_argument("--stream-port", type=int, default=8090)
ap.add_argument("--out", default="rfdetr/distance")
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


yolo = YOLO("yolo26s.engine", task="detect")
rf = {"RF-DETR-Nano": RFDETRTRT("rfdetr/RFDETRNano.engine"), "RF-DETR-Small": RFDETRTRT("rfdetr/RFDETRSmall.engine")}
MODELS = ["YOLO26s"] + list(rf)


def people(name, img):
    """[(confidence, (x1, y1, x2, y2))] for persons with confidence >= LOW."""
    if name == "YOLO26s":
        r = yolo(img, imgsz=640, conf=LOW, classes=[0], device=0, verbose=False)[0]
        return [(float(p), tuple(int(v) for v in b)) for b, p in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy())]
    boxes, scores, labels = rf[name].predict(img, threshold=LOW)
    return [(float(p), tuple(int(v) for v in b)) for b, p, c in zip(boxes, scores, labels) if c == PERSON_COCO]


def panel(img, name, dets):
    v = img.copy()
    for p, (x1, y1, x2, y2) in dets:
        col = (0, 255, 0) if p >= HIGH else (0, 165, 255)
        cv2.rectangle(v, (x1, y1), (x2, y2), col, 2)
        cv2.putText(v, f"person {p:.2f}", (x1 + 3, max(y1 - 6, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
    cv2.rectangle(v, (0, 0), (v.shape[1], 34), (0, 0, 0), -1)
    cv2.putText(v, name, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    return v


def show(views, banner, col):
    grid = np.hstack([cv2.resize(v, (424, 240)) for v in views])
    bar = np.zeros((50, grid.shape[1], 3), np.uint8)
    cv2.putText(bar, banner, (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.85, col, 2)
    ok, jpg = cv2.imencode(".jpg", np.vstack([bar, grid]), [cv2.IMWRITE_JPEG_QUALITY, 75])
    if ok:
        latest[0] = jpg.tobytes()
    return np.hstack(views)


def box_distance(depth, box):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    patch = depth[y1 + int(0.3 * h):y2 - int(0.3 * h), x1 + int(0.3 * w):x2 - int(0.3 * w)]
    v = patch[patch > 0]
    return float(np.median(v)) if v.size > 20 else None


# 0.0.0.0 inside the container; docker run -p 127.0.0.1:... keeps it off the LAN
threading.Thread(target=ThreadingHTTPServer(("0.0.0.0", args.stream_port), Handler).serve_forever, daemon=True).start()
os.makedirs(args.out, exist_ok=True)
cfg = rs.config()
cfg.enable_stream(rs.stream.color, 848, 480, rs.format.bgr8, 30)
cfg.enable_stream(rs.stream.depth, 848, 480, rs.format.z16, 30)
pipe = rs.pipeline()
prof = pipe.start(cfg)
scale = prof.get_device().first_depth_sensor().get_depth_scale()
align = rs.align(rs.stream.color)


def grab():
    fs = align.process(pipe.wait_for_frames(timeout_ms=2000))
    return (np.asanyarray(fs.get_color_frame().get_data()).copy(),
            np.asanyarray(fs.get_depth_frame().get_data()).astype(np.float32) * scale)


img, _ = grab()
for m in MODELS:  # warm-up
    people(m, img)

rec = defaultdict(lambda: defaultdict(list))  # rec[segment][model] = [(best conf or 0, box height or 0)]
dists = defaultdict(list)
try:
    for k, (target, pose) in enumerate(SEGMENTS, 1):
        t0 = time.time()
        while time.time() - t0 < 6:
            img, _ = grab()
            show([img] * 3, f"Next {k}/{len(SEGMENTS)}: stand at {target:.0f} m, {pose}", (0, 165, 255))
        t0, saved = time.time(), False
        last_d, last_t = None, 0.0
        while len(dists[k]) < FRAMES and time.time() - t0 < TIMEOUT:
            img, depth = grab()
            dets = {m: people(m, img) for m in MODELS}
            top = max((x for m in MODELS for x in dets[m]), default=None)
            d = box_distance(depth, top[1]) if top is not None else None
            if d is not None:
                last_d, last_t = d, time.time()
            elif time.time() - last_t < 0.5:
                d = last_d
            in_band = d is not None and abs(d - target) <= BAND
            views = []
            for m in MODELS:
                if in_band:
                    best = max(dets[m], default=(0.0, (0, 0, 0, 0)))
                    rec[k][m].append((best[0], best[1][3] - best[1][1]))
                views.append(panel(img, m, dets[m]))
            you = f"you {d:.2f} m" if d is not None else "you: -"
            if in_band:
                dists[k].append(d)
                msg, col = f"{you}  HOLD - recording {len(dists[k])}/{FRAMES}", (0, 255, 0)
            elif d is None or d < target:
                msg, col = f"{you}  step BACK", (0, 165, 255)
            else:
                msg, col = f"{you}  step FORWARD", (0, 165, 255)
            full = show(views, f"{k}/{len(SEGMENTS)} {target:.0f} m, {pose}:  {msg}", col)
            if in_band and not saved and len(dists[k]) >= FRAMES // 2:
                cv2.imwrite(os.path.join(args.out, f"seg_{k}_{target:.0f}m.jpg"), full)
                saved = True
        print(f"segment {k} ({target:.0f} m, {pose}): {len(dists[k])} frames in band", flush=True)
finally:
    pipe.stop()

print(f"\nperson found at conf>={HIGH} (>={LOW}), median confidence when found, median box height px")
for k, (target, pose) in enumerate(SEGMENTS, 1):
    if not dists[k]:
        print(f"{k} {target:.0f} m {pose}: not reached")
        continue
    print(f"{k} {target:.0f} m {pose} (median {np.median(dists[k]):.2f} m, {len(dists[k])} frames)")
    for m in MODELS:
        r = rec[k][m]
        conf = np.array([c for c, _ in r])
        hgt = [h for c, h in r if c > 0]
        med = f"{np.median(conf[conf > 0]):.2f}" if (conf > 0).any() else "-"
        print(f"   {m:14s} {100 * (conf >= HIGH).mean():5.0f}% ({100 * (conf >= LOW).mean():3.0f}%)  "
              f"conf {med}  height {np.median(hgt) if hgt else 0:.0f} px")
