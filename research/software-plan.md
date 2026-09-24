# CS7638 Hardware Challenge — 소프트웨어 스택 & 11주 일정 리서치

**전제**: Youngmin "Paul" Cho, Data Science Lead (Python/DS 강점, embedded/software engineer 아님). GT OMSCS CS7638 Robotics: AI Techniques, Hardware Challenge(옵션) 마감 2026-12-10, 오늘(리서치 시점) 2026-09-22 기준 약 11주. 저녁/주말에만 작업. 플랫폼: differential-drive robot (중고 Roomba + Open Interface, 또는 quadrature encoder 모터 + Arduino/ESP32 DIY 섀시) 위에 Jetson Orin Nano Super(8GB, JetPack 7.x) + USB webcam + IMU. 코스 규정상 과제 코드는 AI로 생성 불가 — 본인이 직접 작성해야 함.

> **읽는 법**: 근거가 있는 주장에는 링크를 달았습니다. 검색 스니펫/블로그 기반이라 정밀 수치는 "대략적 지표"로 취급하고, 실제 하드웨어에서 재검증하도록 계획에 반영했습니다. 확인하지 못한 부분은 맨 끝 섹션에 모았습니다.

---

## 1. Jetson 소프트웨어 스택 — 설치 순서와 ARM64 함정

### 1.1 설치 순서 (권장)

1. **JetPack 7.x 플래시** (SDK Manager 또는 Orin Nano Super용 이미지) — 이미 있다고 가정.
2. `sudo apt update && sudo apt upgrade`, `jtop`(jetson-stats)로 베이스라인 확인 (RAM/스왑/온도 모니터링용으로 처음부터 깔아두는 걸 추천).
3. **스왑 공간 확보** — 8GB 모듈에서 빌드 작업(OpenCV 등)을 하면 RAM이 부족합니다. zram 외에 swapfile을 4GB 이상 추가하는 걸 권장 ([OpenCV 4.12 빌드 가이드](https://medium.com/@wuclark/building-opencv-4-12-0-97f8ab86efb0), [Q-engineering Orin Nano 가이드](https://qengineering.eu/install-opencv-on-orin-nano.html)).
4. **Python 환경 결정** (아래 1.2).
5. `pip install pyserial numpy matplotlib` — ARM64에서 알려진 문제 없음, wheel 정상 설치.
6. **AprilTag 라이브러리 설치 시도** (아래 1.3) — 실패 시 즉시 fallback으로 전환.
7. 웹캠 테스트 (`cv2.VideoCapture` 또는 `v4l2-ctl`/`gst-launch`로 먼저 확인).
8. 시리얼 권한 설정 — 유저를 `dialout` 그룹에 추가하거나 udev rule 작성 (Arduino/ESP32가 `/dev/ttyUSB0`, `/dev/ttyACM0`으로 잡힐 때 Permission denied가 흔한 함정).

### 1.2 Python 환경: venv vs conda vs docker

Jetson은 JetPack(L4T)에 묶인 시스템 CUDA/OpenCV/GStreamer 라이브러리가 이미 깔려 있어서, 일반 PC의 "그냥 conda 쓰면 되지" 감각이 잘 안 맞습니다.

- **venv (권장, 이 프로젝트 규모엔 가장 무난)**: `--system-site-packages` 옵션으로 만들면 JetPack이 이미 최적화해둔 OpenCV/GStreamer/CUDA 파이썬 바인딩을 그대로 상속받으면서, pip 패키지는 격리할 수 있습니다. 이 프로젝트는 딥러닝 프레임워크를 안 쓰므로 venv로 충분합니다.
- **Conda**: 여러 파이썬 버전을 유연하게 쓸 수 있고 C/C++ 의존성이 있는 패키지 설치가 편하다는 장점이 있지만, GPU 연동은 venv/docker보다 설정이 더 필요합니다 ([Jetson Orin Nano에 conda 설치](https://my.cytron.io/tutorial/p-conda-on-jetson-orin-nano-super), [JetsonHacks Anaconda 가이드](https://jetsonhacks.com/2024/11/04/install-anaconda-all-the-pythons-for-ai-ml/)). Conda 환경이 시스템 CUDA 라이브러리를 가리는 경우가 있어 NVIDIA의 aarch64 전용 pip wheel(예: PyTorch)과 충돌하는 사례도 보고됩니다.
- **Docker**: nvidia-docker 연동으로 GPU 접근이 가장 깔끔하고, 앱 스택 전체(비-Python 의존성 포함)를 캡슐화할 수 있어 재현성이 가장 좋습니다 ([Air Supply Lab Jetson Docker 강의](https://www.airsupplylab.com/nvidia-jetson-orin-nano/jetson_orin-lesson-05-jetson-docker-containers.html)). 다만 컨테이너 안에서 USB 시리얼 장치(`/dev/ttyUSB0`)와 카메라를 매핑해줘야 해서 초기 설정 비용이 있습니다.

**이 프로젝트에는 venv(`--system-site-packages`)를 1순위로 추천**합니다. Docker는 나중에 VLM 데모를 별도로 해볼 때(의존성이 무거워질 때) 쓰는 게 시간 대비 이득이 큽니다.

### 1.3 OpenCV: CUDA 빌드가 필요한가

JetPack에 기본 탑재되거나 `apt`/`pip`로 까는 OpenCV는 **CUDA 바인딩이 빠져 있는 경우가 많습니다**. CUDA 지원 OpenCV를 쓰려면 소스 빌드가 필요하고, 알려진 함정은:

- **CUDA_ARCH_BIN=8.7** (Orin Nano/Orin NX/AGX Orin은 Ampere, `5.3`은 구형 Jetson Nano용 Maxwell 값이라 틀리면 컴파일은 되어도 느리거나 안 돌아감) ([Q-engineering 가이드](https://qengineering.eu/install-opencv-on-orin-nano.html), [ProventusNova 가이드](https://proventusnova.com/blog/opencv-cuda-jetson-installation-guide/)).
- 빌드에 **4GB+ RAM, 스왑 추가 필요**, `make -j4`도 8GB 모듈에서는 버거울 수 있어 `-j2`로 낮추는 사례 있음.
- 기존 `python3-opencv`(apt)가 깔려 있으면 **경로 충돌**이 나므로 먼저 제거해야 함.
- 컴파일 시간 **약 3시간** ([Q-engineering](https://qengineering.eu/install-opencv-on-orin-nano.html)).

**판단(제 권장)**: 이번 프로젝트는 AprilTag 검출 + 기본 영상 처리 정도라 5–15fps면 충분하고, CUDA 가속 OpenCV가 없어도 체감 병목이 크지 않을 가능성이 높습니다. 11주라는 시간 제약을 고려하면 **CPU OpenCV(`pip install opencv-contrib-python` 또는 기본 탑재본)로 시작하고, 실제로 프레임레이트가 문제될 때만 CUDA 빌드를 고려**하는 게 리스크 대비 이득이 낫다고 봅니다. 이건 제 판단이며 "검색으로 확인된 사실"이 아니라는 점을 명확히 합니다.

### 1.4 AprilTag 라이브러리: pupil-apriltags vs dt-apriltags vs OpenCV ArUco

- **pupil-apriltags**: AprilRobotics의 apriltags3를 pupil-labs가 파이썬 바인딩으로 감싼 것. "가장 쉬운 설치"로 소개되지만, 흔히 x86_64/manylinux나 macOS용 prebuilt wheel 위주라 **ARM64(aarch64)용 wheel이 없어 소스 빌드로 떨어지는 경우가 있고**, Jetson Nano + Python 3.8 조합에서 빌드 에러가 보고된 바 있습니다 ([GitHub Issue #59](https://github.com/pupil-labs/apriltags/issues/59), [pupil-apriltags PyPI](https://pypi.org/project/pupil-apriltags/)).
- **dt-apriltags**: 더 오래된 구현체로, PyPI에 armv7l wheel 등 레거시 배포판은 있지만 최신 Python/aarch64용 최신 빌드가 꾸준히 유지되는지는 확인이 어려웠습니다 ([dt-apriltags PyPI](https://pypi.org/project/dt-apriltags/)).
- **OpenCV `cv2.aruco`**: `opencv-contrib-python`에 포함되어 있고, AprilTag 계열 dictionary(예: `DICT_APRILTAG_36h11`)를 직접 지원합니다. 별도 컴파일 없이 ARM64에서 그대로 동작한다는 게 가장 큰 장점입니다.

**권장 전략**: Week 2에 `pip install pupil-apriltags`를 먼저 시도하고(설치되면 그대로 사용), **실패하면 즉시 `cv2.aruco`의 AprilTag dictionary로 폴백**하는 계획을 처음부터 짜두세요. 11주 일정에서 ARM64 wheel 이슈로 하루 이상 쓰는 건 아깝습니다.

### 1.5 NVIDIA VPI로 하드웨어 가속 AprilTag가 가능한가

VPI는 CPU/GPU/**PVA**(Programmable Vision Accelerator) 백엔드로 AprilTag 검출+pose 추정을 지원합니다 ([VPI AprilTag 문서](https://docs.nvidia.com/vpi/algo_apriltags.html), [Isaac ROS AprilTag](https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_apriltag)). 그런데 **PVA는 Jetson AGX Orin과 Orin NX에는 있지만, Orin Nano에는 없습니다** ([PVA SDK](https://developer.nvidia.com/embedded/pva), [Jetson Orin AGX/NX/Nano 비교](https://proventusnova.com/blog/jetson-orin-agx-vs-orin-nx-vs-orin-nano)). 즉 Orin Nano Super에서는 VPI를 쓰더라도 **CPU 또는 GPU 백엔드**만 가능하고, "PVA로 전력 대비 고성능"이라는 VPI의 핵심 셀링포인트는 이 보드에서 못 씁니다.

**판단(제 권장)**: VPI는 API가 C++ 스타일이고 카메라 intrinsics/이미지 포맷을 VPI 고유 방식으로 다뤄야 해서 학습 곡선이 있습니다. 저속 differential-drive 로봇의 로컬라이제이션 업데이트는 초당 몇 회면 충분하므로, **1차로는 순수 Python 라이브러리(pupil-apriltags 또는 cv2.aruco)로 가고, VPI는 "성능이 실제로 병목일 때"의 스트레치 옵션으로 미뤄두는 것을 권장**합니다.

---

## 2. 제어 아키텍처: MCU vs Jetson 역할 분담 + 시리얼 프로토콜

이 급의 diff-drive 로봇 프로젝트(ESP32/Arduino + 상위 컴퓨터)들이 수렴하는 패턴은 뚜렷합니다 ([Hackster ESP32 diff-drive 예시](https://www.hackster.io/amal-shaji/differential-drive-robot-using-ros2-and-esp32-aae289), [Akash-Potti diff-drive SLAM 스택](https://github.com/Akash-Potti/Slam-DifferntialDrive-Robot)).

### 2.1 마이크로컨트롤러(Arduino/ESP32)가 맡는 것 — hard real-time
- Quadrature encoder 인터럽트 카운팅
- **고정 주기 wheel-speed PID** (일반적으로 50–100Hz, 자세한 값은 §4)
- 모터 PWM 출력 및 좌우 휠 속도 동기화
- **워치독/세이프티**: 일정 시간 Jetson으로부터 명령이 안 오면 모터 정지 (연결 끊김 대비)
- 원시 encoder count(및/또는 계산된 wheel velocity)를 고정 주기로 상위로 송신

### 2.2 Jetson이 맡는 것 — soft real-time / 계산 집약
- 상태 추정 (odometry + IMU + AprilTag를 융합하는 EKF)
- 경로 계획/탐색, path smoothing
- 비전 (AprilTag 검출)
- 고수준 속도 명령(linear/angular) 생성 및 텔레메트리 로깅/플로팅
- **"직접 구현해야 하는 코스 알고리즘"**(Kalman filter/particle filter/PID/SLAM/search+smoothing 중 택1)이 실제로 도는 곳

**근거**: MCU는 인터럽트 기반 타이머로 지터 없는 확정적(deterministic) 타이밍을 낼 수 있는 반면, Jetson의 Linux(비-RTOS)는 Python 루프에 지터가 생기기 쉬우므로, 타이밍이 생명인 휠 PID는 MCU에, 알고리즘/연산 집약적 작업은 Jetson에 두는 분업이 표준입니다.

### 2.3 시리얼 프로토콜 설계

가장 흔한 접근은 **줄바꿈으로 구분되는 ASCII/CSV 프레임**입니다(바이너리 프로토콜보다 디버깅이 쉬워 취미/코스 프로젝트에서 선호됨):

- **Jetson → MCU** (예: `V,<left_vel>,<right_vel>\n` 또는 `V,<linear>,<angular>\n`), 약 20–50Hz
- **MCU → Jetson** (예: `E,<left_count>,<right_count>,<dt_ms>\n`, 필요하면 IMU raw도 별도 프레임), PID 루프 주기와 맞춰 50Hz 내외

**프레이밍/견고성 규칙**:
- 줄바꿈(`\n`)을 프레임 경계로 사용, 파싱 실패 시 해당 줄만 버리고 복구(受信 손실을 용인하는 best-effort 설계)
- 체크섬/간단한 XOR — 필수는 아니지만 있으면 깨진 프레임 감지에 도움
- **MCU 쪽 워치독**: N ms 동안 명령 미수신 시 자동 정지 (안전 필수)
- Jetson 쪽은 별도 스레드/논블로킹 read로 시리얼 버퍼가 쌓이지 않게 처리

**Roomba/Create Open Interface를 쓰는 경우**: 이 "MCU 레이어"가 이미 펌웨어로 구현되어 있습니다. OI는 mini-DIN 커넥터로 시리얼 통신하며, 모델별 기본 baud rate가 다릅니다(구형 57600, 500 시리즈류는 115200 — [iRobot Create 2 OI 스펙](https://cdn-shop.adafruit.com/datasheets/create_2_Open_Interface_Spec.pdf), [Roomba 500 OI 스펙](http://cfpm.org/~peter/bfz/iRobot_Roomba_500_Open_Interface_Spec.pdf)). Off/Passive/Safe/Full 네 가지 모드가 있고, Sensor 명령으로 4종의 sensor packet 중 선택해 데이터를 받습니다. Roomba 경로를 택하면 **encoder count·모터 구동·직렬 프로토콜을 직접 설계/디버깅할 필요가 없어져서**, 11주 예산의 상당 부분을 아낄 수 있습니다 (§6에서 이 트레이드오프를 다시 다룸).

---

## 3. Differential-drive Odometry + Kalman Filter

### 3.1 표준 정식화

**Odometry 기구학** (MIT CSAIL 강의자료, Caltech ME133 랩 매뉴얼 등 표준 교재형 자료 참고 — [MIT 자료](https://groups.csail.mit.edu/drl/courses/cs54-2001s/odometry.html), [Caltech ME133 Lab 2](http://robotics.caltech.edu/wiki/images/9/9a/CSME133a_Lab2_Instructions.pdf), [automaticaddison 정리](https://automaticaddison.com/calculating-wheel-odometry-for-a-differential-drive-robot/)):

```
Δd = (d_L + d_R) / 2          # 평균 직진 거리
Δθ_odom = (d_R - d_L) / L     # L = 두 바퀴 사이 track width
```

**State vector**: 가장 간단한 형태는 `x = [x, y, θ]` (위치 + heading)만 씁니다. 속도까지 추정하고 싶으면 `x = [x, y, θ, v, ω]`(constant-velocity 모델)로 확장하는 경우도 있습니다. 23-state UKF처럼 IMU bias까지 포함하는 정교한 정식화도 있지만([arXiv FusionCore 예시](https://arxiv.org/pdf/2605.25239)), 첫 프로젝트에는 과합니다 — **3-state `[x, y, θ]` EKF**가 스코프에 맞습니다.

**Measurement 소스**:
1. **IMU yaw rate (gyro z)** — wheel odometry의 heading이 wheel slip에 취약하므로, gyro가 heading 보정의 1차 소스가 됨.
2. **AprilTag pose/range-bearing** — 절대 위치 fix를 제공해 그렇지 않으면 unbounded로 커지는 odometry drift를 주기적으로 bound시킴 (§5).
3. (설계에 따라) wheel encoder 자체를 "process model의 입력(control input)"으로 쓸지, 아니면 ROS `robot_localization` 패키지 스타일로 "속도 측정치(measurement)"로 다룰지는 선택 사항 — 첫 프로젝트에는 **encoder를 process model 입력으로, IMU+AprilTag를 measurement로** 쓰는 쪽이 구현이 더 단순합니다.

### 3.2 Process/Measurement noise를 실전에서 어떻게 잡는가

문헌 기준 정답은 없고, 실무 워크플로우는 대체로 다음과 같습니다:

- **Q(process noise)**: encoder 해상도 + wheel-slip 가정에서 출발해 작은 값(예: 단위시간당 대각행렬 `~0.001·I` 스케일)으로 시작한 뒤, **실측 궤적(테이프로 표시한 정사각형 경로 등)과 dead-reckoning 궤적을 비교하며 경험적으로 키움**. Q를 작게 잡을수록 필터가 모델을 더 신뢰해 출력이 부드러워지지만 반응이 느려지고, 크게 잡을수록 측정치를 더 신뢰해 노이즈에 민감해집니다.
- **R(measurement noise)**: IMU는 데이터시트의 gyro noise density를 Δt로 적분해 초기값을 잡거나, 정지 상태에서 로그를 찍어 분산을 직접 측정. AprilTag는 **알려진 고정 거리(예: 정확히 1m)에 태그를 두고 100회 정도 반복 검출해 x/y/θ 추정치의 분산을 측정**하는 방식이 학생 프로젝트 리포트에서 흔히 쓰이는 실전 접근입니다.
- 일반론: "Q/R은 데이터·실험·합리적 가정으로 추정하고, 초기값 선택은 반복적 과정"이라는 게 실무 컨센서스입니다 ([Kalman filter Q/R 튜닝 개괄](https://industrialmonitordirect.com/blogs/knowledgebase/kalman-filter-q-and-r-matrices-tuning-bias-compensation)).

### 3.3 클래식 실패 모드

- **Wheel slip**: 단순 Q로는 못 잡는 체계적 heading bias를 만듦 → θ 성분의 process noise를 더 크게 잡거나, slip 감지 로직 추가.
- **Timing jitter**: Jetson의 Python EKF 루프는 고정 주기가 아니므로, 각 measurement에 타임스탬프를 찍고 **실측 Δt를 process model에 사용**해야 함(고정 주기를 가정하면 오차 누적).
- **비동기 센서(unsynchronized sensors)**: encoder count는 시리얼 지연, AprilTag는 카메라 프레임 타임스탬프 — 도착 순서가 뒤섞일 수 있음. 첫 프로젝트에서는 **도착 순서대로 그냥 처리**(out-of-sequence smoothing 생략)하고 이를 알려진 한계로 문서화하는 정도가 현실적 스코프입니다.
- **Yaw drift**: gyro만 적분하면 drift가 쌓이므로 AprilTag/자기장 센서로 주기적 보정 필요. Wheel-odometry 단독 heading도 좌우 바퀴 지름 차이 등 systematic scale-factor error로 drift — UMBmark류의 사전 캘리브레이션 절차가 표준으로 언급됩니다.

---

## 4. Wheel-speed PID 실전 튜닝

### 4.1 루프 주기
소형 로봇/취미 프로젝트에서 **50–100Hz**가 흔히 쓰입니다. 로봇 동역학 대역폭(터틀봇급이면 5Hz 미만)보다 충분히(경험적으로 ~10배) 빠른 제어 주기를 잡으라는 것이 일반 원칙입니다 ([Zbotic diff-drive 속도제어 가이드](https://zbotic.in/differential-drive-robot-kinematics-speed-control-guide/)).

### 4.2 Plant 모델 없이 튜닝하기
정식 시스템 식별 없이, 경험적으로 튜닝하는 순서:
1. **P만** 켜고 Kp를 올리며 step 입력에 대한 오버슈트/진동이 보일 때까지 키움 → 그 값에서 절반 정도로 낮춤
2. **작은 Ki**를 추가해 정상상태 오차 제거, windup/진동 관찰
3. **Kd는 선택적** — 소형 diff-drive 로봇은 encoder-velocity 신호 자체가 노이즈가 커서 D항이 그 노이즈를 증폭시키는 경우가 많아 D를 아예 안 쓰는 구현도 흔함
4. 참고용 시작값으로 소형 섀시 기준 `Kp=2.0, Ki=0.5, Kd=0.1` 같은 수치가 언급되긴 하나, 이건 **특정되지 않은 "소형 섀시" 기준값**이라 본인 모터/휠/배터리 전압에는 그대로 안 맞을 가능성이 큽니다 — 출발점 정도로만 취급.

### 4.3 Anti-windup
PWM이 최대/최소로 saturate된 동안은 integral 누적을 멈추는 **conditional integration**이 구현이 가장 간단하고 효과적입니다. 이렇게 안 하면 로봇이 장애물에 눌려 정지한 상태에서 I항이 계속 쌓이다가, 장애물이 사라지는 순간 큰 오버슈트가 발생합니다.

### 4.4 Encoder 기반 velocity 추정과 저속 노이즈 문제

두 가지 고전적 방법이 있습니다 ([embeddedrelated: How to Estimate Encoder Velocity](https://www.embeddedrelated.com/showarticle/158.php)):

- **Frequency method (constant Δt)**: 고정 주기마다 pulse count를 세어 속도 = Δcount/Δt. 구현이 Arduino ISR + 타이머 루프로 가장 간단하지만, **저속에서는 구간당 pulse 수가 적어 양자화 오차가 커지고, 심하면 실제로 움직이는데도 0으로 읽힐 수 있음**.
- **Period method (constant Δpos)**: encoder edge 사이의 시간을 측정 — 저속에서 정밀도는 더 좋지만, 고속에서는 encoder 제조 공차(전기각 ±35° 수준의 상태 폭 오차)로 인해 속도 오차가 ±5~39%까지 벌어질 수 있고, 정확한 0속도를 감지하려면 타임아웃 로직이 따로 필요해 통합(integration) 시 위치 drift가 unbounded해지는 단점이 있습니다.
- **실전 권장(소스의 결론)**: 두 방법을 상황에 맞게 섞거나, 제어 루프 주기에 맞춰 위치를 샘플링한 뒤 **저역통과 필터(시상수 τ)를 적용**하는 하이브리드가 실용적입니다.

**판단(제 권장)**: 완전한 M/T 하이브리드 추정기는 11주 스코프에는 과합니다. **frequency method + 저역통과 필터**로 시작하고, 저속에서의 정밀도 저하는 "알려진 한계"로 문서화하는 것으로 충분히 스코프에 맞습니다.

---

## 5. AprilTag를 측정치로 쓰기

### 5.1 정확도 (대략적 지표 — 아래 "확인 못한 부분" 참고)

검색으로 찾은 자료들(실험 조건이 제각각이라 크로스체크는 못함)에 따르면:
- 약 2m 이내 거리에서 실제 pose 대비 **약 4cm 이내** 정확도가 보고된 사례가 있음
- 한 로봇 리포트에서는 pose가 **~2.4m까지는 대체로 정확**했고, 그 이상은 편차가 커짐
- **회전(yaw angle) 오차가 정확도 저하의 주 원인**으로 지목되는 경우가 많고, 로봇이 움직이며 회전하는 중에는 pose 오차가 **20도 이상, 거리 오차 0.75m**까지 벌어졌다는 보고도 있음 ([AprilTag pose 정확도 관련 상태추정 논문](https://www.mdpi.com/1424-8220/19/24/5480) — 본문은 접근 차단(403)으로 직접 확인은 못했고 검색 스니펫 기준)

**태그 크기**: 실내 1–3m 범위, 일반 USB webcam(망원 렌즈 아님) 기준으로는 **한 변 8–15cm 정사각 태그**가 흔히 쓰이는 범위입니다(크면 검출 거리·각도 노이즈에 유리, 작으면 좁은 방에서 여러 태그를 배치하기 유리). 10cm와 15cm 두 사이즈를 인쇄해 직접 테스트해보는 걸 권장합니다.

### 5.2 EKF 업데이트에 넣는 방법

두 가지 방식이 흔합니다:
1. **Full 6-DOF tag pose** — AprilTag 라이브러리가 태그 크기+카메라 intrinsics로 내부적으로 solvePnP를 돌려 pose를 주므로, 월드 좌표계상 태그 위치를 알고 있다면 이를 로봇 `(x, y, θ)`의 직접 측정치로 변환해 업데이트.
2. **Range + bearing** — `z = [r, φ]` (태그까지 거리, 카메라 기준 각도)를 측정치로 쓰고, EKF 현재 추정치 `(x, y, θ)`와 알려진 태그 위치로부터 비선형 측정함수 `h(x)`를 계산 → Jacobian으로 선형화해 업데이트.

**판단(제 권장)**: CS7638 같은 코스의 Kalman filter 강의는 보통 **landmark 기반 range/bearing EKF localization**(로봇공학 교과서의 전형적 형태)을 다루므로, **"직접 구현해야 하는 코스 알고리즘"으로는 range/bearing 정식화가 강의 내용과 가장 자연스럽게 맞아떨어질 가능성이 높습니다**. 6-DOF pose를 직접 쓰는 것보다 range/bearing 쪽을 권장합니다.

---

## 6. 11주 마일스톤 플랜 (2026-09-22 → 2026-12-10)

### 6.1 Week 1 최우선 결정: Roomba(OI) vs DIY 섀시

이 결정이 일정 리스크에서 가장 레버리지가 큽니다. **DIY 섀시(모터 드라이버 배선, encoder 신호 품질, 기어 백래시, 모터 정지전류로 인한 전원 강하 등 전기·기계적 디버깅)는 embedded/EE 배경이 없는 상태에서 주말 2~3주를 추가로 먹기 쉽습니다.** Roomba Open Interface는 sensor+actuator+protocol 레이어가 이미 검증되어 있어, 남은 시간을 실제 AI/로보틱스 알고리즘(코스가 평가하려는 것)에 쓸 수 있게 해줍니다. 이건 사용자의 배경(Data Science Lead, non-embedded)을 고려한 **제 권장 판단**이며, DIY 쪽이 "센서를 직접 읽고 액추에이터를 직접 구동"한다는 학습 목표에는 더 부합한다는 반론도 있을 수 있어 최종 선택은 본인 몫입니다.

### 6.2 주차별 계획

| 주차 | 날짜(대략) | 목표 | Demo 체크포인트 |
|---|---|---|---|
| W1 | 9/22–9/28 | Roomba vs DIY 결정, 하드웨어 주문, JetPack 7.x 플래시 | Jetson 부팅 + jtop 정상, python venv 동작 |
| W2 | 9/29–10/5 | SW 환경: venv, pyserial ping-pong, 카메라 캡처, AprilTag 라이브러리 설치(§1.4 전략대로 fallback 포함) | 웹캠 프레임에 AprilTag ID 오버레이된 이미지 저장 |
| W3 | 10/6–10/12 | HW bring-up: encoder count 수동 회전 시 증가 확인, open-loop 모터 구동, IMU 정지시 노이즈/회전시 반응 확인 | **"센서 읽기 + 액추에이터 구동" 요구사항 조기 달성** (버퍼 확보용으로 일부러 일찍 배치) |
| W4 | 10/13–10/19 | MCU 휠 PID 구현(50Hz), frequency-method velocity, P→PI 튜닝, anti-windup | 직진 주행 영상 + 목표속도 대비 실측속도 플롯 |
| W5 | 10/20–10/26 | 시리얼 프로토콜 양방향 구현, 워치독, Jetson 쪽 teleop | 키보드 teleop 주행 + encoder 텔레메트리 CSV 로그 |
| W6 | 10/27–11/2 | Dead-reckoning odometry 구현, 테이프 정사각형 경로로 drift 정량화 | 실측 경로 vs dead-reckoning 플롯, drift(cm/deg per m) 수치화 → §3.2 Q 튜닝 근거 |
| W7 | 11/3–11/9 | AprilTag 파이프라인, 알려진 거리에서 반복 검출로 R 특성화 | 거리별(1m/2m/3m) range·bearing 오차 플롯 (§5.1 재검증 겸함) |
| W8 | 11/10–11/16 | **EKF 직접 구현** (predict: odometry 모델, update: IMU yaw + AprilTag range/bearing), 로그 데이터로 오프라인 검증 먼저 | 정사각형 경로에서 EKF 궤적 vs raw odometry 궤적 overlay, drift 감소 시각적 확인 |
| W9 | 11/17–11/23 | 온라인/실시간 통합, Δt 지터 처리, 라이브에서 발견되는 버그 수정 | 실시간 EKF pose가 카메라 피드/플롯에 라이브로 표시되는 영상 |
| W10 | 11/24–11/30 | **버퍼 주간**(추수감사절) — 순항 중이면 VLM 스트레치 데모, 지연 중이면 W1–W9 마일스톤 보강 | 상황에 따라 유동적 |
| W11 | 12/1–12/7 | 최종 영상 녹화, 플롯/로그 정리, 제출 리포트 작성, 코드 정리, 전체 데모 최소 2회 리허설 | 제출 패키지 완성 |
| 버퍼 | 12/8–12/10 | 제출 포털 이슈 대응, 막판 수정, 제출 | — |

### 6.3 Fallback scope — 밀렸을 때 잘라내는 순서

1. **VLM 스트레치 데모** 전체 제거 (그레이딩 대상 아님, 가장 먼저 버림)
2. **AprilTag-EKF 융합** 축소 — PID 단독 또는 (미리 아는 맵 위에서의) search + path smoothing처럼 스코프가 훨씬 작은 알고리즘으로 "코스 알고리즘 1개 직접 구현" 요구사항을 대체 충족
3. **온라인/라이브 EKF** 포기 — 로그된 데이터에 대한 오프라인 EKF 실행 결과를 데모로 제출
4. 최후 수단: Roomba의 OI 내장 odometry/센서 데이터에 더 직접적으로 의존하고, 직접 짜는 코드 범위를 필터 자체로 좁힘

### 6.4 제출용으로 기록해둘 것
- **영상**: 하드웨어 개요 + 센서 읽기/액추에이터 구동 + 구현한 알고리즘이 실제로 동작하는 라이브 실행
- **플롯**: dead-reckoning vs EKF-보정 궤적(실측 경로 대비), PID step response(목표 vs 실측 wheel velocity), AprilTag 측정 오차 vs 거리, 사용한 Q/R 값과 그 근거
- **로그**: timestamp 찍힌 raw encoder/IMU/AprilTag CSV, 시리얼 프로토콜 명세 문서화, git 히스토리(점진적 자체 개발 과정을 보여줘 AI-코드 사용 의혹에 대한 반증 자료로도 활용 가능)
- **짧은 설명**: state vector, process/measurement 모델, noise 행렬 등 구현한 수식을 강의 내용과 연결해 서술

---

## 확인하지 못한 부분 (검증 필요)

- **CS7638 "Hardware Challenge"의 정확한 요구사항/루브릭**: 공개 syllabus PDF를 텍스트로 파싱하지 못해(인코딩 문제) 직접 확인하지 못했습니다. 이 문서는 전적으로 사용자가 제공한 설명에 의존합니다.
- **AprilTag 정확도 수치(2m에서 ~4cm, ~2.4m까지 신뢰 가능, 회전 중 20도+ 오차)**: 검색 스니펫/블로그 기반이고, 근거로 보이는 MDPI 논문 원문은 403으로 접근하지 못했습니다. 실험 조건(태그 크기, 카메라, 라이브러리)이 제각각이라 **자릿수 감각으로만** 쓰고, W7에서 본인 하드웨어로 반드시 재측정하세요.
- **pupil-apriltags/dt-apriltags의 2026년 현재 ARM64 wheel 제공 여부**: GitHub 이슈로 과거 Jetson 빌드 실패 사례는 확인했지만, 직접 `pip install`을 aarch64에서 실행해 현재 상태를 검증하지는 못했습니다 → W2에 조기 검증 필수.
- **PID 시작값 `Kp=2.0, Ki=0.5, Kd=0.1`**: 출처에서 "소형 섀시"라고만 언급되고 구체적 모터/기어비가 불명확합니다. 본인 하드웨어에 대한 검증된 값이 아니라 순수 출발점입니다.
- **NVIDIA VPI AprilTag 검출기의 정확도/Python API 성숙도**: PVA가 Orin Nano에 없다는 점은 복수 소스로 확인했지만, VPI의 CPU/GPU 백엔드 AprilTag가 pupil-apriltags/cv2.aruco 대비 정확도나 사용 편의성 면에서 실제로 어떤지는 직접 비교한 자료를 찾지 못했습니다. VPI를 1차 경로에서 제외한 것은 시간 제약을 고려한 제 판단이지 출처 있는 결론이 아닙니다.
- **Roomba Open Interface의 정확한 baud rate/센서 스트리밍 명령**: 공식 OI 스펙 PDF 두 개를 시도했으나 모두 파싱에 실패했습니다(바이너리 인코딩 문제). 본문의 baud rate(115200/57600/19200)는 검색 스니펫이 스펙 문서를 요약한 것을 재인용한 것이라, **실제 배선 전에 소지하고 있는 모델의 공식 OI 스펙 문서를 직접 확인**하시길 권합니다.
