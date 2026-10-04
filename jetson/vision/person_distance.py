#!/usr/bin/env python3
"""Live person detection + tracking + distance + bearing with the D436 and YOLO26s (TensorRT FP16).

Boxes are tracked with ByteTrack (Ultralytics), so each person keeps an ID (#n) across frames.
With --owner, the owner is bound to a track ID: the owner's face must match on the same track in
OWNER_HITS consecutive face checks; the binding is released when the track is gone for LOST_RELEASE s
or when REVERIFY_MISSES face checks find a non-owner face on that track.

For every box: distance = median of valid depth pixels in the central 40% of the box
(aligned to color), bearing = horizontal angle from the color camera's optical axis
(negative = left of center). Prints a line per second and times every stage. --out saves one
annotated frame (off by default: it contains faces).

Run (Jetson), mounting our RSUSB librealsense build and the USB devices into the container:
  docker run --rm --runtime nvidia --ipc host -p 127.0.0.1:8090:8090 \
    -v /home/paulcho/yolo:/work -w /work \
    -v /home/paulcho/src/librealsense/build/Release:/rs:ro -e PYTHONPATH=/rs:/work/pylib -e LD_LIBRARY_PATH=/rs \
    -v /dev/bus/usb:/dev/bus/usb --device-cgroup-rule='c 189:* rmw' \
    ultralytics/ultralytics:latest-jetson-jetpack6 python3 person_distance.py --engine yolo26s-pose.engine \
    --owner owner/paul_guided.npz --stream-port 8090 --seconds 600
The view port is published on the Jetson's localhost only; on the Mac use an SSH tunnel
(ssh -N -L 8090:127.0.0.1:8090 paulcho@192.168.1.234) and open http://localhost:8090.
"""
import argparse
import math
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
import pyrealsense2 as rs
from ultralytics import YOLO

ap = argparse.ArgumentParser()
ap.add_argument("--seconds", type=float, default=20)
ap.add_argument("--engine", default="yolo26s.engine")
ap.add_argument("--conf", type=float, default=0.1,
                help="detector threshold; low-score boxes feed ByteTrack's second association stage")
ap.add_argument("--tracker", default="bytetrack.yaml", help="Ultralytics tracker config (bytetrack.yaml, botsort.yaml)")
ap.add_argument("--out", default="", help="save one annotated frame here (contains faces; never commit it)")
ap.add_argument("--all-classes", action="store_true", help="detect all 80 COCO classes, not only person")
ap.add_argument("--owner", default="", help="owner file from face_enroll_guided.py, e.g. owner/paul_guided.npz")
ap.add_argument("--face-detector", choices=["scrfd", "yunet"], default="scrfd")
ap.add_argument("--face-every", type=int, default=3, help="run face recognition every N frames")
ap.add_argument("--stream-port", type=int, default=0,
                help="if > 0, serve a live MJPEG view (color with boxes | depth) on this port")
args = ap.parse_args()

latest_jpeg = [None]
clients = [0]  # frames are JPEG-encoded only while someone is watching
if args.stream_port:
    class Handler(BaseHTTPRequestHandler):
        timeout = 10  # drop a viewer whose connection stalls

        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path != "/stream":
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body style='margin:0;background:#111'>"
                                 b"<img src='/stream' style='width:100%'></body></html>")
                return
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            clients[0] += 1
            try:
                while True:
                    jpg = latest_jpeg[0]
                    if jpg is not None:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n")
                    time.sleep(0.04)
            except OSError:  # viewer closed the page, reset, or timed out
                pass
            finally:
                clients[0] -= 1

    # 0.0.0.0 inside the container; docker run -p 127.0.0.1:... keeps it off the LAN
    server = ThreadingHTTPServer(("0.0.0.0", args.stream_port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"live view on port {args.stream_port}", flush=True)

fid = None
if args.owner:
    from face_owner import FaceID
    fid = FaceID("models", detector=args.face_detector)
    fid.load_owner(args.owner)
    print(f"face detector {args.face_detector}, ArcFace threshold {fid.threshold}", flush=True)
    print(f"owner: {fid.owner_name} ({len(fid.owner_samples)} samples)", flush=True)
OWNER_HITS = 2         # consecutive face checks matching the owner on one track before it is bound
REVERIFY_MISSES = 3    # face checks finding a non-owner face on the owner track before it is released
LOST_RELEASE = 2.0     # seconds the owner track may be missing before it is released
owner_tid, owner_sim, owner_last, owner_misses = None, 0.0, 0.0, 0
hits = {}              # track id -> consecutive owner-face matches
face_scores = []  # (x-centre px, similarity) of every face in the last face check, for the log

POSE = "pose" in args.engine  # e.g. yolo26s-pose.engine: person boxes + 17 COCO keypoints
model = YOLO(args.engine, task="pose" if POSE else "detect")
# COCO keypoints: 0 nose, 1-2 eyes, 3-4 ears, 5-6 shoulders, 7-8 elbows, 9-10 wrists, 11-12 hips, 13-14 knees,
# 15-16 ankles (odd = person's left, even = person's right)
SKELETON = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12), (11, 13), (13, 15),
            (12, 14), (14, 16), (0, 1), (0, 2), (1, 3), (2, 4)]
KP_CONF = 0.5
PERSON = [k for k, v in model.names.items() if v == "person"][0] if hasattr(model, "names") and model.names else 0

W, H, FPS = 848, 480, 30
cfg = rs.config()
cfg.enable_stream(rs.stream.depth, W, H, rs.format.z16, FPS)
cfg.enable_stream(rs.stream.color, W, H, rs.format.bgr8, FPS)
pipe = rs.pipeline()
prof = pipe.start(cfg)
scale = prof.get_device().first_depth_sensor().get_depth_scale()
intr = prof.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
align = rs.align(rs.stream.color)
print(f"color intrinsics fx {intr.fx:.1f} cx {intr.ppx:.1f}; depth scale {scale}")

timing = {k: deque(maxlen=3000) for k in ("wait", "align", "yolo", "post")}
frames, timeouts = 0, 0
t0 = time.time()
next_print = t0 + 1
saved = False
try:
    while time.time() - t0 < args.seconds:
        a = time.perf_counter()
        try:
            fs = pipe.wait_for_frames(timeout_ms=2000)
        except RuntimeError:  # a dropped USB transfer should not end the run
            timeouts += 1
            continue
        b = time.perf_counter()
        fs = align.process(fs)
        d_frame, c_frame = fs.get_depth_frame(), fs.get_color_frame()
        if not d_frame or not c_frame:
            continue
        depth = np.asanyarray(d_frame.get_data()).astype(np.float32) * scale
        img = np.asanyarray(c_frame.get_data())
        c = time.perf_counter()
        res = model.track(img, persist=True, tracker=args.tracker, imgsz=640, conf=args.conf,
                          classes=None if args.all_classes else [PERSON], device=0, verbose=False)[0]
        d = time.perf_counter()

        people = []
        # With no active track Ultralytics leaves the raw conf>=0.1 detections in res; show tracked boxes only.
        ids = res.boxes.id.int().cpu().tolist() if res.boxes.id is not None else []
        kps = res.keypoints.data.cpu().numpy() if POSE else [None] * len(ids)  # (x, y, confidence) per keypoint
        for (x1, y1, x2, y2), conf, cls, tid, kp in zip(res.boxes.xyxy.cpu().numpy(), res.boxes.conf.cpu().numpy(),
                                                        res.boxes.cls.cpu().numpy(), ids, kps):
            w, h = x2 - x1, y2 - y1
            cx1, cx2 = int(x1 + 0.3 * w), int(x2 - 0.3 * w)
            cy1, cy2 = int(y1 + 0.3 * h), int(y2 - 0.3 * h)
            patch = depth[max(cy1, 0):max(cy2, 1), max(cx1, 0):max(cx2, 1)]
            valid = patch[patch > 0]
            dist = float(np.median(valid)) if valid.size > 20 else float("nan")
            u = (x1 + x2) / 2
            bearing = math.degrees(math.atan2(u - intr.ppx, intr.fx))
            people.append((dist, bearing, float(conf), (int(x1), int(y1), int(x2), int(y2)),
                           res.names[int(cls)], tid, kp))
        now = time.time()
        if fid is not None and frames % args.face_every == 0:
            matches = fid.match(img)
            face_scores = [(int(f[0] + f[2] / 2), round(sim, 2)) for f, sim, _ in matches]

            def track_of(f):
                # the smallest person box that contains the face centre (the nearest of overlapping people)
                fx, fy = f[0] + f[2] / 2, f[1] + f[3] / 2
                inside = [p for p in people if p[4] == "person" and p[5] is not None
                          and p[3][0] <= fx <= p[3][2] and p[3][1] <= fy <= p[3][3]]
                return min(inside, key=lambda p: (p[3][2] - p[3][0]) * (p[3][3] - p[3][1]))[5] if inside else None

            # Only one owner exists: only the best-scoring face can be the owner, and only above the threshold.
            best = max(matches, key=lambda m: m[1], default=None)
            t = track_of(best[0]) if best is not None and best[2] else None
            hits = {t: hits.get(t, 0) + 1} if t is not None else {}
            if t is not None and (t == owner_tid or hits[t] >= OWNER_HITS):
                owner_tid, owner_sim, owner_last, owner_misses = t, best[1], now, 0
            elif owner_tid is not None and any(track_of(f) == owner_tid for f, _, _ in matches):
                owner_misses += 1  # a face on the owner track that is not the owner
                if owner_misses >= REVERIFY_MISSES:
                    owner_tid = None
        if owner_tid is not None:
            if any(p[5] == owner_tid for p in people):
                owner_last = now
            elif now - owner_last > LOST_RELEASE:
                owner_tid = None
        people = [p[:4] + (f"{fid.owner_name} (owner) {owner_sim:.2f}",) + p[5:]
                  if owner_tid is not None and p[5] == owner_tid else p for p in people]
        e = time.perf_counter()

        if args.stream_port and clients[0]:
            view = img.copy()
            for dist, bearing, conf, (x1, y1, x2, y2), name, tid, kp in people:
                color = (0, 215, 255) if "(owner)" in name else (0, 255, 0)
                cv2.rectangle(view, (x1, y1), (x2, y2), color, 3 if "(owner)" in name else 2)
                if kp is not None:
                    for i, j in SKELETON:
                        if kp[i, 2] > KP_CONF and kp[j, 2] > KP_CONF:
                            cv2.line(view, (int(kp[i, 0]), int(kp[i, 1])), (int(kp[j, 0]), int(kp[j, 1])), (255, 200, 0), 2)
                    for k, (x, y, c) in enumerate(kp):
                        if c > KP_CONF:  # wrists larger and magenta: gestures will use them
                            cv2.circle(view, (int(x), int(y)), 7 if k in (9, 10) else 3,
                                       (255, 0, 255) if k in (9, 10) else (255, 255, 255), -1)
                cv2.putText(view, f"#{tid} {name} {conf:.0%} {dist:.2f} m {bearing:+.0f} deg", (x1, max(y1 - 8, 15)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            dvis = cv2.applyColorMap(cv2.convertScaleAbs(np.clip(depth, 0, 4.0), alpha=255 / 4.0), cv2.COLORMAP_TURBO)
            dvis[depth == 0] = 0
            fps_now = frames / max(time.time() - t0, 1e-6)
            cv2.putText(view, f"{fps_now:.1f} fps", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            ok, jpg = cv2.imencode(".jpg", np.hstack([view, dvis]), [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                latest_jpeg[0] = jpg.tobytes()

        timing["wait"].append((b - a) * 1000)
        timing["align"].append((c - b) * 1000)
        timing["yolo"].append((d - c) * 1000)
        timing["post"].append((e - d) * 1000)
        frames += 1

        if time.time() >= next_print:
            desc = ", ".join(f"#{p[5]} {p[4]} {p[0]:.2f} m @ {p[1]:+.0f} deg ({p[2]:.2f})" for p in sorted(people, key=lambda q: q[0])) or "nothing"
            extra = f"  faces(x px: score) {face_scores}" if fid is not None else ""
            print(f"t={time.time() - t0:5.1f}s  {len(people)} object(s): {desc}{extra}", flush=True)
            next_print = time.time() + 1

        if args.out and people and not saved and time.time() - t0 > 2:
            for dist, bearing, conf, (x1, y1, x2, y2), name, tid, kp in people:
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(img, f"{dist:.2f} m {bearing:+.0f} deg", (x1, max(y1 - 8, 15)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.imwrite(args.out, img)
            saved = True
finally:
    pipe.stop()

el = time.time() - t0
print(f"\n{frames} frames in {el:.1f} s = {frames / el:.1f} fps end-to-end; frame timeouts {timeouts}")
for k, v in timing.items():
    if not v:
        continue
    v = np.array(v)
    print(f"  {k:5s} median {np.median(v):6.2f} ms  p90 {np.percentile(v, 90):6.2f} ms")
if args.out:
    print(f"annotated frame: {args.out if saved else 'none (no person seen after 2 s)'}")
