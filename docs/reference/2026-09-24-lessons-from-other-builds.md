# Lessons from other people's builds (collected 2026-09-24)

Notes from four projects Paul reviewed while planning. Each item says what they did and what we take from it.

## 1. "Running fridge" tank robot (YouTube, 2026; Jetson Orin Nano Super + ESP32 + Odin 1)

Architecture — matches ours almost 1:1:
- **Jetson = brain, ESP32 = spinal cord.** Jetson does vision and planning; the ESP32 drives the motor ESCs and enforces safety limits. Our kit is the same split (ESP32 runs PID and the JSON protocol).
- **Tiny serial protocol with resync.** 4 bytes: sync byte, left speed, right speed, door command; 100 = stop, 0 = full reverse, 200 = full forward; the ESP32 resyncs if a byte is dropped so noise never makes the robot lurch. Our kit uses JSON at 115200 — verbose but same idea. Lesson: a dropped byte must never turn into motion.
- **Software speed limits first.** Combat-robot motors made the fridge wheelie; he clamped max/min speed in firmware before anything else. Our kit's 1.3 m/s is tame, but we still cap speed and acceleration in our first control code.
- **Vision on the GPU, driving on the CPU.** YOLO nano exported to TensorRT so the GPU carries detection and the CPU stays free for Nav2. Same plan for us (Ultralytics → TensorRT).
- **Velocity smoother node** between planner and motors so the payload does not get thrown around. We add the same for the camera and later the arm.
- **Nav2 does not know how to follow a person.** He wrote a translator node: follow = goal 1 m short of the person; flee = goal in the opposite direction, updated as the person moves. Generic planners need a small purpose-built node on top.
- **Three control modes: manual / semi-auto / auto**, with manual giving the raw unfiltered drive. We keep a manual mode that bypasses the filters for testing and data collection.
- **Web page served by the Jetson, driven from a Steam Deck.** Browser page with live telemetry + robot-eye camera; the Deck's sticks and buttons drive it through the browser's gamepad support; a big red stop under the thumb. No laptop tether, no app. Our Waveshare kit ships a Flask + WebRTC web app with gamepad support, so we get this nearly free; any device with a browser (phone, laptop, Deck) works. Priority for our version: the software E-stop must be the most reliable control on the page.
- **Persistent target ID is missing** — the tracker locks to the closest person every frame and switches in crowds. Lesson for our person-following: track identity over time (a tracker with IDs, or face/appearance re-ID), not per-frame nearest.
- **Line of sight is the limit**; his next step is UWB tags (radio time-of-flight) so the robot can find him through walls. Interesting later option for "come to me".
- **No global map yet** — only local costmap; global map + saved destinations (charger, couch) is his next step. Same as our phase 2.
- **Sponsor sensor (Odin 1)** did the localization for him (on-device SLAM, $999). We build that part ourselves; see decisions.md.
- **Practical**: 3D-scanned the fridge underside to design the chassis around it; bought real tank treads instead of printing them; a walking base would shake the drinks. Choose the base for the payload.
- **Field damage after an event → full rebuild in stronger material.** Plan for repairs; keep the design files.

## 2. Jetson Nano rover with RealSense + RPLidar + joysticks (Hackaday, 2020)

- Teleop + sensor visualization only; mapping in Rviz but "no control node yet". It stopped at phase 1.
- **No wheel encoders** (servos + ESC, open loop) — no odometry, so no filter or autonomy was possible. This is why encoders are a hard requirement for us.
- Ubuntu/ROS version mismatch between PC and Jetson caused friction; "ROS 2 gets crazy with 8 or more terminals". Keep the first version ROS-free.

## 3. Pan-tilt YOLO tracking with Isaac ROS (Martin Cerven, 2026)

- D455 + Isaac ROS YOLO at 30 fps + PD controller on a pan-tilt head; "next: enable tilt and joint limits".
- Our version: convert pixel error to angle with the camera intrinsics (≈14.7 px/° on the D436), use the ST3215 servo's position feedback, P(+D) with speed/acceleration limits, filter the detection with a constant-velocity Kalman filter, log (t, pixel error, commanded angle, measured angle) and tune the gains by replay. First instance of the self-tuning loop.

## 4. SO-101 arms + LeRobot (YouTube, 2026)

- Two 3D-printed arms (leader/follower, Feetech STS3215 servos), LeRobot data collection (≈1 h per 50 episodes), ACT training 2–4 h, SmolVLA fine-tune 3 h; works "almost", <90% success, fails with two cubes.
- Toolchain wants real Linux (VM USB cameras choke, macOS unsupported at the time); assign servo IDs one by one during assembly; kit clamps too small; a Jetson Nano (2019) could not run the policies. Our Orin Nano Super can (see decisions.md).
- Deferred to a later phase; deformable objects (clothes) are out of scope.

## Cross-cutting lessons

1. Every successful build separates **real-time motor control (microcontroller)** from **perception/planning (Jetson)**.
2. **Encoders and timestamps** are the difference between a demo and a system you can evaluate.
3. Start **without ROS**, add it when a package (Nav2, Isaac ROS) is worth its setup cost.
4. **Manual mode + E-stop + logging** come before autonomy; the manual runs are the first dataset.
5. Vision on GPU via TensorRT; keep the CPU for control and planning.
6. Expect to **rebuild** after the first outing.
