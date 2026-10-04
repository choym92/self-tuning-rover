#!/usr/bin/env python3
"""Guided owner enrollment covering the situations the robot will see.

For every shot, both face detectors (YuNet and SCRFD) look at the same frame; each one's landmarks
are used to align the face and an ArcFace R50 embedding is stored per detector. So one session
produces a gallery for YuNet and a gallery for SCRFD.

Distance is measured with the D436 depth at the face; the 3-second countdown runs only while the
owner is within +-0.25 m of the target. Camera height cannot be measured, so each segment names it.
Only embeddings and per-shot metadata are saved (no images).

Run (Jetson, Ultralytics container, camera mounted as for person_distance.py):
  python3 face_enroll_guided.py --name Paul --out owner/paul_guided.npz --stream-port 8090
"""
import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
import pyrealsense2 as rs

from face_owner import FaceID

STRAIGHT, LEFT, RIGHT = "LOOK STRAIGHT", "turn head LEFT ~30 deg  <-", "turn head RIGHT ~30 deg  ->"
PROF_L, PROF_R = "LEFT side profile (turn ~70 deg)  <<-", "RIGHT side profile (turn ~70 deg)  ->>"
UP, DOWN, LOOK_DOWN = "chin UP a bit  ^", "chin DOWN a bit  v", "look DOWN at the camera"
# (segment title shown on screen, camera position, target distance m, list of poses)
SEGMENTS = [
    ("A", "camera on the DESK", 1.0, [STRAIGHT, LEFT, RIGHT, PROF_L, PROF_R, UP, DOWN]),
    ("B", "camera on the DESK", 2.0, [STRAIGHT, LEFT, RIGHT, PROF_L, PROF_R]),
    ("C", "camera on the DESK", 3.0, [STRAIGHT, LEFT, RIGHT]),
    ("D", "camera at KNEE height (~50 cm)", 1.5, [STRAIGHT, LEFT, RIGHT, PROF_L, PROF_R]),
    ("E", "camera on the FLOOR, tilted up", 1.5, [LOOK_DOWN, LEFT, RIGHT, STRAIGHT]),
    ("F", "camera on the FLOOR, tilted up", 2.5, [LOOK_DOWN, LEFT, RIGHT, STRAIGHT]),
]
# Close-range plan, appended to an existing gallery with --plan close --append.
CLOSE_SEGMENTS = [
    ("G", "camera on the DESK", 0.5, [STRAIGHT, LEFT, RIGHT, UP, DOWN, PROF_L, PROF_R]),
    ("H", "camera on the DESK", 0.8, [STRAIGHT, LEFT, RIGHT, UP, DOWN]),
]
BAND = 0.25
COUNTDOWN = 3.0
SHOT_TIMEOUT = 25.0  # seconds per shot before it is skipped (e.g. no face found at a profile)

ap = argparse.ArgumentParser()
ap.add_argument("--name", default="Paul")
ap.add_argument("--out", default="owner/paul_guided.npz")
ap.add_argument("--stream-port", type=int, default=8090)
ap.add_argument("--plan", choices=["full", "close"], default="full")
ap.add_argument("--append", action="store_true", help="add the new shots to the existing gallery in --out")
args = ap.parse_args()
if args.plan == "close":
    SEGMENTS = CLOSE_SEGMENTS
    BAND = 0.15
prev = np.load(args.out) if args.append else None  # fail now, not after the session, if the file is missing

fid_y = FaceID("models", detector="yunet")
fid_s = FaceID("models", detector="scrfd", share_from=fid_y)

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
    return (np.asanyarray(fs.get_color_frame().get_data()),
            np.asanyarray(fs.get_depth_frame().get_data()).astype(np.float32) * depth_scale)


def largest(faces):
    return max(faces, key=lambda r: r[2] * r[3]) if len(faces) else None


def distance_at(depth, face):
    if face is not None:
        x, y, w, h = [int(v) for v in face[:4]]
        patch = depth[max(y + h // 4, 0):y + 3 * h // 4, max(x + w // 4, 0):x + 3 * w // 4]
    else:
        H, W = depth.shape
        patch = depth[H // 3:2 * H // 3, W // 3:2 * W // 3]
    v = patch[patch > 0]
    return float(np.median(v)) if v.size > 20 else None


def show(view, top1, top2, col2, big=None, big_col=(255, 255, 255), bottom=None):
    cv2.rectangle(view, (0, 0), (view.shape[1], 80), (0, 0, 0), -1)
    cv2.putText(view, top1, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
    cv2.putText(view, top2, (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.8, col2, 2)
    if big:
        (tw, _), _ = cv2.getTextSize(big, cv2.FONT_HERSHEY_SIMPLEX, 1.3, 4)
        cv2.putText(view, big, (max((view.shape[1] - tw) // 2, 5), 270), cv2.FONT_HERSHEY_SIMPLEX, 1.3, big_col, 4)
    if bottom:
        cv2.rectangle(view, (0, 390), (view.shape[1], 440), (0, 0, 0), -1)
        (tw, _), _ = cv2.getTextSize(bottom, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 3)
        cv2.putText(view, bottom, (max((view.shape[1] - tw) // 2, 5), 427), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 3)
    ok, jpg = cv2.imencode(".jpg", view, [cv2.IMWRITE_JPEG_QUALITY, 70])
    if ok:
        latest[0] = jpg.tobytes()


total = sum(len(s[3]) for s in SEGMENTS)
emb = {"yunet": [], "scrfd": []}
meta = []  # (segment, pose, distance, yunet_found, scrfd_found, yunet_px, scrfd_px)
shot = 0
print(f"guided enrollment of {args.name}: {total} shots", flush=True)
try:
    for seg, where, target, poses in SEGMENTS:
        # moving to a new segment: show where to put the camera, wait 8 s
        t0 = time.time()
        while time.time() - t0 < 8:
            img, _ = grab()
            show(img.copy(), f"Segment {seg}: {where}, stand at {target:.1f} m", "set up the camera and stand there",
                 (0, 165, 255), big=f"NEXT: {where}", big_col=(0, 255, 255),
                 bottom=f"starting in {8 - (time.time() - t0):.0f} s")
        for pose in poses:
            shot += 1
            countdown_start, t_shot = None, time.time()
            taken = False
            while not taken and time.time() - t_shot < SHOT_TIMEOUT:
                img, depth = grab()
                fy, fs = largest(fid_y.faces(img)), largest(fid_s.faces(img))
                dist = distance_at(depth, fs if fs is not None else fy)
                face_found = fy is not None or fs is not None
                in_band = face_found and dist is not None and abs(dist - target) <= BAND
                view = img.copy()
                for f, col in ((fy, (0, 255, 0)), (fs, (255, 128, 0))):
                    if f is not None:
                        x, y, w, h = [int(v) for v in f[:4]]
                        cv2.rectangle(view, (x, y), (x + w, y + h), col, 2)
                you = f"you {dist:.2f} m" if dist is not None else "you: -"
                if not in_band:
                    countdown_start = None
                    if dist is None:
                        msg = "stand in front of the camera"
                    elif not face_found:
                        msg = "face not found - follow the pose below"
                    elif dist < target:
                        msg = f"step BACK {target - dist:.1f} m"
                    else:
                        msg = f"step FORWARD {dist - target:.1f} m"
                    show(view, f"#{shot}/{total}  Segment {seg}: {where}, {target:.1f} m", f"{you}   {msg}",
                         (0, 165, 255), bottom=pose)
                    continue
                if countdown_start is None:
                    countdown_start = time.time()
                left = COUNTDOWN - (time.time() - countdown_start)
                if left > 0:
                    show(view, f"#{shot}/{total}  Segment {seg}: {where}, {target:.1f} m", f"{you}   HOLD the pose",
                         (0, 255, 0), big=str(int(np.ceil(left))), bottom=pose)
                    continue
                # capture: embeddings from each detector that found the face
                found = {}
                for name, fid, f in (("yunet", fid_y, fy), ("scrfd", fid_s, fs)):
                    if f is not None:
                        emb[name].append(fid.embed(img, f))
                        found[name] = int(f[2])
                meta.append((seg, pose, dist, "yunet" in found, "scrfd" in found,
                             found.get("yunet", 0), found.get("scrfd", 0)))
                tag = f"yunet {'OK' if 'yunet' in found else 'MISS'}  scrfd {'OK' if 'scrfd' in found else 'MISS'}"
                print(f"  #{shot} {seg} {pose[:24]:24s} {dist:.2f} m  {tag}", flush=True)
                t_flash = time.time()
                while time.time() - t_flash < 1.2:
                    img2, _ = grab()
                    show(img2.copy(), f"#{shot}/{total}  Segment {seg}", tag,
                         (0, 255, 0) if found else (0, 0, 255),
                         big=f"CAPTURED #{shot}" if found else "NO FACE FOUND", big_col=(0, 255, 0) if found else (0, 0, 255))
                taken = True
            if not taken:
                meta.append((seg, pose, -1.0, False, False, 0, 0))
                print(f"  #{shot} {seg} {pose[:24]:24s} skipped (not in the distance band for {SHOT_TIMEOUT:.0f} s)", flush=True)
except (KeyboardInterrupt, RuntimeError) as e:  # Ctrl-C or camera timeout: keep the shots taken so far
    print(f"stopped early ({type(e).__name__}: {e}); saving what was captured", flush=True)
finally:
    pipe.stop()

if not emb["yunet"] and not emb["scrfd"]:
    raise SystemExit("nothing captured; not saved")
save = {"name": args.name, "model": "arcface", "created": time.strftime("%Y-%m-%d %H:%M"),
        "meta_json": json.dumps(meta)}
old_counts = {}
if prev is not None:
    save["meta_json"] = json.dumps(json.loads(str(prev["meta_json"])) + meta)
    save["created"] = str(prev["created"]) + " + " + save["created"]
    for name in ("yunet", "scrfd"):
        key = f"samples_{name}"
        if key in prev.files:
            old_counts[name] = len(prev[key])
            emb[name] = list(prev[key]) + emb[name]
for name in ("yunet", "scrfd"):
    if emb[name]:
        save[f"samples_{name}"] = np.stack(emb[name])
if old_counts:
    print(f"appended to {args.out}: previous {old_counts}")
np.savez(args.out, **save)
print(f"\nsaved {args.out}: yunet {len(emb['yunet'])} embeddings, scrfd {len(emb['scrfd'])} embeddings")
print("per segment (found by yunet / scrfd out of shots):")
for seg, where, target, poses in SEGMENTS:
    rows = [m for m in meta if m[0] == seg]
    print(f"  {seg} {where:34s} {target:.1f} m: yunet {sum(m[3] for m in rows)}/{len(rows)}, "
          f"scrfd {sum(m[4] for m in rows)}/{len(rows)}")
