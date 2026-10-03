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
SFACE = "face_recognition_sface_2021dec.onnx"      # OpenCV Zoo, Apache-2.0, 128-d
ARCFACE = "w600k_r50.onnx"                          # InsightFace buffalo_l, ArcFace R50, 512-d, non-commercial research only
# Starting thresholds (cosine): SFace 0.363 is OpenCV's published value; ArcFace 0.40 is a starting
# point to be calibrated on our own owner / other-person logs.
THRESHOLD = {"sface": 0.363, "arcface": 0.40}
# Standard 112x112 ArcFace landmark template (left eye, right eye, nose, left mouth, right mouth in image coordinates).
ARC_TEMPLATE = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366],
                         [41.5493, 92.3655], [70.7299, 92.2041]], dtype=np.float32)


class FaceID:
    def __init__(self, model_dir="models", score=0.7, model="sface"):
        self.model = model
        self.threshold = THRESHOLD[model]
        self.det = cv2.FaceDetectorYN.create(os.path.join(model_dir, YUNET), "", (320, 320), score, 0.3, 5000)
        if model == "sface":
            self.rec = cv2.FaceRecognizerSF.create(os.path.join(model_dir, SFACE), "")
        else:
            import onnxruntime as ort
            self.sess = ort.InferenceSession(os.path.join(model_dir, ARCFACE),
                                             providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
            self.inp = self.sess.get_inputs()[0].name
        self.owner_name = None
        self.owner = None  # unit-norm mean embedding

    def faces(self, img):
        h, w = img.shape[:2]
        self.det.setInputSize((w, h))
        _, faces = self.det.detect(img)
        return [] if faces is None else list(faces)

    def embed(self, img, face):
        if self.model == "sface":
            aligned = self.rec.alignCrop(img, face)
            f = self.rec.feature(aligned).flatten().astype(np.float32)
        else:
            # YuNet landmarks: right eye, left eye, nose, right mouth, left mouth of the person,
            # i.e. image-left eye first, matching the ArcFace template order.
            lm = np.array(face[4:14], dtype=np.float32).reshape(5, 2)
            M, _ = cv2.estimateAffinePartial2D(lm, ARC_TEMPLATE, method=cv2.LMEDS)
            crop = cv2.warpAffine(img, M, (112, 112), borderValue=0.0)
            blob = cv2.dnn.blobFromImage(crop, 1.0 / 127.5, (112, 112), (127.5, 127.5, 127.5), swapRB=True)
            f = self.sess.run(None, {self.inp: blob})[0].flatten().astype(np.float32)
        return f / (np.linalg.norm(f) + 1e-9)

    def load_owner(self, path):
        d = np.load(path)
        saved_model = str(d["model"]) if "model" in d.files else "sface"
        assert saved_model == self.model, f"{path} was enrolled with {saved_model}, not {self.model}"
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
            out.append((f, sim, sim >= self.threshold))
        return out


PHASES = [  # (up to sample n, instruction shown on screen)
    (10, "0.5-1 m: face the camera; change angle a little LEFT / RIGHT between shots"),
    (20, "0.5-1 m: look slightly UP / DOWN between shots; change expression"),
    (30, "STEP BACK to 1.5-2 m: face the camera; a little left / right between shots"),
    (40, "Camera LOW (knee height), 1-1.5 m: look at it; a little left / right between shots"),
]


# One direction per shot (40 shots). The phase hint says where to stand; this says what to do for the next shot.
_POSES = ["LOOK STRAIGHT", "turn head a bit LEFT  <-", "turn head a bit RIGHT  ->", "LOOK STRAIGHT",
          "turn head more LEFT  <<-", "turn head more RIGHT  ->>", "tilt head LEFT", "tilt head RIGHT",
          "LOOK STRAIGHT, smile", "LOOK STRAIGHT, neutral"]
_UPDOWN = ["chin a bit UP  ^", "chin a bit DOWN  v", "LOOK STRAIGHT", "UP and LEFT", "UP and RIGHT",
           "DOWN and LEFT", "DOWN and RIGHT", "smile", "eyes half closed", "LOOK STRAIGHT"]
DIRECTIONS = _POSES + _UPDOWN + _POSES + _POSES


def direction(n):
    return DIRECTIONS[n] if n < len(DIRECTIONS) else "LOOK STRAIGHT"


def hint(n):
    for upto, text in PHASES:
        if n < upto:
            return text
    return PHASES[-1][1]


def enroll(args):
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    import pyrealsense2 as rs

    fid = FaceID(args.models, model=args.model)
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
    samples = []
    t0 = time.time()
    countdown_start = time.time()
    flash_until, flash_text = 0.0, ""
    print(f"enrolling {args.name} with {args.model}: {args.samples} shots, {args.countdown:.0f} s countdown each", flush=True)
    try:
        while len(samples) < args.samples and time.time() - t0 < args.timeout:
            img = np.asanyarray(pipe.wait_for_frames().get_color_frame().get_data())
            faces = fid.faces(img)
            view = img.copy()
            f = max(faces, key=lambda r: r[2] * r[3]) if faces else None  # largest face = the person in front
            if f is not None:
                x, y, w, h = [int(v) for v in f[:4]]
                cv2.rectangle(view, (x, y), (x + w, y + h), (0, 255, 0) if w >= args.min_face else (0, 165, 255), 2)
            now = time.time()
            remaining = args.countdown - (now - countdown_start)
            if remaining <= 0:
                if f is not None and f[2] >= args.min_face:
                    samples.append(fid.embed(img, f))
                    flash_text = f"CAPTURED #{len(samples)}"
                    print(f"  captured {len(samples)}/{args.samples} (score {f[14]:.2f}, face {int(f[2])}px) "
                          f"next: {direction(len(samples))} | {hint(len(samples))}", flush=True)
                else:
                    flash_text = "no face / too far - retry"
                flash_until = now + 1.0
                countdown_start = now + 1.0  # next countdown starts after the flash
            if now < flash_until:
                cv2.putText(view, flash_text, (150, 260), cv2.FONT_HERSHEY_SIMPLEX, 1.6,
                            (0, 255, 0) if flash_text.startswith("CAPTURED") else (0, 0, 255), 4)
            elif remaining > 0:
                cv2.putText(view, str(int(np.ceil(remaining))), (390, 300), cv2.FONT_HERSHEY_SIMPLEX, 4,
                            (255, 255, 255), 8)
                txt = f"#{len(samples) + 1}: {direction(len(samples))}"
                (tw, _), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 1.1, 3)
                cv2.rectangle(view, (0, 380), (view.shape[1], 430), (0, 0, 0), -1)
                cv2.putText(view, txt, (max((view.shape[1] - tw) // 2, 5), 418), cv2.FONT_HERSHEY_SIMPLEX, 1.1,
                            (0, 255, 255), 3)
            cv2.putText(view, f"{args.name}: {len(samples)}/{args.samples}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(view, hint(len(samples)), (10, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
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
    np.savez(args.owner_file, name=args.name, model=args.model, mean=mean, samples=E,
             created=time.strftime("%Y-%m-%d %H:%M"))
    print(f"saved {len(samples)} embeddings for {args.name} to {args.owner_file}; similarity of each sample to the "
          f"mean: min {self_sim.min():.2f} median {np.median(self_sim):.2f} (threshold {fid.threshold})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["enroll"])
    ap.add_argument("--name", default="Paul")
    ap.add_argument("--models", default="models")
    ap.add_argument("--model", choices=["sface", "arcface"], default="sface")
    ap.add_argument("--owner-file", default="owner/paul.npz")
    ap.add_argument("--samples", type=int, default=40)
    ap.add_argument("--countdown", type=float, default=3.0, help="seconds counted down before each shot")
    ap.add_argument("--min-face", type=int, default=40, help="minimum face width in pixels (~1.7 m at 848x480)")
    ap.add_argument("--every", type=float, default=0.7, help="seconds between samples")
    ap.add_argument("--timeout", type=float, default=420)
    ap.add_argument("--stream-port", type=int, default=0)
    enroll(ap.parse_args())
