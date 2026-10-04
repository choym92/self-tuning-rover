#!/usr/bin/env python3
"""Camera + one detector, nothing else: for measuring RAM and GPU load per detector.

Runs the D436 colour stream (848x480, 30 fps) through one TensorRT FP16 detector for --seconds and
prints frames per second and the median detector time. RAM and GPU load are sampled from outside
(tegrastats and docker stats on the host) while it runs.

  --model yolo26s        Ultralytics YOLO("yolo26s.engine")
  --model rfdetr-nano    rfdetr_trt.RFDETRTRT("rfdetr/RFDETRNano.engine")
  --model rfdetr-small   rfdetr_trt.RFDETRTRT("rfdetr/RFDETRSmall.engine")
"""
import argparse
import time

import numpy as np
import pyrealsense2 as rs

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=["yolo26s", "rfdetr-nano", "rfdetr-small"])
ap.add_argument("--seconds", type=float, default=40)
args = ap.parse_args()

if args.model == "yolo26s":
    from ultralytics import YOLO
    yolo = YOLO("yolo26s.engine", task="detect")

    def detect(img):
        return yolo(img, imgsz=640, conf=0.5, device=0, verbose=False)[0]
else:
    from rfdetr_trt import RFDETRTRT
    rf = RFDETRTRT({"rfdetr-nano": "rfdetr/RFDETRNano.engine", "rfdetr-small": "rfdetr/RFDETRSmall.engine"}[args.model])

    def detect(img):
        return rf.predict(img, threshold=0.5)

cfg = rs.config()
cfg.enable_stream(rs.stream.color, 848, 480, rs.format.bgr8, 30)
pipe = rs.pipeline()
pipe.start(cfg)
for _ in range(10):  # warm-up
    detect(np.asanyarray(pipe.wait_for_frames().get_color_frame().get_data()))
print("RUNNING", flush=True)
ms, frames, t0 = [], 0, time.time()
try:
    while time.time() - t0 < args.seconds:
        img = np.asanyarray(pipe.wait_for_frames(timeout_ms=2000).get_color_frame().get_data())
        t = time.perf_counter()
        detect(img)
        ms.append((time.perf_counter() - t) * 1000)
        frames += 1
finally:
    pipe.stop()
print(f"{args.model}: {frames / (time.time() - t0):.1f} fps, detector median {np.median(ms):.1f} ms "
      f"p90 {np.percentile(ms, 90):.1f} ms", flush=True)
