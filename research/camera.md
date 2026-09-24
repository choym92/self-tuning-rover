# 로봇 카메라 선택 & 조명 강건성(lighting robustness) 리서치

대상: GT OMSCS CS7638 Robotics Hardware Challenge (2026-12-10 마감). Jetson Orin Nano Super (8GB) 기반 바퀴 로봇. 컬러 오브젝트(colored object)를 카메라로 검출 → Kalman filter → PID steering. 추후 소형 VLM 실행 가능성 있음.

---

## 결론 먼저 (TL;DR)

**오늘 사야/해야 할 것**
1. **USB UVC 웹캠 (1080p 이하, 4K 아님) — manual exposure/white-balance를 `v4l2-ctl`로 잠글 수 있는 모델.** 이유: 조명 문제의 8할은 auto-exposure/auto-white-balance가 원인이고, 이걸 끄는 게 가장 저비용·고효과 조치. Jetson의 CSI/Argus 카메라 스택보다 UVC 쪽이 표준 v4l2 control로 훨씬 간단하게 잠긴다. ([kernel.org](https://www.kernel.org/doc/html/next/userspace-api/media/v4l/ext-ctrls-camera.html), [laury.dev](https://laury.dev/snippets/manually-control-webcam-using-command-line-linux/))
2. **타겟 오브젝트를 matte(무광) 단색으로 준비, 광택 플라스틱/금속 피하기.** 이유: glare/specular reflection은 색상 자체를 하얗게 날려버려 HSV 임계값을 깨뜨리는 주요 원인. 무광 표면은 diffuse reflection만 반사해 색이 안정적으로 보인다. 비용 거의 0. ([Toshiba Teli](https://www.toshiba-teli.co.jp/en/technology/technical/t0011-Reflection-Polarization.htm))
3. **타겟에 AprilTag(또는 ArUco)를 같이 붙이는 것을 강하게 고려.** 이유: 이 과목이 다루는 Kalman filter/localization/SLAM 문제 설계 방식과 정확히 맞아떨어짐 — 태그 하나로 ID + 3D pose(거리·자세)가 바로 나와서, "색 blob 찾기 → 방향 추정" 같은 불안정한 파이프라인 없이 곧바로 EKF의 measurement로 넣을 수 있다. 컬러 검출과 별개 레이어라서 실패해도 fallback이 된다. ([WPILib AprilTag docs](https://docs.wpilib.org/en/stable/docs/software/vision-processing/apriltag/apriltag-intro.html))

**오늘은 미뤄도 되는 것 (defer)**
- **Depth camera (RealSense D435, OAK-D Lite 등).** 단일 컬러 오브젝트까지의 거리는 태그 크기 기반 monocular distance estimation이나 known-object-size 방식으로 충분히 구할 수 있음. $150–350 추가 비용 + SDK 학습 비용 대비 이득이 낮음. ([Fictionlab 비교글](https://fictionlab.pl/blog/intel-realsense-d435-vs-oak-d-lite-which-depth-camera-for-mobile-robotics-research/))
- **CSI(MIPI) 카메라.** 이론상 CPU/latency 이점이 있지만, Jetson Orin Nano에서 커넥터 어댑터(15핀→22핀), JetPack 6.2+ 이후 `jetson-io.py` 재설정, Argus 기반 노출 제어 등 셋업 리스크가 있다. 소프트웨어 엔지니어가 아니고 마감이 있는 상황에서는 리스크 대비 이득이 작음.
- **Global shutter 카메라.** 실내에서 천천히 움직이는 바퀴 로봇에는 rolling shutter의 기하학적 왜곡("jello effect")이 문제될 정도로 빠른 상대운동이 없음. Global shutter는 드론/고속 트래킹처럼 진짜 빠른 물체에 필요. ([e-con Systems](https://www.e-consystems.com/blog/camera/technology/what-are-global-shutter-and-rolling-shutter-how-to-choose-the-one-that-fits-the-application/))
- **4K 해상도.** 색 threshold도, ViT/VLM도 4K를 못 씀 (아래 6번 참고). USB 대역폭·CPU만 낭비.
- **Polarizing filter, 정식 color calibration rig.** glare가 1차 테스트에서 실제 문제로 확인된 후에 투자할 "2차 대응"으로 미뤄도 됨.

---

## 1. 조명 문제와 해법 (효과/노력 순 랭킹)

HSV color threshold가 깨지는 근본 원인: 카메라의 **auto-exposure**와 **auto white balance(AWB)**가 장면이 바뀔 때마다 같은 물리적 색을 다른 픽셀값으로 매핑하기 때문. 카메라 파라미터(exposure, gain, brightness, white-balance) 설정이 정보 추출 품질에 결정적이라는 지적이 로봇 비전 문헌에도 나온다. ([ResearchGate: Camera parameters auto-adjusting technique for robust robot vision](https://www.researchgate.net/publication/221070058_Camera_parameters_auto-adjusting_technique_for_robust_robot_vision)) Auto-exposure 알고리즘 자체도 조명이 바뀌면 노출이 안정된 이미지 취득을 끊어버려 성능을 떨어뜨린다는 지적도 있음. ([같은 계열 특허 문헌 요약](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7576797))

여기에 더해:
- **Glare/specular reflection**: 매끈한 표면의 정반사는 광원 색(대개 흰색)을 그대로 반사해 물체 고유색 정보를 지워버림. ([Nature Sci Reports](https://www.nature.com/articles/s41598-025-06887-w))
- **실외 태양광 vs 실내 조명**: 색온도가 크게 다르고(태양광은 IR까지 강함, 실내 LED/형광등은 스펙트럼이 좁음), 두 광원이 섞이면 AWB가 계속 흔들림.
- **그림자**: 같은 물체라도 그림자 진 부분은 V(밝기)가 낮아져 HSV 임계값 밖으로 나가거나, 반대로 그림자 자체가 낮은 S/V 영역에서 배경과 섞여 오탐지 유발.

### 랭킹 (효과 대비 노력 낮은 순)

| 순위 | 조치 | 노력 | 효과 |
|---|---|---|---|
| 1 | **`v4l2-ctl`로 exposure·white-balance 수동 고정** | 낮음 (명령어 2~3줄) | 매우 큼 — 근본 원인 제거 |
| 2 | **Matte(무광) 타겟 사용, 광택 표면 회피** | 매우 낮음 (재료 선택) | 큼 — glare 자체를 없앰 |
| 3 | **Diffuse/일정한 조명 확보 (직사광선 피하고, 데모 환경 조명을 고정)** | 낮음~중간 | 큼 — 테스트-데모 간 재현성 확보 |
| 4 | **매 세션(실제 데모 조명 아래) HSV 임계값 재보정** | 낮음~중간 (20–30장 참고 이미지로 평균 HSV 산출 후 H는 ±15, S/V는 ±50 정도 버퍼) | 중간~큼, 단 조명 바뀔 때마다 반복 필요 |
| 5 | **색공간을 HSV→Lab 또는 YCrCb로 전환** | 중간 (코드 변경 + 재보정) | 중간 — 조도 변화에 더 강함 |
| 6 | **저가 LED 링라이트를 카메라 옆에 부착해 타겟을 일정하게 조명** | 낮음~중간, 비용 소액 | 중간~큼 — 주변광 영향 비율을 낮춤 |
| 7 | **Polarizing filter (교차 편광: 광원 + 렌즈 양쪽에 편광판)** | 중간 (부착·정렬 필요, 비용 소액~중간) | 중간 — glare가 실제 문제로 확인된 뒤 투자 |
| 8 | **Retroreflective 타겟 + 전용 LED + 노출을 아주 낮게 설정** (FRC 비전 타겟 방식) | 높음 | 매우 큼 — 조명 변화에 사실상 면역이지만 셋업 복잡 |
| 9 | **정식 color calibration (color checker chart로 카메라 프로파일링)** | 매우 높음 | 크지만 이 프로젝트 스코프엔 과함 |

**v4l2-ctl 실전 명령어** ([laury.dev](https://laury.dev/snippets/manually-control-webcam-using-command-line-linux/), [USB/V4L/UVC Cameras with ROS gist](https://gist.github.com/lucasw/85dc92c9f5146e9d5175a33b49ef4a90)):
```
v4l2-ctl -d /dev/video0 -c exposure_auto=1          # manual exposure 모드 (1=manual, 3=aperture priority가 기본값인 카메라가 많음)
v4l2-ctl -d /dev/video0 -c exposure_absolute=200    # 원하는 노출값 고정
v4l2-ctl -d /dev/video0 -c white_balance_temperature_auto=0
v4l2-ctl -d /dev/video0 -c white_balance_temperature=4500
v4l2-ctl -d /dev/video0 -c focus_auto=0
```
Linux 커널 문서 기준으로 auto exposure/AWB/AF는 각각 독립적인 "lock bit"로 잠글 수 있고, 잠그면 lock을 풀기 전까지 그 값을 유지한다. ([Linux Kernel Camera Control Reference](https://www.kernel.org/doc/html/next/userspace-api/media/v4l/ext-ctrls-camera.html))

주의: 모든 UVC 카메라가 이 컨트롤들을 똑같이 잘 지원하진 않는다. 구매 전/후 `v4l2-ctl --list-ctrls -d /dev/videoX`로 실제 노출·WB 컨트롤이 노출되는지 확인할 것. 일부 UVC 카메라는 최소 노출시간이 프레임레이트에 종속되어 임의로 짧게 못 줄 수도 있다 (Arducam 사례). ([Arducam: Adjust the minimum exposure time](https://docs.arducam.com/UVC-Camera/Adjust-the-minimum-exposure-time/))

**색공간 비교 (검증되지 않은 정밀 수치는 없고, 정성적 비교만 확인됨)**: Lab과 YCrCb가 조도 변화에 대해 HSV보다 시각적으로 유사한 색을 더 잘 뭉쳐준다는 비교 결과가 있으나, HSV는 조절할 축(H 하나)이 적어 튜닝이 쉽다는 실용적 장점이 있다. HSV의 약점은 Hue가 원형(circular)이라 빨간색이 0°/360° 양끝에 걸쳐있어 임계값 로직이 꼬이기 쉽다는 점. ([피부색 검출 HSV vs YCbCr 비교 논문](https://www.researchgate.net/publication/283185121_Comparative_Study_of_Skin_Color_Detection_and_Segmentation_in_HSV_and_YCbCr_Color_Space), [LearnOpenCV: Color spaces in OpenCV](https://learnopencv.com/color-spaces-in-opencv-cpp-python/))

**Glare 대응 원리**: 정반사(specular)는 입사광의 편광을 유지하는 반면 diffuse 반사는 편광을 흩뜨린다. 광원과 렌즈에 서로 직교하는 편광판을 달면(cross-polarization) 정반사 성분만 걸러내고 물체 고유색(diffuse) 성분만 남길 수 있다. ([Toshiba Teli 기술문서](https://www.toshiba-teli.co.jp/en/technology/technical/t0011-Reflection-Polarization.htm), [arXiv:1811.02608](https://arxiv.org/pdf/1811.02608))

---

## 2. 마커 (AprilTag / ArUco) — Kalman filter·localization 관점

**왜 로봇공학 코스가 fiducial marker를 좋아하는가**: AprilTag은 미시간대에서 "많은 응용에 쓸 수 있는 저오버헤드·고정확도 localization"을 목표로 개발됐다. 태그 하나를 인식하면 (1) 고유 ID, (2) 필드/환경 내 알려진 위치, (3) 카메라 대비 3D pose(거리+자세)까지 한 번에 얻는다. 이 값을 바로 WPILib류 pose-estimation(=Kalman filter 기반 fusion) 클래스의 measurement로 넣을 수 있다. ([WPILib: What Are AprilTags?](https://docs.wpilib.org/en/stable/docs/software/vision-processing/apriltag/apriltag-intro.html))

이게 왜 CS7638의 Kalman filter/particle filter/SLAM 커리큘럼과 잘 맞는가: 고전적 landmark-based localization(알려진 위치의 landmark를 관측해 자기 위치를 갱신) 문제를 그대로 구현할 수 있게 해준다. 즉 "컬러 blob 중심점 → 대략적 방향"이라는 노이즈 심한 관측 대신, "태그 ID + range/bearing(혹은 풀 pose)"라는 훨씬 깨끗한 관측을 EKF에 넣을 수 있다.

**강건성(robustness)**: 두 방식 모두 error-correction 코딩이 있어 부분 가림(occlusion)과 조명 변화에 어느 정도 강하다. 비교 결과, AprilTag이 ArUco보다 오검출(false positive)이 적고 먼 거리·기운 각도에서도 검출률이 높다는 평가가 있는 반면, ArUco는 조명 간섭에 대한 저항성이 낮다는 평가도 있다. 다만 AprilTag도 저해상도나 harsh lighting에서는 pose의 회전(rotation) 오차가 커질 수 있다 — 주된 오차원은 카메라 대비 태그의 각도. ([Robotics Knowledgebase: Comparison of Fiducial Markers](https://roboticsknowledgebase.com/wiki/sensing/fiducial-markers/), [it-jim: Fiducial Markers Overview](https://www.it-jim.com/blog/fiducial-markers-types/))

**속도**: 일반적으로 두 방식 모두 실시간(~30fps) 검출이 가능하다고 알려져 있으나, 계산 자원이 한정된 임베디드 환경에서는 ArUco가 AprilTag보다 다소 더 효율적이라는 평가가 있다. ([검색 요약, Robotics Knowledgebase 계열](https://roboticsknowledgebase.com/wiki/sensing/fiducial-markers/)) AprilTag 구현체(C 라이브러리)는 `quad_decimate` 파라미터로 속도-검출거리 트레이드오프를 조절할 수 있고, 코어를 늘리면 더 빨라진다. ([AprilRobotics/apriltag GitHub](https://github.com/AprilRobotics/apriltag))

- **검증 못한 부분**: NVIDIA VPI(하드웨어 가속 AprilTag)가 Jetson AGX Orin/Orin NX급에서 720p 기준 116–178fps를 낸다는 2차 출처 요약을 찾았으나, VPI 공식 문서 페이지를 직접 열어봤을 때 표에 실제 수치가 드러나지 않아 1차 소스로 확인하지 못했다. Orin Nano Super 전용 수치는 못 찾음 — 실측 필요. ([NVIDIA VPI AprilTag docs](https://docs.nvidia.com/vpi/algo_apriltags.html))
- Raspberry Pi급 CPU에서의 AprilTag 정확한 fps 수치도 검색에서 확인하지 못했다 (AprilTag이 RPi용으로 빌드된다는 사실만 확인). Jetson Orin Nano Super는 RPi보다 훨씬 강력하므로 CPU-only 실행도 충분히 실시간에 들어올 가능성이 높지만 숫자 근거는 없음 — 플래그.

**결론**: 색 threshold 파이프라인과 AprilTag/ArUco를 병행(타겟에 태그 부착)하면, 조명 강건성 문제를 상당 부분 marker의 error-correction과 binary thresholding(태그는 흑백 패턴이라 컬러보다 조명 변화에 원래 덜 민감함)으로 우회하면서, 동시에 EKF에 넣을 깨끗한 range/pose measurement까지 얻는다 — Hardware Challenge의 "카메라 센서 읽기 + Kalman filter" 요구사항에 정확히 들어맞는 조합.

---

## 3. 카메라 스펙 — 진짜 중요한 것 vs 돈 낭비

**돈 쓸 가치 있는 것**
- **UVC manual exposure/WB 지원 여부.** 위 1번 문제의 근본 해법이 여기 달려있음. 스펙시트에 "UVC 1.5", "exposure control" 명시 여부, 또는 구매 전 리뷰/포럼에서 v4l2-ctl 호환성 확인.
- **MJPEG 지원 (특정 해상도·프레임레이트에서).** YUYV(raw) 1080p@30fps는 최대 ~180Mb/s 대역폭이 필요한 반면 MJPEG는 보통 ≤1.5Mb/s. 레이턴시도 MJPEG가 <50ms급으로 YUYV(150ms+)보다 낮고, CPU 부하도 MJPEG 5–12% vs YUYV 35–55%로 훨씬 가볍다 (JPEG 하드웨어 디코더가 널리 보급돼 있기 때문). Jetson의 제한된 CPU를 Kalman filter/PID/VLM에 더 쓰려면 MJPEG 쪽이 유리. ([Kiloview: USB Audio & Video](https://www.kiloview.com/en/usb-audio-video-whats-actually-streaming-through-your-usb-webcam/), [Krieer: MJPEG vs YUY2](https://www.krieer.com/blog/detail/mjpeg-vs-yuy2-usb-camera-module))
- **적절한 FOV** (방 안에서 로봇이 움직일 때 타겟을 화면 안에 유지할 수 있는 화각). 다만 구체적 권장 각도 수치는 이번 검색에서 확인하지 못함 — 실측/실험 필요.

**돈 낭비인 것**
- **4K/고해상도 센서.** 아래 6번 참조 — ViT/VLM은 224~384px급으로 리사이즈하고, HSV threshold도 고해상도가 딱히 필요 없음(오히려 대역폭·연산만 늘어남).
- **Global shutter (프리미엄 가격).** 실내 저속 바퀴 로봇에는 rolling shutter로 충분 — rolling shutter 왜곡("jello effect")은 빠르게 움직이는 피사체에서 문제가 되고, motion blur는 셔터 방식과 무관하게 노출시간을 짧게 하면 해결된다. ([e-con Systems: Rolling shutter artifacts vs motion blur](https://www.e-consystems.com/blog/camera/technology/differences-between-rolling-shutter-artifacts-and-motion-blur/), [RidgeRun: Camera Shutter Technology](https://www.ridgerun.com/post/camera-shutter-technology))
- **HDR/WDR 고급 센서.** 실내 통제된 조명(데모/코스 환경)에서는 exposure 고정만으로 충분한 경우가 많음. 역광 창문이 있는 환경이라면 고려할 만하지만, 이번 프로젝트에서는 후순위.

---

## 4. Jetson Orin Nano — USB UVC vs CSI, 구체적 주의사항

**CSI 커넥터 규격**: Jetson Orin 시리즈는 22-pin, 0.5mm pitch 커넥터(TE Connectivity)를 사용한다. ([Arducam: Jetson Camera Connector Type/Pinout](https://docs.arducam.com/Nvidia-Jetson-Camera/type-and-pinout-mipi-csi-2/))

**출고 시 지원 센서**: Jetson에는 Raspberry Pi Camera V2.1(IMX219)용 드라이버가 내장돼 있다. IMX477(Raspberry Pi HQ Camera 계열)도 내장 드라이버로 지원된다는 정보를 JetsonHacks 글에서 확인했다. 반면 **IMX708(진짜 Raspberry Pi Camera Module 3)은 기본 드라이버에 없고, RidgeRun이 개발한 별도 드라이버를 설치해야 동작**한다는 것이 RidgeRun 위키에 명시돼 있다. ([RidgeRun: IMX708 카메라 지원](https://developer.ridgerun.com/wiki/index.php/NVIDIA_Jetson_Orin_Nano/Camera_Sensors_Support/IMX708), [RidgeRun: IMX219](https://developer.ridgerun.com/wiki/index.php/NVIDIA_Jetson_Orin_Nano/Camera_Sensors_Support/IMX219))

- **주의(불일치 발견)**: JetsonHacks 글은 "Raspberry Pi V2와 V3 카메라"를 다루면서 내장 드라이버가 "IMX219와 IMX477"이라고 적었는데, 실제 Raspberry Pi Camera Module 3의 센서는 IMX708이다. RidgeRun 쪽 출처가 더 센서를 특정해서 설명하므로, **IMX708(RPi Cam v3)은 기본 미지원, 별도 드라이버 필요**로 보는 게 더 안전하다. 구매 전 정확한 센서명(IMX219/IMX477/IMX708)을 확인할 것. ([JetsonHacks 원문](https://jetsonhacks.com/2025/03/04/jetson-orin-nano-super-with-the-raspberry-pi-v2-and-v3-cameras/))

**커넥터/케이블 캐비어트**:
- Raspberry Pi V2.1 카메라는 **15-pin** 커넥터를 쓰기 때문에 Jetson의 **22-pin** CSI 커넥터에 연결하려면 어댑터 케이블이 필요하다.
- 15-pin 커넥터가 핀 간격이 달라 오히려 22-pin 어댑터보다 물리적으로 더 넓다는 점도 언급됨.
- 커넥터 자체가 작고 튼튼하지 않아 다룰 때 주의가 필요.
- **JetPack 6.2부터는 카메라 연결 전 `jetson-io.py` 유틸리티로 커넥터를 수동 설정**해야 한다 (`sudo python jetson-io.py` → "Configure Jetson 24 pin CSI Connector" → "Configure for compatible hardware" → IMX219/IMX477 선택 → 재부팅 → `/dev/video*` 확인). 이전 JetPack 버전은 자동 인식됐던 것과 달리 추가 스텝이 생겼다. ([JetsonHacks](https://jetsonhacks.com/2025/03/04/jetson-orin-nano-super-with-the-raspberry-pi-v2-and-v3-cameras/))

**CPU 부하/레이턴시**: 이론적으로는 CSI가 유리하다 — MIPI CSI-2는 USB 오버헤드 없이 Jetson ISP에 직결되고, ISP가 AE/AWB/노이즈감소를 하드웨어로 처리해 CPU를 아낀다는 설명이 일반적이다. **그러나 Jetson 개발자 포럼의 실측 경험담은 엇갈린다**: 한 사용자는 CSI 카메라 지연이 GStreamer 파이프라인에서 USB보다 훨씬 컸다고 보고했고(예: CSI 500ms vs USB 150ms, CSI가 CPU도 더 먹음), 다른 사례는 GPU 추론과 결합했을 때 CSI가 최대 2초 지연이 발생한 반면 USB는 거의 무지연이었다고 보고했다. 즉 **실제 지연은 인터페이스 자체보다 GStreamer/nvarguscamerasrc 파이프라인 설정(버퍼링 등)에 더 좌우되는 경향**이 있다. ([NVIDIA Developer Forums: High Latency with CSI Camera vs USB](https://forums.developer.nvidia.com/t/high-latency-with-csi-camera-using-gstreamer-compared-to-usb-camera/273697), [CSI Camera Latency on Jetson Nano](https://forums.developer.nvidia.com/t/csi-camera-latency-on-jetson-nano/164644))

**결론**: 소프트웨어 엔지니어가 아니고 12월 마감이 있는 상황에서는, exposure/WB를 표준 `v4l2-ctl` UVC 컨트롤로 바로 잠글 수 있는 **USB UVC 웹캠이 셋업 리스크가 훨씬 낮다.** CSI는 대역폭·CPU 이점이 있지만 커넥터 어댑터, jetson-io 설정, Argus 기반 노출 제어(표준 v4l2 UVC 컨트롤과 다름, [Jetson Linux V4L2Argus API 참고](https://docs.nvidia.com/jetson/archives/r35.5.0/ApiReference/group__V4L2Argus.html))라는 추가 학습 곡선이 있다.

---

## 5. 깊이 카메라 — 언제 필요한가

| | Intel RealSense D435 | Luxonis OAK-D Lite |
|---|---|---|
| 방식 | Active IR stereo + 전용 depth ASIC | Passive stereo + Myriad X VPU(온보드 신경망 추론) |
| 가격대 (Fictionlab 추정) | 약 $300–350 | 약 $150–180 |
| 강점 | 실내에서 0.3–3m 밀집 깊이, 무늬 없는(textureless) 표면에서도 안정적, ROS2 공식 드라이버로 plug-and-play | 저렴, 카메라 자체에서 AI 추론 가능(호스트 연산 절약), 실외에서 IR 방식보다 햇빛에 덜 취약 |
| 약점 | 가격, 실외에서 IR 패턴이 햇빛에 묻힐 수 있음 | 평면(빈 벽 등)에서 취약, 파이프라인 그래프/NN 배포 이해 필요해 설정 복잡도 ↑ |

([Fictionlab: RealSense D435 vs OAK-D Lite](https://fictionlab.pl/blog/intel-realsense-d435-vs-oak-d-lite-which-depth-camera-for-mobile-robotics-research/))

**이번 프로젝트에 필요한가**: 아니오, 1차적으로는 불필요. Hardware Challenge 요구사항("센서 읽기 + 액추에이터 구동 + 알고리즘 1개")과 계획("컬러 오브젝트 → Kalman filter → PID")은 단안 카메라만으로 충분히 만족된다 — 거리는 (a) AprilTag처럼 알려진 크기의 마커의 픽셀 크기로 역산하거나, (b) 알려진 물체 크기 기반 pinhole distance estimation으로 구할 수 있음. 깊이 카메라가 정당화되는 경우는: 타겟이 알려진 크기/마커가 아닌 임의 형상일 때, 조밀한 장애물 회피나 실제 SLAM 매핑(단일 landmark localization을 넘어서는)이 필요할 때, 또는 마감 이후 여유 시간에 실험적으로 확장할 때. 지금 단계에서는 $150–350와 SDK(RealSense SDK 또는 DepthAI) 학습 비용 대비 이득이 낮다.

---

## 6. Vision model이 실제로 쓰는 입력 해상도 — 4K는 낭비인가

Vision Transformer(ViT) 계열은 보통 **224×224**로 사전학습(pretrain)되고, fine-tuning 시 더 높은 해상도(예: **384×384**)를 쓰면 성능이 좋아진다는 것이 공식 문서에 나온다. patch size는 16×16이 흔하고(예: `vit-base-patch16-224`), ViT-H/14는 336 해상도로 평가되기도 한다. ([HuggingFace ViT docs](https://huggingface.co/docs/transformers/model_doc/vit), [google/vit-base-patch32-384](https://huggingface.co/google/vit-base-patch32-384))

즉 대부분의 ViT/VLM 이미지 인코더는 입력을 **224~384px급으로 리사이즈**해서 처리한다. 이 범위를 넘는 해상도(1024px대 타일링을 쓰는 일부 최신 대형 VLM 등)도 존재한다고 알려져 있지만, **이번 검색에서 구체적인 소스로 확인하지는 못했다** — 플래그. Jetson에서 돌릴 법한 소형 온디바이스 VLM(수백M~수B 파라미터급)이 정확히 몇 px를 쓰는지도 검색으로 확정하지 못함 — 실제 채택할 모델의 config를 직접 확인 필요.

**결론**: 4K(3840×2160) 웹캠을 사도 VLM 인코더 앞단에서 어차피 몇백 px로 다운샘플링되므로 해상도 이득은 사실상 없고, 대신 USB 대역폭·CPU 디코딩 부하만 늘어난다(3번 MJPEG/YUYV 비교 참고). 고해상도가 실제로 의미 있는 경우는 classical CV에서 먼 거리의 작은 타겟(예: AprilTag 코너)의 sub-pixel 정확도가 필요할 때 정도 — 이 프로젝트라면 1280×720 정도면 충분할 가능성이 높다(단, 실측 권장).

---

## 검증하지 못한 항목 (Flag)

- NVIDIA VPI AprilTag의 Orin Nano Super 전용 fps 수치 (1차 문서에서 표 데이터 미확인)
- Raspberry Pi급 CPU에서의 AprilTag 정확한 fps
- 특정 UVC 웹캠 모델(예: Logitech 계열)의 manual exposure 지원 여부 — 이번 리서치에서 특정 모델을 소스로 검증하지 못했으므로, 구매 전 반드시 `v4l2-ctl --list-ctrls`로 직접 확인 권장
- 이 로봇/방에 적합한 구체적 FOV(화각) 권장값
- 최신 대형 VLM(1024px 타일링 등)의 정확한 입력 해상도 스펙
- JetsonHacks 글의 "IMX477 = Raspberry Pi V3" 표기와 RidgeRun의 "IMX708 = Raspberry Pi Camera Module 3, 별도 드라이버 필요" 표기 사이의 불일치 — 센서명을 직접 확인 후 구매할 것

---

## 출처 전체 목록

- [Linux Kernel: Camera Control Reference (lock bits, exposure/WB controls)](https://www.kernel.org/doc/html/next/userspace-api/media/v4l/ext-ctrls-camera.html)
- [laury.dev: Manually control a webcam using the command line on Linux](https://laury.dev/snippets/manually-control-webcam-using-command-line-linux/)
- [USB/V4L/UVC Cameras with ROS (gist)](https://gist.github.com/lucasw/85dc92c9f5146e9d5175a33b49ef4a90)
- [Arducam: Adjust the minimum exposure time (UVC)](https://docs.arducam.com/UVC-Camera/Adjust-the-minimum-exposure-time/)
- [ResearchGate: Camera parameters auto-adjusting technique for robust robot vision](https://www.researchgate.net/publication/221070058_Camera_parameters_auto-adjusting_technique_for_robust_robot_vision)
- [Comparative Study of Skin Color Detection: HSV vs YCbCr](https://www.researchgate.net/publication/283185121_Comparative_Study_of_Skin_Color_Detection_and_Segmentation_in_HSV_and_YCbCr_Color_Space)
- [LearnOpenCV: Color spaces in OpenCV (C++/Python)](https://learnopencv.com/color-spaces-in-opencv-cpp-python/)
- [PhotonVision Docs: Thresholding](https://docs.photonvision.org/en/latest/docs/reflectiveAndShape/thresholding.html)
- [Toshiba Teli: Reflection & polarization of light in machine vision](https://www.toshiba-teli.co.jp/en/technology/technical/t0011-Reflection-Polarization.htm)
- [arXiv:1811.02608 — Embedded polarizing filters to separate diffuse and specular reflection](https://arxiv.org/pdf/1811.02608)
- [Nature Scientific Reports: Glare suppressed 3D mapping via linear polarization](https://www.nature.com/articles/s41598-025-06887-w)
- [Robotics Knowledgebase: Comparison of Fiducial Markers](https://roboticsknowledgebase.com/wiki/sensing/fiducial-markers/)
- [it-jim: Fiducial Markers Overview, Types, Use Cases, Comparison](https://www.it-jim.com/blog/fiducial-markers-types/)
- [WPILib: What Are AprilTags?](https://docs.wpilib.org/en/stable/docs/software/vision-processing/apriltag/apriltag-intro.html)
- [AprilRobotics/apriltag GitHub (quad_decimate 등 성능 파라미터)](https://github.com/AprilRobotics/apriltag)
- [NVIDIA VPI: AprilTag Detector and Pose Estimator](https://docs.nvidia.com/vpi/algo_apriltags.html)
- [RidgeRun Wiki: Jetson Orin Nano Camera Sensors Support — IMX219](https://developer.ridgerun.com/wiki/index.php/NVIDIA_Jetson_Orin_Nano/Camera_Sensors_Support/IMX219)
- [RidgeRun Wiki: Jetson Orin Nano Camera Sensors Support — IMX708](https://developer.ridgerun.com/wiki/index.php/NVIDIA_Jetson_Orin_Nano/Camera_Sensors_Support/IMX708)
- [Arducam: NVIDIA Jetson Camera Connector Type and Pinout (MIPI CSI-2)](https://docs.arducam.com/Nvidia-Jetson-Camera/type-and-pinout-mipi-csi-2/)
- [JetsonHacks: Jetson Orin Nano Super with the Raspberry Pi V2 and V3 Cameras](https://jetsonhacks.com/2025/03/04/jetson-orin-nano-super-with-the-raspberry-pi-v2-and-v3-cameras/)
- [NVIDIA Jetson Linux API Reference: V4L2Argus](https://docs.nvidia.com/jetson/archives/r35.5.0/ApiReference/group__V4L2Argus.html)
- [NVIDIA Developer Forums: High Latency with CSI Camera Using GStreamer Compared to USB Camera](https://forums.developer.nvidia.com/t/high-latency-with-csi-camera-using-gstreamer-compared-to-usb-camera/273697)
- [NVIDIA Developer Forums: CSI Camera Latency on Jetson Nano](https://forums.developer.nvidia.com/t/csi-camera-latency-on-jetson-nano/164644)
- [RidgeRun: Camera Shutter Technology (Rolling vs Global)](https://www.ridgerun.com/post/camera-shutter-technology)
- [e-con Systems: Differences between rolling shutter artifacts and motion blur](https://www.e-consystems.com/blog/camera/technology/differences-between-rolling-shutter-artifacts-and-motion-blur/)
- [e-con Systems: What are Global Shutter and Rolling Shutter cameras](https://www.e-consystems.com/blog/camera/technology/what-are-global-shutter-and-rolling-shutter-how-to-choose-the-one-that-fits-the-application/)
- [Kiloview: USB Audio & Video — What's Actually Streaming Through Your USB Webcam?](https://www.kiloview.com/en/usb-audio-video-whats-actually-streaming-through-your-usb-webcam/)
- [Krieer: MJPEG vs YUY2 — Which Is Better for USB Camera Modules?](https://www.krieer.com/blog/detail/mjpeg-vs-yuy2-usb-camera-module)
- [Fictionlab: Intel RealSense D435 vs OAK-D Lite — Which Depth Camera for Mobile Robotics Research](https://fictionlab.pl/blog/intel-realsense-d435-vs-oak-d-lite-which-depth-camera-for-mobile-robotics-research/)
- [HuggingFace: Vision Transformer (ViT) docs](https://huggingface.co/docs/transformers/model_doc/vit)
- [HuggingFace: google/vit-base-patch32-384](https://huggingface.co/google/vit-base-patch32-384)
