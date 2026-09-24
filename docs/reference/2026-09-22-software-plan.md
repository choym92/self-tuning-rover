> Research snapshot written 2026-09-22. Not maintained; current decisions are in [../decisions.md](../decisions.md) and current parts in [../build-spec.md](../build-spec.md).

# CS7638 Hardware Challenge — Software Stack & 11-Week Schedule Research

**Premise**: Youngmin "Paul" Cho, Data Science Lead (strong in Python/DS, not an embedded/software engineer). GT OMSCS CS7638 Robotics: AI Techniques, Hardware Challenge (optional), due 2026-12-10, about 11 weeks out from today (research date) 2026-09-22. Working only in evenings/weekends. Platform: a differential-drive robot (either a used Roomba + Open Interface, or a DIY chassis with quadrature-encoder motors + Arduino/ESP32) on top of a Jetson Orin Nano Super (8GB, JetPack 7.x) + USB webcam + IMU. Per course rules, assignment code cannot be AI-generated — it must be written by the student themselves.

> **How to read this**: claims backed by evidence are linked. Since this is based on search snippets/blogs, treat precise figures as "rough indicators only," and the plan builds in re-verification on the actual hardware. Anything I could not confirm is collected in the final section.

---

## 1. Jetson software stack — install order and ARM64 pitfalls

### 1.1 Recommended install order

1. **Flash JetPack 7.x** (SDK Manager or the Orin Nano Super image) — assumed already done.
2. `sudo apt update && sudo apt upgrade`, check baseline with `jtop` (jetson-stats) (recommended to install from the start for RAM/swap/temperature monitoring).
3. **Secure swap space** — build tasks (e.g. OpenCV) on the 8GB module run short on RAM. Beyond zram, recommend adding a swapfile of 4GB or more ([OpenCV 4.12 build guide](https://medium.com/@wuclark/building-opencv-4-12-0-97f8ab86efb0), [Q-engineering Orin Nano guide](https://qengineering.eu/install-opencv-on-orin-nano.html)).
4. **Decide the Python environment** (see 1.2 below).
5. `pip install pyserial numpy matplotlib` — no known issues on ARM64, wheels install normally.
6. **Attempt to install the AprilTag library** (see 1.3 below) — if it fails, switch to the fallback immediately.
7. Test the webcam (check first with `cv2.VideoCapture` or `v4l2-ctl`/`gst-launch`).
8. Set up serial permissions — add the user to the `dialout` group or write a udev rule (Permission denied is a common pitfall when the Arduino/ESP32 gets assigned to `/dev/ttyUSB0` or `/dev/ttyACM0`).

### 1.2 Python environment: venv vs conda vs docker

Jetson already ships with system CUDA/OpenCV/GStreamer libraries tied to JetPack (L4T), so the usual PC intuition of "just use conda" doesn't map well here.

- **venv (recommended, the most reasonable fit for this project's scale)**: creating it with the `--system-site-packages` option lets you inherit the OpenCV/GStreamer/CUDA Python bindings JetPack has already optimized, while still isolating pip packages. This project doesn't use any deep learning frameworks, so venv is sufficient.
- **Conda**: has the advantage of flexibly using multiple Python versions and easier installation of packages with C/C++ dependencies, but GPU integration needs more setup than venv/docker ([installing conda on Jetson Orin Nano](https://my.cytron.io/tutorial/p-conda-on-jetson-orin-nano-super), [JetsonHacks Anaconda guide](https://jetsonhacks.com/2024/11/04/install-anaconda-all-the-pythons-for-ai-ml/)). There are also reported cases where conda environments shadow the system CUDA libraries, causing conflicts with NVIDIA's aarch64-specific pip wheels (e.g. PyTorch).
- **Docker**: nvidia-docker integration gives the cleanest GPU access, and it can encapsulate the whole app stack (including non-Python dependencies), giving the best reproducibility ([Air Supply Lab Jetson Docker lesson](https://www.airsupplylab.com/nvidia-jetson-orin-nano/jetson_orin-lesson-05-jetson-docker-containers.html)). However, there's upfront setup cost, since you need to map the USB serial device (`/dev/ttyUSB0`) and the camera into the container.

**Recommendation for this project: venv (`--system-site-packages`) as the first choice.** Docker pays off later, when doing a separate VLM demo (once dependencies get heavier).

### 1.3 OpenCV: is a CUDA build necessary?

The OpenCV bundled with JetPack, or installed via `apt`/`pip`, **often lacks CUDA bindings**. Using CUDA-enabled OpenCV requires a source build, and the known pitfalls are:

- **CUDA_ARCH_BIN=8.7** (Orin Nano/Orin NX/AGX Orin are Ampere; `5.3` is the old Jetson Nano Maxwell value — get it wrong and it will still compile, but run slowly or not work) ([Q-engineering guide](https://qengineering.eu/install-opencv-on-orin-nano.html), [ProventusNova guide](https://proventusnova.com/blog/opencv-cuda-jetson-installation-guide/)).
- The build needs **4GB+ RAM plus added swap**; even `make -j4` can be too much for the 8GB module, with cases of dropping to `-j2`.
- If `python3-opencv` (apt) is already installed, there will be **path conflicts**, so it must be removed first.
- Compile time is **about 3 hours** ([Q-engineering](https://qengineering.eu/install-opencv-on-orin-nano.html)).

**Judgment (my recommendation)**: this project is mainly AprilTag detection plus basic image processing, so 5–15 fps should be plenty, and the lack of CUDA-accelerated OpenCV is unlikely to be a noticeable bottleneck. Given the 11-week time constraint, I think **starting with CPU OpenCV (`pip install opencv-contrib-python` or the pre-installed build), and only considering a CUDA build if frame rate actually becomes a problem**, is the better risk/reward tradeoff. I want to be clear this is my judgment, not a "fact confirmed by search."

### 1.4 AprilTag libraries: pupil-apriltags vs dt-apriltags vs OpenCV ArUco

- **pupil-apriltags**: AprilRobotics' apriltags3 wrapped with Python bindings by pupil-labs. Advertised as "the easiest install," but since prebuilt wheels are mostly for x86_64/manylinux or macOS, **there is often no ARM64 (aarch64) wheel, forcing a source build**, and build errors have been reported on Jetson Nano + Python 3.8 combinations ([GitHub Issue #59](https://github.com/pupil-labs/apriltags/issues/59), [pupil-apriltags PyPI](https://pypi.org/project/pupil-apriltags/)).
- **dt-apriltags**: an older implementation; PyPI has legacy distributions such as armv7l wheels, but it was hard to confirm whether up-to-date builds for recent Python/aarch64 are actively maintained ([dt-apriltags PyPI](https://pypi.org/project/dt-apriltags/)).
- **OpenCV `cv2.aruco`**: included in `opencv-contrib-python`, and directly supports AprilTag-family dictionaries (e.g. `DICT_APRILTAG_36h11`). Its biggest advantage is working out of the box on ARM64 with no separate compilation.

**Recommended strategy**: in Week 2, try `pip install pupil-apriltags` first (use it as-is if it installs), and **plan from the start to fall back immediately to `cv2.aruco`'s AprilTag dictionary if it fails**. Losing more than a day to an ARM64 wheel issue would be wasteful on an 11-week schedule.

### 1.5 Is hardware-accelerated AprilTag possible with NVIDIA VPI?

VPI supports AprilTag detection + pose estimation on CPU/GPU/**PVA** (Programmable Vision Accelerator) backends ([VPI AprilTag docs](https://docs.nvidia.com/vpi/algo_apriltags.html), [Isaac ROS AprilTag](https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_apriltag)). However, **PVA exists on Jetson AGX Orin and Orin NX, but not on Orin Nano** ([PVA SDK](https://developer.nvidia.com/embedded/pva), [Jetson Orin AGX/NX/Nano comparison](https://proventusnova.com/blog/jetson-orin-agx-vs-orin-nx-vs-orin-nano)). That means on the Orin Nano Super, even if you use VPI, only the **CPU or GPU backend** is available — VPI's core selling point of "high performance per watt via PVA" cannot be used on this board.

**Judgment (my recommendation)**: VPI has a C++-style API and requires handling camera intrinsics/image formats in VPI's own way, so there's a learning curve. Since a slow differential-drive robot's localization updates only need to run a few times per second, **I recommend going with a pure Python library (pupil-apriltags or cv2.aruco) as the first path, and deferring VPI as a stretch option for "when performance actually turns out to be the bottleneck."**

---

## 2. Control architecture: MCU vs Jetson role split + serial protocol

Diff-drive robot projects at this scale (ESP32/Arduino + host computer) converge on a clear pattern ([Hackster ESP32 diff-drive example](https://www.hackster.io/amal-shaji/differential-drive-robot-using-ros2-and-esp32-aae289), [Akash-Potti diff-drive SLAM stack](https://github.com/Akash-Potti/Slam-DifferntialDrive-Robot)).

### 2.1 What the microcontroller (Arduino/ESP32) handles — hard real-time
- Quadrature encoder interrupt counting
- **Fixed-period wheel-speed PID** (commonly 50–100Hz, details in §4)
- Motor PWM output and left/right wheel speed synchronization
- **Watchdog/safety**: stop the motors if no command arrives from Jetson for a set time (in case of a disconnection)
- Send raw encoder counts (and/or computed wheel velocity) upstream at a fixed period

### 2.2 What Jetson handles — soft real-time / compute-intensive
- State estimation (an EKF fusing odometry + IMU + AprilTag)
- Path planning/search, path smoothing
- Vision (AprilTag detection)
- Generating high-level velocity commands (linear/angular) and telemetry logging/plotting
- Where the **"course algorithm that must be implemented by hand"** (pick one of Kalman filter/particle filter/PID/SLAM/search+smoothing) actually runs

**Rationale**: the MCU can produce jitter-free, deterministic timing via interrupt-based timers, whereas Jetson's Linux (non-RTOS) is prone to jitter in Python loops — so the standard division of labor is to put timing-critical wheel PID on the MCU, and put algorithmic/compute-heavy work on Jetson.

### 2.3 Serial protocol design

The most common approach is **newline-delimited ASCII/CSV frames** (preferred in hobby/course projects for being easier to debug than a binary protocol):

- **Jetson → MCU** (e.g. `V,<left_vel>,<right_vel>\n` or `V,<linear>,<angular>\n`), roughly 20–50Hz
- **MCU → Jetson** (e.g. `E,<left_count>,<right_count>,<dt_ms>\n`, plus a separate frame for raw IMU if needed), around 50Hz to match the PID loop period

**Framing/robustness rules**:
- Use newline (`\n`) as the frame boundary; on a parse failure, drop just that line and recover (a best-effort design that tolerates receive loss)
- Checksum/simple XOR — not required, but it helps detect corrupted frames
- **MCU-side watchdog**: auto-stop if no command is received for N ms (a safety requirement)
- On the Jetson side, handle this with a separate thread/non-blocking read so the serial buffer doesn't build up

**When using the Roomba/Create Open Interface**: this "MCU layer" is already implemented in firmware. OI communicates serially over a mini-DIN connector, and the default baud rate differs by model (older models 57600, 500-series models 115200 — [iRobot Create 2 OI spec](https://cdn-shop.adafruit.com/datasheets/create_2_Open_Interface_Spec.pdf), [Roomba 500 OI spec](http://cfpm.org/~peter/bfz/iRobot_Roomba_500_Open_Interface_Spec.pdf)). It has four modes — Off/Passive/Safe/Full — and you choose among four sensor packet types via the Sensor command to receive data. Taking the Roomba path means **you don't need to design/debug encoder counting, motor driving, and the serial protocol yourself**, which saves a substantial chunk of the 11-week budget (this tradeoff is revisited in §6).

---

## 3. Differential-drive Odometry + Kalman Filter

### 3.1 Standard formulation

**Odometry kinematics** (standard textbook material — referencing MIT CSAIL lecture notes, the Caltech ME133 lab manual, etc. — [MIT material](https://groups.csail.mit.edu/drl/courses/cs54-2001s/odometry.html), [Caltech ME133 Lab 2](http://robotics.caltech.edu/wiki/images/9/9a/CSME133a_Lab2_Instructions.pdf), [automaticaddison summary](https://automaticaddison.com/calculating-wheel-odometry-for-a-differential-drive-robot/)):

```
Δd = (d_L + d_R) / 2          # average forward distance
Δθ_odom = (d_R - d_L) / L     # L = track width between the two wheels
```

**State vector**: the simplest form uses only `x = [x, y, θ]` (position + heading). Some extend it to `x = [x, y, θ, v, ω]` (constant-velocity model) when they also want to estimate velocity. There are more elaborate formulations, such as a 23-state UKF that even includes IMU bias ([arXiv FusionCore example](https://arxiv.org/pdf/2605.25239)), but that's overkill for a first project — a **3-state `[x, y, θ]` EKF** fits the scope.

**Measurement sources**:
1. **IMU yaw rate (gyro z)** — since wheel odometry's heading is vulnerable to wheel slip, gyro becomes the primary source of heading correction.
2. **AprilTag pose/range-bearing** — provides an absolute position fix that periodically bounds odometry drift, which would otherwise grow unbounded (§5).
3. (a design choice) whether to treat the wheel encoder itself as a "control input to the process model," or as a "velocity measurement" in the style of ROS's `robot_localization` package — for a first project, **using the encoder as the process-model input, and IMU+AprilTag as measurements**, is simpler to implement.

### 3.2 How to set process/measurement noise in practice

There's no textbook-correct answer, and the practical workflow generally looks like this:

- **Q (process noise)**: start from encoder resolution + wheel-slip assumptions with a small value (e.g. a diagonal matrix scaled roughly `~0.001·I` per unit time), then **grow it empirically by comparing a measured trajectory (e.g. a taped square path) against the dead-reckoning trajectory**. A smaller Q makes the filter trust the model more, giving smoother but slower-reacting output; a larger Q trusts the measurements more, making it more sensitive to noise.
- **R (measurement noise)**: for IMU, get an initial value by integrating the datasheet's gyro noise density over Δt, or directly measure the variance from logs while stationary. For AprilTag, a practical approach commonly used in student project reports is to **place the tag at a known fixed distance (e.g. exactly 1m) and repeat detection about 100 times to measure the variance of the x/y/θ estimates**.
- General principle: the practical consensus is that "Q/R should be estimated from data, experiments, and reasonable assumptions, and choosing initial values is an iterative process" ([overview of Kalman filter Q/R tuning](https://industrialmonitordirect.com/blogs/knowledgebase/kalman-filter-q-and-r-matrices-tuning-bias-compensation)).

### 3.3 Classic failure modes

- **Wheel slip**: creates a systematic heading bias that a simple Q can't capture → increase process noise on the θ component, or add slip-detection logic.
- **Timing jitter**: since Jetson's Python EKF loop doesn't run at a fixed period, **timestamp each measurement and use the actually measured Δt in the process model** (assuming a fixed period accumulates error).
- **Unsynchronized sensors**: encoder counts carry serial latency, AprilTag carries camera frame timestamps — arrival order can get scrambled. For a first project, a realistic scope is to **just process them in arrival order** (skip out-of-sequence smoothing) and document this as a known limitation.
- **Yaw drift**: integrating the gyro alone accumulates drift, so periodic correction via AprilTag/a magnetic sensor is needed. Wheel-odometry-only heading also drifts from systematic scale-factor error, such as a difference in left/right wheel diameter — a pre-calibration procedure in the style of UMBmark is commonly cited as standard.

---

## 4. Practical wheel-speed PID tuning

### 4.1 Loop period
**50–100Hz** is commonly used for small robots/hobby projects. The general principle is to set the control period sufficiently faster (empirically ~10x) than the robot dynamics' bandwidth (under 5Hz for something TurtleBot-class) ([Zbotic diff-drive speed control guide](https://zbotic.in/differential-drive-robot-kinematics-speed-control-guide/)).

### 4.2 Tuning without a plant model
An order for tuning empirically without formal system identification:
1. Turn on **P only** and raise Kp until you see overshoot/oscillation on a step input → then back it off to about half that value
2. Add a **small Ki** to remove steady-state error, watching for windup/oscillation
3. **Kd is optional** — for small diff-drive robots, the encoder-velocity signal itself is often quite noisy, so the D term tends to amplify that noise, and it's common to skip D entirely
4. Reference starting values such as `Kp=2.0, Ki=0.5, Kd=0.1` are sometimes cited for a "small chassis," but these are **unspecified "small chassis" baseline values** and likely a poor match for your own motor/wheel/battery voltage — treat them only as a starting point.

### 4.3 Anti-windup
**Conditional integration** — halting integral accumulation while the PWM is saturated at max/min — is the simplest and most effective approach to implement. Without this, if the robot is stalled against an obstacle, the I term keeps accumulating, and a large overshoot occurs the moment the obstacle is removed.

### 4.4 Encoder-based velocity estimation and the low-speed noise problem

There are two classic methods ([embeddedrelated: How to Estimate Encoder Velocity](https://www.embeddedrelated.com/showarticle/158.php)):

- **Frequency method (constant Δt)**: count pulses over a fixed period, velocity = Δcount/Δt. Simplest to implement with an Arduino ISR + timer loop, but **at low speed there are fewer pulses per interval, so quantization error grows, and in severe cases it can read as zero even while actually moving**.
- **Period method (constant Δpos)**: measures the time between encoder edges — better precision at low speed, but at high speed, encoder manufacturing tolerance (state-width error on the order of ±35° electrical angle) can push velocity error to ±5–39%, and accurately detecting exact zero velocity requires separate timeout logic, with the drawback that integrating it makes position drift unbounded.
- **Practical recommendation (the source's conclusion)**: a hybrid that mixes the two methods depending on the situation, or that samples position at the control loop period and then **applies a low-pass filter (time constant τ)**, is practical.

**Judgment (my recommendation)**: a full M/T hybrid estimator is overkill for an 11-week scope. **Start with the frequency method + low-pass filter**, and document the loss of precision at low speed as a "known limitation" — that is sufficiently in scope.

---

## 5. Using AprilTag as a measurement

### 5.1 Accuracy (rough indicators — see the "Unverified" section at the end)

According to sources found via search (experimental conditions vary too much to cross-check):
- Some reports show accuracy within **about 4cm** of actual pose at distances within roughly 2m
- One robot report found pose was generally accurate up to **~2.4m**, with deviation growing beyond that
- **Rotation (yaw angle) error is often cited as the main cause of reduced accuracy**, and while the robot is moving and rotating, pose error has reportedly reached **over 20 degrees, with 0.75m of distance error** ([paper on state estimation related to AprilTag pose accuracy](https://www.mdpi.com/1424-8220/19/24/5480) — the full text was blocked (403), so this is based on search snippets only)

**Tag size**: for indoor use within 1–3m with a regular USB webcam (not telephoto), a **square tag 8–15cm per side** is a commonly used range (larger favors detection distance/angle noise, smaller favors placing multiple tags in a small room). I recommend printing both 10cm and 15cm sizes and testing them directly.

### 5.2 How to feed it into the EKF update

Two approaches are common:
1. **Full 6-DOF tag pose** — since the AprilTag library internally runs solvePnP using tag size + camera intrinsics to produce a pose, if you know the tag's position in world coordinates, you can convert this into a direct measurement of the robot's `(x, y, θ)` for the update.
2. **Range + bearing** — use `z = [r, φ]` (distance to the tag, angle relative to the camera) as the measurement, and compute a nonlinear measurement function `h(x)` from the EKF's current estimate `(x, y, θ)` and the known tag position → linearize with the Jacobian for the update.

**Judgment (my recommendation)**: since Kalman filter lectures in courses like CS7638 usually cover **landmark-based range/bearing EKF localization** (the classic textbook robotics form), **the range/bearing formulation is likely to fit most naturally with the lecture content as the "course algorithm that must be implemented by hand."** I recommend range/bearing over using 6-DOF pose directly.

---

## 6. 11-week milestone plan (2026-09-22 → 2026-12-10)

### 6.1 Top-priority Week 1 decision: Roomba (OI) vs DIY chassis

This decision carries the most leverage for schedule risk. **A DIY chassis (electrical/mechanical debugging of motor driver wiring, encoder signal quality, gear backlash, power-supply sag from motor stall current, etc.) can easily eat an extra 2–3 weekends without an embedded/EE background.** The Roomba Open Interface already has its sensor+actuator+protocol layer validated, freeing the remaining time for the actual AI/robotics algorithms (what the course is actually evaluating). This is **my recommendation**, taking into account the user's background (Data Science Lead, non-embedded); there is also a counterargument that the DIY route better fits the learning goal of "reading sensors and driving actuators yourself" — so the final choice is yours.

### 6.2 Week-by-week plan

| Week | Dates (approx.) | Goal | Demo checkpoint |
|---|---|---|---|
| W1 | 9/22–9/28 | Decide Roomba vs DIY, order hardware, flash JetPack 7.x | Jetson boots + jtop working, python venv works |
| W2 | 9/29–10/5 | SW environment: venv, pyserial ping-pong, camera capture, install AprilTag library (with fallback per the §1.4 strategy) | Webcam frame saved with AprilTag ID overlay |
| W3 | 10/6–10/12 | HW bring-up: confirm encoder count increases when turned by hand, open-loop motor driving, check IMU noise at rest / response while rotating | **Early achievement of the "read sensors + drive actuators" requirement** (deliberately scheduled early as a buffer) |
| W4 | 10/13–10/19 | Implement MCU wheel PID (50Hz), frequency-method velocity, P→PI tuning, anti-windup | Video of straight-line driving + plot of target vs. measured speed |
| W5 | 10/20–10/26 | Implement bidirectional serial protocol, watchdog, teleop on the Jetson side | Keyboard teleop driving + CSV log of encoder telemetry |
| W6 | 10/27–11/2 | Implement dead-reckoning odometry, quantify drift with a taped square path | Plot of measured path vs. dead-reckoning, drift figures (cm/deg per m) → basis for §3.2 Q tuning |
| W7 | 11/3–11/9 | AprilTag pipeline, characterize R via repeated detection at known distances | Plot of range/bearing error by distance (1m/2m/3m) (also re-verifies §5.1) |
| W8 | 11/10–11/16 | **Implement the EKF itself** (predict: odometry model, update: IMU yaw + AprilTag range/bearing), validate offline with logged data first | Overlay of EKF trajectory vs. raw odometry trajectory on a square path, visual confirmation of reduced drift |
| W9 | 11/17–11/23 | Online/real-time integration, handle Δt jitter, fix bugs found live | Video showing real-time EKF pose displayed live on the camera feed/plot |
| W10 | 11/24–11/30 | **Buffer week** (Thanksgiving) — if on track, VLM stretch demo; if behind, reinforce W1–W9 milestones | Flexible depending on status |
| W11 | 12/1–12/7 | Record final video, organize plots/logs, write submission report, clean up code, rehearse the full demo at least twice | Submission package complete |
| Buffer | 12/8–12/10 | Handle submission portal issues, last-minute fixes, submit | — |

### 6.3 Fallback scope — what to cut, in order, if behind schedule

1. **Remove the VLM stretch demo entirely** (not graded, so cut it first)
2. **Scale down AprilTag-EKF fusion** — replace it with a much smaller-scope algorithm, such as PID alone, or search + path smoothing on a pre-known map, to satisfy the "implement one course algorithm yourself" requirement
3. **Give up on online/live EKF** — submit a demo of the EKF running offline on logged data
4. Last resort: rely more directly on the Roomba's built-in OI odometry/sensor data, and narrow the scope of hand-written code down to the filter itself

### 6.4 What to record for submission
- **Video**: hardware overview + reading sensors/driving actuators + the implemented algorithm actually running live
- **Plots**: dead-reckoning vs. EKF-corrected trajectory (against the measured path), PID step response (target vs. measured wheel velocity), AprilTag measurement error vs. distance, the Q/R values used and their justification
- **Logs**: timestamped raw encoder/IMU/AprilTag CSV, documented serial protocol spec, git history (also useful as counter-evidence against suspicion of AI-generated code, by showing an incremental, self-developed process)
- **Short write-up**: describing the implemented equations — state vector, process/measurement models, noise matrices, etc. — connected back to the lecture content

---

## Unverified items (need confirmation)

- **CS7638's exact "Hardware Challenge" requirements/rubric**: I could not confirm this directly, since I was unable to parse the public syllabus PDF as text (encoding issue). This document relies entirely on the description provided by the user.
- **AprilTag accuracy figures (~4cm at 2m, reliable up to ~2.4m, 20+ degree error while rotating)**: based on search snippets/blogs, and I could not access the full text of the MDPI paper that appears to be the underlying source (403 error). Experimental conditions (tag size, camera, library) vary widely, so treat this **only as an order-of-magnitude sense**, and be sure to re-measure on your own hardware in W7.
- **Whether pupil-apriltags/dt-apriltags currently (as of 2026) provide ARM64 wheels**: I confirmed past Jetson build-failure cases via GitHub issues, but did not directly run `pip install` on aarch64 to verify the current status → must be verified early, in W2.
- **PID starting values `Kp=2.0, Ki=0.5, Kd=0.1`**: the source only says "small chassis" without specifying motor/gear ratio. These are not values verified against your hardware — purely a starting point.
- **Accuracy/Python API maturity of NVIDIA VPI's AprilTag detector**: I confirmed from multiple sources that PVA is absent on the Orin Nano, but I could not find material directly comparing how VPI's CPU/GPU-backend AprilTag actually performs against pupil-apriltags/cv2.aruco in terms of accuracy or ease of use. Excluding VPI from the primary path is my judgment given the time constraint, not a sourced conclusion.
- **Roomba Open Interface's exact baud rate/sensor streaming commands**: I tried two official OI spec PDFs, but parsing failed on both (binary encoding issue). The baud rates in the body of this document (115200/57600/19200) are re-quoted from search snippets summarizing the spec documents, so **please check the official OI spec document for your specific model directly before wiring anything**.
