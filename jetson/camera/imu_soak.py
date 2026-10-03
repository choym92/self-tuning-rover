#!/usr/bin/env python3
"""IMU soak test for the D436 on the Jetson (RSUSB build).

Streams depth + color (like the robot will) and the IMU at the same time for N seconds.
Records every IMU sample timestamp and every video frame number, then reports:
  - average and per-second IMU rates
  - IMU gaps: intervals longer than 2x the nominal period (missed samples)
  - video frame drops: jumps in the hardware frame counter
Writes a per-second CSV so the run can be plotted later on the Mac.

Run on the Jetson:
  PYTHONPATH=$HOME/src/librealsense/build/Release python3 imu_soak.py --seconds 600
"""
import argparse
import collections
import csv
import threading
import time

import numpy as np
import pyrealsense2 as rs

ap = argparse.ArgumentParser()
ap.add_argument("--seconds", type=float, default=600)
ap.add_argument("--gyro-hz", type=int, default=200)
ap.add_argument("--accel-hz", type=int, default=100)
ap.add_argument("--video", action=argparse.BooleanOptionalAction, default=True, help="also stream depth+color")
ap.add_argument("--csv", default="imu_soak_per_second.csv")
args = ap.parse_args()

ctx = rs.context()
dev = ctx.query_devices()[0]
motion = next(s for s in dev.query_sensors() if s.is_motion_sensor())
profiles = [p for p in motion.get_stream_profiles()
            if (p.stream_type() == rs.stream.gyro and p.fps() == args.gyro_hz) or
               (p.stream_type() == rs.stream.accel and p.fps() == args.accel_hz)]
assert len(profiles) == 2, f"IMU profiles not found for gyro {args.gyro_hz} / accel {args.accel_hz}"

lock = threading.Lock()
ts = {"gyro": [], "accel": []}  # hardware timestamps in ms
def on_imu(f):
    key = "gyro" if f.get_profile().stream_type() == rs.stream.gyro else "accel"
    with lock:
        ts[key].append(f.get_timestamp())

video_frames = {"depth": [], "color": []}  # hardware frame numbers
pipe = None
if args.video:
    cfg = rs.config()
    cfg.enable_device(dev.get_info(rs.camera_info.serial_number))
    cfg.enable_stream(rs.stream.depth, 848, 480, rs.format.z16, 30)
    cfg.enable_stream(rs.stream.color, 848, 480, rs.format.rgb8, 30)
    pipe = rs.pipeline(ctx)

motion.open(profiles)
motion.start(on_imu)
if pipe:
    pipe.start(cfg)

per_second = []
t0 = time.time()
last_counts = {"gyro": 0, "accel": 0}
next_tick = t0 + 1
print(f"running {args.seconds:.0f} s: gyro {args.gyro_hz} Hz, accel {args.accel_hz} Hz, video {'on' if pipe else 'off'}", flush=True)
try:
    while time.time() - t0 < args.seconds:
        if pipe:
            fs = pipe.poll_for_frames()
            if fs:
                d, c = fs.get_depth_frame(), fs.get_color_frame()
                if d:
                    video_frames["depth"].append(d.get_frame_number())
                if c:
                    video_frames["color"].append(c.get_frame_number())
            else:
                time.sleep(0.002)
        else:
            time.sleep(0.05)
        if time.time() >= next_tick:
            with lock:
                n = {k: len(v) for k, v in ts.items()}
            row = {"second": int(next_tick - t0), "gyro": n["gyro"] - last_counts["gyro"],
                   "accel": n["accel"] - last_counts["accel"],
                   "depth_frames": len(video_frames["depth"]), "color_frames": len(video_frames["color"])}
            per_second.append(row)
            last_counts = n
            if row["second"] % 60 == 0:
                print(f"  t={row['second']:4d}s gyro {row['gyro']} Hz accel {row['accel']} Hz", flush=True)
            next_tick += 1
finally:
    if pipe:
        pipe.stop()
    motion.stop()
    motion.close()
elapsed = time.time() - t0


def gaps(stamps, hz):
    """Gaps after the first second (start-up). Clock jumps (negative or > 1 s) are counted separately."""
    a = np.array(stamps)
    a = a[a >= a[0] + 1000.0] if len(a) else a
    if len(a) < 2:
        return 0, 0.0, 0, 0
    d = np.diff(a)
    jumps = (d < 0) | (d > 1000.0)
    d = d[~jumps]
    nominal = 1000.0 / hz
    big = d > 2 * nominal
    missing = int(np.round(d[big] / nominal - 1).sum())
    return int(big.sum()), float(d.max()), missing, int(jumps.sum())


def drops(numbers):
    if len(numbers) < 2:
        return 0, 0
    d = np.diff(np.array(numbers))
    return int((d > 1).sum()), int((d[d > 1] - 1).sum())


print(f"\n== result over {elapsed:.0f} s")
for key, hz in (("gyro", args.gyro_hz), ("accel", args.accel_hz)):
    n = len(ts[key])
    g, worst, missing, jumps = gaps(ts[key], hz)
    rates = [r[key] for r in per_second[1:]]  # skip the first second (start-up)
    print(f"{key:5s}: {n} samples, mean {n / elapsed:.1f} Hz (nominal {hz}), per-second min {min(rates)} max {max(rates)}, "
          f"gaps >2x period {g}, estimated missing {missing} ({missing / max(n, 1):.3%}), worst gap {worst:.1f} ms, "
          f"clock jumps {jumps} (first second excluded)")
if pipe:
    for key in ("depth", "color"):
        n = len(video_frames[key])
        events, lost = drops(video_frames[key])
        print(f"{key:5s}: {n} frames, mean {n / elapsed:.1f} fps, drop events {events}, frames lost {lost}")

with open(args.csv, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(per_second[0].keys()))
    w.writeheader()
    w.writerows(per_second)
print(f"per-second counts written to {args.csv}")
