# Prior art for the 2026-10-03 vision measurements

Dated web research (2026-10-03): which of the measurements in `docs/verify.md` from that day were
already published. FOUND = a source states it; PARTIAL = related or other hardware; NOT FOUND =
learned only by measuring. Reddit was not searched (blocked).

## Detectors (YOLO26s vs RF-DETR)

| Our finding | Status | Source |
|---|---|---|
| RF-DETR-Nano TRT FP16 ~5.8 ms model-only on Jetson | PARTIAL: 6.0 ms on Orin NX (batch 1, trtexec); only RF-DETR Base (14.83 ms) published for Orin Nano Super | roboflow.com/blog/rf-detr-nvidia-deepstream; huggingface.co/embedl/rf-detr-base |
| End-to-end Nano 14 ms, Small 19 ms | FOUND (Orin NX: 12.7 ms, 19.0 ms) | docs.roboflow.com/reference/inference/inference-python/benchmarks |
| YOLO26s on Orin Nano Super | PARTIAL: only YOLO26n (4.57 ms) published | docs.ultralytics.com/guides/nvidia-jetson/ |
| Same RAM and GPU share for YOLO26s and RF-DETR-Nano at 30 fps | NOT FOUND | - |
| RF-DETR finds chairs YOLO26s misses; laptop vs tv | NOT FOUND (no per-class comparisons published) | - |
| RF-DETR gives more low-confidence guesses | PARTIAL: DETR-family calibration is known to be poor for unmatched queries | arxiv.org/html/2412.01782v2 |
| Transformer slows relatively more on Jetson | NOT FOUND; ratios from mixed vendor setups are inconclusive | - |
| Python TensorRT runner for RF-DETR | FOUND: trtutils, Embedl `infer_trt.py` (ours is independent) | trtutils.readthedocs.io/en/latest/tutorials/rtdetr/rfdetr.html |

## Face recognition (SCRFD + ArcFace) on TensorRT

| Our finding | Status | Source |
|---|---|---|
| SCRFD 13.0 ms, ArcFace 4.5 ms TRT FP16 on Orin Nano | NOT FOUND (x86 numbers only) | github.com/SthPhoenix/InsightFace-REST |
| FP16 embeddings identical (cosine 1.0000) | PARTIAL: FP16 recommended, no numbers | insightface.ai/guides/convert-onnx-to-tensorrt-openvino |
| SCRFD output order can change in TensorRT | FOUND (pitfall; our validation shows it did not affect us) | forums.developer.nvidia.com/t/tx2-scrfd-model-tensorrt-conversion-faulty/325077 |
| onnxruntime CUDA EP costs much RAM on Jetson (we saw ~0.8 GB) | FOUND (>= 1.5 GB on Xavier NX, older JetPack); cuDNN workspace defaults explain part | forums.developer.nvidia.com/t/high-ram-consumption-with-cuda-and-tensorrt-on-jetson-xavier-nx/183107; onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html |
| CPU and GPU memory are the same DRAM | FOUND | docs.nvidia.com/cuda/cuda-for-tegra-appnote/ |
| 2.5-4x TRT vs ORT speed-up | FOUND as typical (2.5-4x on Orin NX); part is FP16 itself | docs.roboflow.com benchmarks; github.com/hokwangchoi/jetson-orin-nano-benchmarks |
| Whole-loop fps 21 -> 28.7, GPU 53% -> 31% | NOT FOUND | - |

## Tracking, owner binding, gestures

| Our finding | Status | Source |
|---|---|---|
| New track ID after leaving the frame | FOUND (maintainer statement) | github.com/orgs/ultralytics/discussions/19784 |
| `track_buffer` counts processed frames, not seconds | FOUND in source (`byte_tracker.py`); 30 frames = about 1 s at 29 fps | github.com/ultralytics/ultralytics |
| `model.track` returns untracked boxes when no track exists | PARTIAL: visible in source (`track.py`), no issue or doc | - |
| BYTETracker fed by another detector | PARTIAL: API documented, no RF-DETR example | docs.ultralytics.com/reference/trackers/byte_tracker/ |
| Face-bound owner track surviving back view | PARTIAL: the problem is well studied (face + body ReID); our thresholds are ours | arxiv.org/abs/2309.12479; arxiv.org/abs/2309.11727 |
| Pose costs little over detect | FOUND on T4 (2.7 vs 2.5 ms for YOLO26s) | docs.ultralytics.com/tasks/pose/ |
| COCO has no monitor class | FOUND (62 tv) | docs.ultralytics.com/datasets/detect/coco/ |
| MediaPipe gesture range limited beyond ~2-3 m | PARTIAL: one study, 100% at 2 m, 77-100% at 3 m, 10-74% at 4.5 m (different pipeline) | ejournals.itda.ac.id/index.php/avitec/article/download/3132/pdf |
| MediaPipe aarch64 wheels | FOUND: 1.0.1 has manylinux aarch64 (older claims of none are stale) | pypi.org/project/mediapipe |
