#!/usr/bin/env python3
"""RF-DETR vs YOLO26 on the Jetson: same TensorRT FP16 path for every model.

For each RF-DETR model: download the COCO checkpoint, run it once in PyTorch on bus.jpg (objects
found), export ONNX, then build and time a TensorRT FP16 engine with trtexec. The YOLO ONNX files
already in /work are built and timed with the same trtexec command, so the GPU times compare
directly. trtexec "GPU Compute Time" is the model forward only (no pre/post-processing).

Run (Jetson; rfdetr and its extra packages live in ~/yolo/pylib_rfdetr, not in the image):
  docker run --rm --runtime nvidia --ipc host -u $(id -u):$(id -g) -e HOME=/tmp -e USER=paulcho \
    -v /home/paulcho/yolo:/work -w /work -e PYTHONPATH=/work/pylib_rfdetr \
    ultralytics/ultralytics:latest-jetson-jetpack6 python3 rfdetr_bench.py
"""
import os
import re
import subprocess
import sys
import time

import numpy as np
from PIL import Image

TRTEXEC = "/usr/src/tensorrt/bin/trtexec"
OUT = "rfdetr"
RF_MODELS = sys.argv[1:] or ["RFDETRNano", "RFDETRSmall", "RFDETRSegNano", "RFDETRSegSmall"]
YOLO_ONNX = ["yolo26s.onnx", "yolo26s-pose.onnx"]


def trt_time(onnx_path, engine_path):
    """Build an FP16 engine with trtexec and return (median GPU compute ms, engine MB, build s)."""
    t = time.time()
    log = subprocess.run([TRTEXEC, f"--onnx={onnx_path}", "--fp16", f"--saveEngine={engine_path}",
                          "--iterations=200", "--warmUp=2000", "--useCudaGraph"],
                         capture_output=True, text=True).stdout
    build = time.time() - t
    m = re.search(r"GPU Compute Time: min = [\d.]+ ms, max = [\d.]+ ms, mean = [\d.]+ ms, median = ([\d.]+) ms", log)
    if not m or not os.path.exists(engine_path):
        print(log[-3000:])
        return None, None, build
    return float(m.group(1)), os.path.getsize(engine_path) / 1e6, build


os.makedirs(OUT, exist_ok=True)
img = Image.open("bus.jpg").convert("RGB")
rows = []
for name in RF_MODELS:
    import rfdetr
    model = getattr(rfdetr, name)()
    det = model.predict(img, threshold=0.5)
    for _ in range(5):  # warm-up
        model.predict(img, threshold=0.5)
    lat = []
    for _ in range(20):
        t = time.perf_counter()
        model.predict(img, threshold=0.5)
        lat.append((time.perf_counter() - t) * 1000)
    from rfdetr.assets.coco_classes import COCO_CLASSES  # predictions use COCO category ids (person = 1)
    labels = [COCO_CLASSES.get(int(c), str(c)) for c in det.class_id]
    persons = sum(1 for lb in labels if lb == "person")
    masks = getattr(det, "mask", None) is not None
    res = getattr(model.model, "resolution", None)
    print(f"{name}: resolution {res}, bus.jpg objects {len(labels)} (persons {persons}), masks {masks}, "
          f"PyTorch predict median {np.median(lat):.1f} ms", flush=True)
    onnx_dir = os.path.join(OUT, name)
    onnx_path = model.export(output_dir=onnx_dir, verbose=False)
    onnx_path = str(onnx_path) if onnx_path and str(onnx_path).endswith(".onnx") else \
        next(os.path.join(onnx_dir, f) for f in os.listdir(onnx_dir) if f.endswith(".onnx"))
    ms, mb, build = trt_time(onnx_path, os.path.join(OUT, f"{name}.engine"))
    rows.append((name, res, ms, mb, build, persons, len(labels)))
    print(f"  TensorRT FP16: {ms} ms median GPU compute, engine {mb} MB, build {build:.0f} s", flush=True)
    del model

for onnx_path in YOLO_ONNX:
    if not os.path.exists(onnx_path):
        continue
    ms, mb, build = trt_time(onnx_path, os.path.join(OUT, onnx_path.replace(".onnx", ".trtexec.engine")))
    rows.append((onnx_path[:-5], 640, ms, mb, build, None, None))
    print(f"{onnx_path}: TensorRT FP16 {ms} ms median GPU compute, engine {mb} MB, build {build:.0f} s", flush=True)

print("\nmodel | input px | TRT FP16 GPU ms (median) | engine MB | bus.jpg persons / objects (conf 0.5)")
for name, res, ms, mb, build, persons, objs in rows:
    ms_s = f"{ms:.2f}" if ms else "failed"
    mb_s = f"{mb:.1f}" if mb else "-"
    po = f"{persons} / {objs}" if persons is not None else "-"
    print(f"{name} | {res} | {ms_s} | {mb_s} | {po}")
