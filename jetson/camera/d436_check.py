#!/usr/bin/env python3
"""First live check of the RealSense D436 on the Jetson.

Streams depth + color + IMU for a few seconds, prints the depth and RGB matrices as numbers,
measures the real frame/sample rates, and saves one aligned depth/color picture.

Run on the Jetson:  ~/venvs/robot/bin/python d436_check.py [--seconds 5] [--out frame.png]
"""
import argparse
import time

import numpy as np
import pyrealsense2 as rs

ap = argparse.ArgumentParser()
ap.add_argument("--seconds", type=float, default=5.0)
ap.add_argument("--out", default="d436_frame.png")
args = ap.parse_args()

W, H, FPS = 848, 480, 30
cfg = rs.config()
cfg.enable_stream(rs.stream.depth, W, H, rs.format.z16, FPS)
cfg.enable_stream(rs.stream.color, W, H, rs.format.rgb8, FPS)

pipe = rs.pipeline()
profile = pipe.start(cfg)
dev = profile.get_device()
depth_scale = dev.first_depth_sensor().get_depth_scale()  # meters per raw unit
print(f"device {dev.get_info(rs.camera_info.name)}  serial {dev.get_info(rs.camera_info.serial_number)}  "
      f"fw {dev.get_info(rs.camera_info.firmware_version)}  usb {dev.get_info(rs.camera_info.usb_type_descriptor)}")
print(f"depth scale {depth_scale} m per unit")

# IMU runs on its own sensor with a callback so it does not depend on the video frame rate.
imu = {"accel": [], "gyro": []}
motion = next((s for s in dev.query_sensors() if s.is_motion_sensor()), None)
if motion:
    profiles = [p for p in motion.get_stream_profiles()
                if (p.stream_type() == rs.stream.accel and p.fps() == 100) or
                   (p.stream_type() == rs.stream.gyro and p.fps() == 200)]
    def on_imu(f):
        m = f.as_motion_frame().get_motion_data()
        key = "accel" if f.get_profile().stream_type() == rs.stream.accel else "gyro"
        imu[key].append((f.get_timestamp(), m.x, m.y, m.z))
    motion.open(profiles)
    motion.start(on_imu)
else:
    print("no motion sensor found")

align = rs.align(rs.stream.color)  # put depth pixels on the color image grid
n_depth = n_color = 0
t0 = time.time()
last = None
try:
    while time.time() - t0 < args.seconds:
        frames = align.process(pipe.wait_for_frames(timeout_ms=2000))
        d, c = frames.get_depth_frame(), frames.get_color_frame()
        if d:
            n_depth += 1
        if c:
            n_color += 1
        if d and c:
            last = (np.asanyarray(d.get_data()).copy(), np.asanyarray(c.get_data()).copy())
finally:
    pipe.stop()
    if motion:
        motion.stop()
        motion.close()
elapsed = time.time() - t0

depth_raw, rgb = last
depth = depth_raw * depth_scale  # meters, 0 = no measurement
valid = depth[depth > 0]
r, c = depth.shape[0] // 2, depth.shape[1] // 2
print(f"\nDEPTH matrix {depth.shape} (rows, cols), meters; raw dtype {depth_raw.dtype}")
print(f"  valid {valid.size / depth.size:.0%}  min {valid.min():.3f}  median {np.median(valid):.3f}  max {valid.max():.3f} m")
print(f"  center ({r},{c}) = {depth[r, c]:.3f} m")
print("  5x5 around center:\n", np.round(depth[r - 2:r + 3, c - 2:c + 3], 3))
print(f"\nRGB matrix {rgb.shape} (rows, cols, R/G/B) {rgb.dtype}; center = {rgb[r, c]}")
print(f"\nrates over {elapsed:.1f} s: depth {n_depth / elapsed:.1f} fps, color {n_color / elapsed:.1f} fps, "
      f"accel {len(imu['accel']) / elapsed:.0f} Hz, gyro {len(imu['gyro']) / elapsed:.0f} Hz")
if imu["accel"]:
    a = np.array(imu["accel"])[:, 1:]
    g = np.array(imu["gyro"])[:, 1:] if imu["gyro"] else np.zeros((1, 3))
    print(f"  accel mean (m/s^2) {np.round(a.mean(0), 3)}  |a| {np.linalg.norm(a.mean(0)):.3f} (expect ~9.81 at rest)")
    print(f"  gyro mean (rad/s) {np.round(g.mean(0), 4)} (expect ~0 at rest)")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(12, 4))
    ax[0].imshow(rgb)
    ax[0].set_title(f"RGB {rgb.shape[1]}x{rgb.shape[0]}")
    lo, hi = np.percentile(valid, [2, 98])
    im = ax[1].imshow(np.where(depth > 0, depth, np.nan), cmap="turbo", vmin=lo, vmax=hi)
    ax[1].set_title("Depth aligned to color (m), white = no data")
    fig.colorbar(im, ax=ax[1], label="meters")
    for x in ax:
        x.axis("off")
    fig.tight_layout()
    fig.savefig(args.out, dpi=100)
    print(f"\nsaved {args.out}")
except ImportError:
    np.save(args.out.rsplit(".", 1)[0] + "_depth.npy", depth)
    np.save(args.out.rsplit(".", 1)[0] + "_rgb.npy", rgb)
    print("\nmatplotlib not installed in this venv; saved the matrices as .npy instead")
