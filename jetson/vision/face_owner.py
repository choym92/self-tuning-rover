#!/usr/bin/env python3
"""Owner face recognition: face detector (SCRFD by default, YuNet as fallback) + ArcFace R50 embedding.

Privacy: only the owner's embeddings (512 numbers per sample) are stored, in an owner file on the
Jetson (enrolled with face_enroll_guided.py). No face images are written to disk. Faces of other
people are compared in memory and discarded.

Models (in models/, not in the repository):
  det_10g.onnx, w600k_r50.onnx    InsightFace buffalo_l, non-commercial research only
  face_detection_yunet_2023mar    OpenCV Zoo, MIT
  det_10g.fp16.engine, w600k_r50.fp16.engine   TensorRT FP16 builds of the two ONNX files (backend="trt"):
    trtexec --onnx=models/det_10g.onnx --fp16 --shapes=input.1:1x3x640x640 --saveEngine=models/det_10g.fp16.engine
    trtexec --onnx=models/w600k_r50.onnx --fp16 --shapes=input.1:1x3x112x112 --saveEngine=models/w600k_r50.fp16.engine

Library use (person_distance.py --owner owner/paul_guided.npz):
  fid = FaceID("models", detector="scrfd"); fid.load_owner("owner/paul_guided.npz"); fid.match(bgr_image)
"""
import os

import cv2
import numpy as np

YUNET = "face_detection_yunet_2023mar.onnx"
ARCFACE = "w600k_r50.onnx"                          # InsightFace buffalo_l, ArcFace R50, 512-d, non-commercial research only
# ArcFace cosine threshold: owner vs brother measured 0.74 vs 0.24 (median), 0.45 vs 0.35 (worst case),
# see docs/verify.md. Recalibrate when more people are tested.
THRESHOLD = 0.40
# Standard 112x112 ArcFace landmark template (left eye, right eye, nose, left mouth, right mouth in image coordinates).
ARC_TEMPLATE = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366],
                         [41.5493, 92.3655], [70.7299, 92.2041]], dtype=np.float32)


SCRFD_FILE = "det_10g.onnx"  # InsightFace buffalo_l face detector, non-commercial research only
ENGINE = {SCRFD_FILE: "det_10g.fp16.engine", ARCFACE: "w600k_r50.fp16.engine"}


def runner(path, backend):
    """Callable blob -> list of outputs, with onnxruntime (CUDA) or the TensorRT engine next to the ONNX file."""
    if backend == "trt":
        from trt_engine import TRTEngine
        return TRTEngine(os.path.join(os.path.dirname(path), ENGINE[os.path.basename(path)]))
    import onnxruntime as ort
    sess = ort.InferenceSession(path, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    inp = sess.get_inputs()[0].name
    return lambda blob: sess.run(None, {inp: blob})


class SCRFD:
    """Minimal SCRFD decoder for det_10g.onnx (3 strides, 2 anchors per location, 5 landmarks).
    Returns rows in YuNet's layout: x, y, w, h, 5 landmarks (x, y), score."""

    def __init__(self, path, size=640, score=0.5, nms=0.4, backend="ort"):
        self.run = runner(path, backend)
        self.size, self.score, self.nms = size, score, nms
        self.strides, self.na = (8, 16, 32), 2
        self.centers = {}

    def _centers(self, h, w, s):
        key = (h, w, s)
        if key not in self.centers:
            yy, xx = np.mgrid[:h, :w]
            c = (np.stack([xx, yy], -1).reshape(-1, 2) * s).astype(np.float32)
            self.centers[key] = np.repeat(c, self.na, axis=0)
        return self.centers[key]

    def detect(self, img):
        H, W = img.shape[:2]
        scale = self.size / max(H, W)
        nh, nw = int(H * scale), int(W * scale)
        canvas = np.zeros((self.size, self.size, 3), np.uint8)
        canvas[:nh, :nw] = cv2.resize(img, (nw, nh))
        blob = cv2.dnn.blobFromImage(canvas, 1.0 / 128, (self.size, self.size), (127.5, 127.5, 127.5), swapRB=True)
        outs = self.run(blob)
        boxes, scores, kpss = [], [], []
        for i, s in enumerate(self.strides):
            sc, bb, kp = outs[i].reshape(-1), outs[i + 3].reshape(-1, 4) * s, outs[i + 6].reshape(-1, 10) * s
            c = self._centers(self.size // s, self.size // s, s)
            keep = np.where(sc >= self.score)[0]
            if not len(keep):
                continue
            boxes.append(np.hstack([c[keep] - bb[keep, :2], c[keep] + bb[keep, 2:]]))
            scores.append(sc[keep])
            kpss.append(c[keep][:, None, :] + kp[keep].reshape(-1, 5, 2))
        if not boxes:
            return []
        boxes, scores, kpss = np.vstack(boxes) / scale, np.hstack(scores), np.vstack(kpss) / scale
        xywh = [[float(x1), float(y1), float(x2 - x1), float(y2 - y1)] for x1, y1, x2, y2 in boxes]
        idx = cv2.dnn.NMSBoxes(xywh, scores.tolist(), self.score, self.nms)
        return [np.array([*xywh[i], *kpss[i].reshape(-1), scores[i]], np.float32) for i in np.array(idx).flatten()]


class FaceID:
    def __init__(self, model_dir="models", score=0.7, detector="scrfd", share_from=None, backend="ort"):
        """detector: "scrfd" (InsightFace, GPU, default) or "yunet" (OpenCV Zoo, MIT, CPU).
        share_from: another FaceID whose ArcFace session to reuse (saves GPU memory).
        backend: "ort" (onnxruntime CUDA) or "trt" (TensorRT FP16 engines) for SCRFD and ArcFace."""
        self.detector = detector
        self.threshold = THRESHOLD
        if detector == "scrfd":
            self.scrfd = SCRFD(os.path.join(model_dir, SCRFD_FILE), score=0.5, backend=backend)
        else:
            self.det = cv2.FaceDetectorYN.create(os.path.join(model_dir, YUNET), "", (320, 320), score, 0.3, 5000)
        if share_from is not None:
            self.arcface = share_from.arcface
            self.owner_name, self.owner = None, None
            return
        self.arcface = runner(os.path.join(model_dir, ARCFACE), backend)
        self.owner_name = None
        self.owner = None  # unit-norm mean embedding

    def faces(self, img):
        if self.detector == "scrfd":
            return self.scrfd.detect(img)
        h, w = img.shape[:2]
        self.det.setInputSize((w, h))
        _, faces = self.det.detect(img)
        return [] if faces is None else list(faces)

    def embed(self, img, face):
        # Landmarks (both detectors): image-left eye, image-right eye, nose, image-left mouth corner,
        # image-right mouth corner, matching the ArcFace template order.
        lm = np.array(face[4:14], dtype=np.float32).reshape(5, 2)
        M, _ = cv2.estimateAffinePartial2D(lm, ARC_TEMPLATE, method=cv2.LMEDS)
        if M is None:  # degenerate landmarks (e.g. a face cut off at the image edge)
            return None
        crop = cv2.warpAffine(img, M, (112, 112), borderValue=0.0)
        blob = cv2.dnn.blobFromImage(crop, 1.0 / 127.5, (112, 112), (127.5, 127.5, 127.5), swapRB=True)
        f = self.arcface(blob)[0].flatten().astype(np.float32)
        return f / (np.linalg.norm(f) + 1e-9)

    def load_owner(self, path):
        d = np.load(path)
        assert "model" in d.files and str(d["model"]) == "arcface", f"{path} is not an ArcFace enrollment"
        self.owner_name = str(d["name"])
        key = f"samples_{self.detector}"  # guided enrollment stores one gallery per face detector
        if key not in d.files:
            raise SystemExit(f"{path} has no {key} gallery; enroll with face_enroll_guided.py")
        S = d[key].astype(np.float32)
        mean = S.mean(0)
        self.owner = mean / np.linalg.norm(mean)
        self.owner_samples = S

    def similarity(self, e):
        """Score = max(similarity to the mean, mean of the 3 closest enrolled samples).
        The second term helps at angles the mean represents poorly (side view, camera below)."""
        if self.owner is None:
            return 0.0
        top3 = np.sort(self.owner_samples @ e)[-3:].mean() if len(self.owner_samples) else 0.0
        return float(max(np.dot(e, self.owner), top3))

    def match(self, img):
        """Return [(face_row, similarity, is_owner)] for every face found."""
        out = []
        for f in self.faces(img):
            e = self.embed(img, f)
            if e is None:
                continue
            sim = self.similarity(e)
            out.append((f, sim, sim >= self.threshold))
        return out
