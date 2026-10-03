#!/usr/bin/env python3
"""A/B test of two face detectors on the same frames: YuNet (OpenCV Zoo, MIT) vs SCRFD det_10g
(InsightFace buffalo_l, non-commercial research). For each guided segment (distance / camera height)
it records, per detector: detection rate, detector time, face width, and the ArcFace owner score.

Run (Jetson, Ultralytics container, camera mounted as for person_distance.py):
  python3 face_det_compare.py --owner owner/paul_arcface.npz --stream-port 8090
"""
import argparse
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
import onnxruntime as ort
import pyrealsense2 as rs

from face_owner import FaceID

# (label, target distance in metres, extra instruction). Frames are recorded only while the measured
# distance (D436 depth at the face, or at the image centre if no face is found) is within +-BAND of the
# target; a segment ends after FRAMES_PER_SEGMENT recorded frames or SEGMENT_TIMEOUT seconds.
SEGMENTS = [("1 m", 1.0, "face the camera"), ("2 m", 2.0, "face the camera"), ("3 m", 3.0, "face the camera"),
            ("camera LOW, 1.5 m", 1.5, "camera at knee height, look at it")]
BAND = 0.2
FRAMES_PER_SEGMENT = 60
SEGMENT_TIMEOUT = 60


class SCRFD:
    """Minimal SCRFD decoder for det_10g.onnx (3 strides, 2 anchors per location, 5 landmarks)."""

    def __init__(self, path, size=640, score=0.5, nms=0.4):
        self.sess = ort.InferenceSession(path, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        self.inp = self.sess.get_inputs()[0].name
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
        outs = self.sess.run(None, {self.inp: blob})
        boxes, scores, kpss = [], [], []
        for i, s in enumerate(self.strides):
            sc, bb, kp = outs[i].reshape(-1), outs[i + 3].reshape(-1, 4) * s, outs[i + 6].reshape(-1, 10) * s
            c = self._centers(self.size // s, self.size // s, s)
            keep = np.where(sc >= self.score)[0]
            if not len(keep):
                continue
            b = np.hstack([c[keep] - bb[keep, :2], c[keep] + bb[keep, 2:]])
            k = (c[keep][:, None, :] + kp[keep].reshape(-1, 5, 2))
            boxes.append(b); scores.append(sc[keep]); kpss.append(k)
        if not boxes:
            return []
        boxes, scores, kpss = np.vstack(boxes) / scale, np.hstack(scores), np.vstack(kpss) / scale
        xywh = [[float(x1), float(y1), float(x2 - x1), float(y2 - y1)] for x1, y1, x2, y2 in boxes]
        idx = cv2.dnn.NMSBoxes(xywh, scores.tolist(), self.score, self.nms)
        out = []
        for i in np.array(idx).flatten():
            x, y, w, h = xywh[i]
            # same row layout as YuNet: x, y, w, h, 5 landmarks (x, y), score
            out.append(np.array([x, y, w, h, *kpss[i].reshape(-1), scores[i]], np.float32))
        return out


ap = argparse.ArgumentParser()
ap.add_argument("--owner", default="owner/paul_arcface.npz")
ap.add_argument("--stream-port", type=int, default=8090)
args = ap.parse_args()

fid = FaceID("models", model="arcface")
fid.load_owner(args.owner)
scrfd = SCRFD("models/det_10g.onnx")

latest = [None]


class H(BaseHTTPRequestHandler):
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
                time.sleep(0.05)
        except (BrokenPipeError, ConnectionResetError):
            pass


threading.Thread(target=ThreadingHTTPServer(("0.0.0.0", args.stream_port), H).serve_forever, daemon=True).start()

cfg = rs.config()
cfg.enable_stream(rs.stream.color, 848, 480, rs.format.bgr8, 30)
cfg.enable_stream(rs.stream.depth, 848, 480, rs.format.z16, 30)
pipe = rs.pipeline()
prof = pipe.start(cfg)
depth_scale = prof.get_device().first_depth_sensor().get_depth_scale()
align = rs.align(rs.stream.color)


def grab():
    fs = align.process(pipe.wait_for_frames())
    img = np.asanyarray(fs.get_color_frame().get_data())
    depth = np.asanyarray(fs.get_depth_frame().get_data()).astype(np.float32) * depth_scale
    return img, depth


def distance_at(depth, face):
    if face is not None:
        x, y, w, h = [int(v) for v in face[:4]]
        patch = depth[max(y + h // 4, 0):y + 3 * h // 4, max(x + w // 4, 0):x + 3 * w // 4]
    else:
        H, W = depth.shape
        patch = depth[H // 3:2 * H // 3, W // 3:2 * W // 3]
    v = patch[patch > 0]
    return float(np.median(v)) if v.size > 20 else None


# warm-up so the first segment's timing is not dominated by CUDA start-up
img0, _ = grab()
for _ in range(5):
    scrfd.detect(img0); fid.faces(img0)

results = {}
try:
    for label, target, extra in SEGMENTS:
        rec = {"yunet": [], "scrfd": [], "dist": []}
        t_seg = time.time()
        while len(rec["dist"]) < FRAMES_PER_SEGMENT and time.time() - t_seg < SEGMENT_TIMEOUT:
            img, depth = grab()
            view = img.copy()
            row = {}
            for name, color, detect in (("yunet", (0, 255, 0), fid.faces), ("scrfd", (255, 128, 0), scrfd.detect)):
                t = time.perf_counter()
                faces = detect(img)
                ms = (time.perf_counter() - t) * 1000
                f = max(faces, key=lambda r: r[2] * r[3]) if len(faces) else None
                row[name] = (f, ms)
            face_for_dist = row["scrfd"][0] if row["scrfd"][0] is not None else row["yunet"][0]
            dist = distance_at(depth, face_for_dist)
            in_band = dist is not None and abs(dist - target) <= BAND
            for name, color in (("yunet", (0, 255, 0)), ("scrfd", (255, 128, 0))):
                f, ms = row[name]
                score = fid.similarity(fid.embed(img, f)) if f is not None else None
                if in_band:
                    rec[name].append((f is not None, ms, int(f[2]) if f is not None else 0, score))
                if f is not None:
                    x, y, w, h = [int(v) for v in f[:4]]
                    cv2.rectangle(view, (x, y), (x + w, y + h), color, 2)
                    cv2.putText(view, f"{name} {score:.2f}", (x, y - 8 if name == "yunet" else y + h + 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            if in_band:
                rec["dist"].append(dist)
            # guidance
            if dist is None:
                msg, col = "stand in front of the camera", (0, 165, 255)
            elif in_band:
                msg, col = f"HOLD - recording {len(rec['dist'])}/{FRAMES_PER_SEGMENT}", (0, 255, 0)
            elif dist < target:
                msg, col = f"step BACK {target - dist:.1f} m", (0, 165, 255)
            else:
                msg, col = f"step FORWARD {dist - target:.1f} m", (0, 165, 255)
            cv2.rectangle(view, (0, 0), (view.shape[1], 80), (0, 0, 0), -1)
            cv2.putText(view, f"Target {label}: {extra}", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            now_txt = f"you: {dist:.2f} m" if dist is not None else "you: -"
            cv2.putText(view, f"{now_txt}   {msg}", (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.85, col, 2)
            cv2.putText(view, "green = YuNet   blue = SCRFD", (10, 470), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            ok, jpg = cv2.imencode(".jpg", view, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                latest[0] = jpg.tobytes()
        results[label] = rec
        md = f"{np.median(rec['dist']):.2f} m" if rec["dist"] else "-"
        print(f"done: {label} ({len(rec['dist'])} frames in band, median distance {md})", flush=True)
        # short pause with a message before the next segment
        t_pause = time.time()
        while time.time() - t_pause < 3:
            img, _ = grab()
            view = img.copy()
            cv2.rectangle(view, (0, 0), (view.shape[1], 80), (0, 0, 0), -1)
            cv2.putText(view, f"{label} done - next segment in {3 - (time.time() - t_pause):.0f} s", (10, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            ok, jpg = cv2.imencode(".jpg", view, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                latest[0] = jpg.tobytes()
finally:
    pipe.stop()

print("\nsegment | detector | found % | detector ms (median) | face px (median) | ArcFace score median / min")
for label, rec in results.items():
    if not rec["dist"]:
        print(f"{label:28s} | no frames recorded in the distance band")
        continue
    for name in ("yunet", "scrfd"):
        r = rec[name]
        found = [x for x in r if x[0]]
        rate = 100 * len(found) / max(len(r), 1)
        ms = np.median([x[1] for x in r])
        px = np.median([x[2] for x in found]) if found else 0
        sc = [x[3] for x in found]
        scs = f"{np.median(sc):.2f} / {min(sc):.2f}" if sc else "-"
        print(f"{label[:28]:28s} | {name:5s} | {rate:5.0f}% | {ms:6.1f} | {px:5.0f} | {scs}")
