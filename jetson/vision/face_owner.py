#!/usr/bin/env python3
"""Owner face recognition: YuNet face detector + SFace face embedding (OpenCV Zoo models).

Privacy: only the owner's embeddings (128 numbers per sample) are stored, in --owner-file on
the Jetson. No face images are written to disk. Faces of other people are compared in memory
and discarded.

Enrollment (camera in front of the owner; follow the on-screen hints; 30 samples in four phases):
  docker run ... ultralytics/ultralytics:latest-jetson-jetpack6 \
    python3 face_owner.py enroll --name Paul --stream-port 8090

As a library (used by person_distance.py --owner owner/paul.npz):
  fid = FaceID("models"); fid.load_owner("owner/paul.npz"); fid.match(bgr_image)
"""
import argparse
import os
import time

import cv2
import numpy as np

YUNET = "face_detection_yunet_2023mar.onnx"
SFACE = "face_recognition_sface_2021dec.onnx"
# OpenCV's published SFace thresholds: cosine >= 0.363 means "same identity".
COSINE_SAME = 0.363


class FaceID:
    def __init__(self, model_dir="models", score=0.7):
        self.det = cv2.FaceDetectorYN.create(os.path.join(model_dir, YUNET), "", (320, 320), score, 0.3, 5000)
        self.rec = cv2.FaceRecognizerSF.create(os.path.join(model_dir, SFACE), "")
        self.owner_name = None
        self.owner = None  # unit-norm mean embedding

    def faces(self, img):
        h, w = img.shape[:2]
        self.det.setInputSize((w, h))
        _, faces = self.det.detect(img)
        return [] if faces is None else list(faces)

    def embed(self, img, face):
        aligned = self.rec.alignCrop(img, face)
        f = self.rec.feature(aligned).flatten().astype(np.float32)
        return f / (np.linalg.norm(f) + 1e-9)

    def load_owner(self, path):
        d = np.load(path)
        self.owner_name = str(d["name"])
        self.owner = d["mean"].astype(np.float32)
        S = d["samples"].astype(np.float32)
        self.owner_samples = S[(S @ self.owner) >= 0.4]

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
            sim = self.similarity(self.embed(img, f))
            out.append((f, sim, sim >= COSINE_SAME))
        return out


PHASES = [  # (up to sample n, instruction shown on screen)
    (8, "0.5-1 m: face the camera, then slowly turn LEFT, then RIGHT"),
    (14, "0.5-1 m: look slightly UP, then DOWN; change expression"),
    (22, "STEP BACK to 1.5-2 m: face the camera, then turn left/right"),
    (30, "Put the camera LOW (knee height), 1-1.5 m: look at it, turn left/right"),
]


def hint(n):
    for upto, text in PHASES:
        if n < upto:
            return text
    return PHASES[-1][1]


def enroll(args):
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    import pyrealsense2 as rs

    fid = FaceID(args.models)
    latest = [None]
    if args.stream_port:
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path != "/stream":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"<html><body style='margin:0;background:#111'><img src='/stream' style='width:100%'></body></html>")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()
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
    pipe = rs.pipeline()
    pipe.start(cfg)
    samples, last_take = [], 0.0
    t0 = time.time()
    print(f"enrolling {args.name}: look at the camera and slowly turn your head; target {args.samples} samples", flush=True)
    try:
        while len(samples) < args.samples and time.time() - t0 < args.timeout:
            img = np.asanyarray(pipe.wait_for_frames().get_color_frame().get_data())
            faces = fid.faces(img)
            view = img.copy()
            msg = "no face"
            if faces:
                f = max(faces, key=lambda r: r[2] * r[3])  # largest face = the person in front
                x, y, w, h = [int(v) for v in f[:4]]
                ok_size = w >= args.min_face
                cv2.rectangle(view, (x, y), (x + w, y + h), (0, 255, 0) if ok_size else (0, 165, 255), 2)
                msg = "move closer" if not ok_size else "hold still / turn slowly"
                if ok_size and time.time() - last_take >= args.every:
                    e = fid.embed(img, f)
                    # keep only samples that add variety (not near-duplicates of the last one)
                    if not samples or float(np.dot(e, samples[-1])) < 0.97:
                        samples.append(e)
                        last_take = time.time()
                        print(f"  sample {len(samples)}/{args.samples} (score {f[14]:.2f}, face {w}px) next: {hint(len(samples))}", flush=True)
            cv2.putText(view, f"{args.name}: {len(samples)}/{args.samples}  {msg}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(view, hint(len(samples)), (10, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            ok, jpg = cv2.imencode(".jpg", view, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                latest[0] = jpg.tobytes()
    finally:
        pipe.stop()

    if len(samples) < max(5, args.samples // 3):
        print(f"only {len(samples)} samples; not saved. Try again closer to the camera with more light.")
        return
    E = np.stack(samples)
    mean = E.mean(0)
    mean /= np.linalg.norm(mean)
    # Drop samples that disagree with the rest (bad crop, motion blur, too far), then recompute.
    keep = (E @ mean) >= 0.4
    if keep.sum() >= 5 and keep.sum() < len(E):
        print(f"dropping {int((~keep).sum())} outlier sample(s) with similarity < 0.4 to the mean")
        E = E[keep]
        mean = E.mean(0)
        mean /= np.linalg.norm(mean)
    self_sim = E @ mean
    os.makedirs(os.path.dirname(args.owner_file) or ".", exist_ok=True)
    np.savez(args.owner_file, name=args.name, mean=mean, samples=E, created=time.strftime("%Y-%m-%d %H:%M"))
    print(f"saved {len(samples)} embeddings for {args.name} to {args.owner_file}; similarity of each sample to the "
          f"mean: min {self_sim.min():.2f} median {np.median(self_sim):.2f} (threshold {COSINE_SAME})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["enroll"])
    ap.add_argument("--name", default="Paul")
    ap.add_argument("--models", default="models")
    ap.add_argument("--owner-file", default="owner/paul.npz")
    ap.add_argument("--samples", type=int, default=30)
    ap.add_argument("--min-face", type=int, default=40, help="minimum face width in pixels (~1.7 m at 848x480)")
    ap.add_argument("--every", type=float, default=0.7, help="seconds between samples")
    ap.add_argument("--timeout", type=float, default=240)
    ap.add_argument("--stream-port", type=int, default=0)
    enroll(ap.parse_args())
