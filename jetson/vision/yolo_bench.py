#!/usr/bin/env python3
"""Benchmark a YOLO26 model (default yolo26s) on the Jetson inside the Ultralytics container.

Exports the PyTorch weights to a TensorRT FP16 engine (once, cached in /work), then times
inference on a fixed image and reports latency percentiles, plus the engine file size and
GPU memory seen by torch. Compare with Ultralytics' published Orin Nano Super figure
(YOLO26n TensorRT FP16: 4.57 ms, mAP50-95 0.48; docs.ultralytics.com/guides/nvidia-jetson).

Run (Jetson):
  docker run --rm --runtime nvidia --ipc host -v ~/yolo:/work -w /work \
    ultralytics/ultralytics:latest-jetson-jetpack6 python3 yolo_bench.py [yolo26n|yolo26s|yolo26s-pose|...]
"""
import os
import time

import numpy as np
from ultralytics import YOLO

import sys

NAME = sys.argv[1] if len(sys.argv) > 1 else "yolo26s"
WEIGHTS = f"{NAME}.pt"
ENGINE = f"{NAME}.engine"
TASK = "pose" if NAME.endswith("-pose") else "detect"
IMAGE = "https://ultralytics.com/images/bus.jpg"
N = 200

if not os.path.exists(ENGINE):
    t = time.time()
    YOLO(WEIGHTS).export(format="engine", half=True, imgsz=640, device=0)
    print(f"export to TensorRT FP16 took {time.time() - t:.0f} s")

for name, path in (("pytorch", WEIGHTS), ("tensorrt_fp16", ENGINE)):
    model = YOLO(path, task=TASK)
    for _ in range(10):  # warm-up
        model(IMAGE, imgsz=640, device=0, verbose=False)
    lat = []
    for _ in range(N):
        r = model(IMAGE, imgsz=640, device=0, verbose=False)[0]
        lat.append(r.speed["inference"])  # ms, model forward only (Ultralytics' own split)
    lat = np.array(lat)
    people = int(sum(1 for c in r.boxes.cls.tolist() if r.names[int(c)] == "person"))
    print(f"{name:14s} inference ms: median {np.median(lat):.2f}  p90 {np.percentile(lat, 90):.2f}  "
          f"min {lat.min():.2f}  -> {1000 / np.median(lat):.0f} fps; persons found in bus.jpg: {people}; "
          f"pre {r.speed['preprocess']:.1f} ms post {r.speed['postprocess']:.1f} ms")

print(f"files: {WEIGHTS} {os.path.getsize(WEIGHTS) / 1e6:.1f} MB, {ENGINE} {os.path.getsize(ENGINE) / 1e6:.1f} MB")
try:
    import torch
    print(f"torch max GPU memory allocated: {torch.cuda.max_memory_allocated() / 1e6:.0f} MB")
except Exception as e:
    print("torch memory n/a:", e)
