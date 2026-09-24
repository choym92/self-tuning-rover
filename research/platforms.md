# GT OMSCS CS7638 Robotics Hardware Challenge — 로봇 플랫폼 서베이

**작성일**: 2026-09-22 (가격은 조사 시점 기준 근사치이며 재고/환율에 따라 변동될 수 있음)
**전제 조건**: Jetson Orin Nano Super (8GB) dev kit 별도 구매 확정, Mac (M5 Pro 64GB) 보유, wheeled differential-drive 선호 + 추후 소형 arm 확장 고려, graded task는 classical algorithm(Kalman filter / particle filter / PID / SLAM / search+smoothing) 중 1개, VLM/LLM은 보너스(sentdex 감성).

---

## TL;DR — 추천 순위 3개

### 1위 (최종 추천): DIY 루트 — chassis + quadrature encoder DC motor + motor driver + IMU
**이유**: 엔코더 유무를 직접 선택하므로 "엔코더 있음"이 100% 보장되는 유일한 옵션. 이미 구매 예정인 Jetson Orin Nano Super를 그대로 메인 컴퓨터로 쓰고 추가 보드 구매가 필요 없음. 소프트웨어가 처음부터 끝까지 내 Python/C++ 코드이므로 PID·KF·particle filter를 "from scratch"로 구현하는 과제 요구사항과 정확히 맞음. 비용도 LiDAR 없이 약 $150~250, LiDAR 포함해도 $330~470 수준으로 완제품 키트보다 저렴하다.
**트레이드오프**: 조립·배선·캘리브레이션을 전부 직접 해야 하고, 통합된 벤더 튜토리얼이 없어 초기 디버깅(모터 드라이버 극성, encoder tick 카운트, I2C 배선 등) 시간이 가장 많이 든다. 실시간 encoder 카운팅/PID는 Jetson의 Linux GPIO보다 저가 마이크로컨트롤러(Arduino Nano/ESP32)에 맡기고 Jetson과는 USB serial로 통신하는 구조를 권장 — 이는 아래 2위 키트가 이미 채택한 아키텍처이기도 하다.

### 2위: Waveshare JetBot ROS AI Kit (Pro/Dual-Controller 버전, RP2040 + Jetson)
**이유**: 조사한 완제품 키트 중 "AB상 홀 엔코더 + PID 폐루프 속도제어 + wheel odometry 출력" 및 "내장 IMU"가 벤더 페이지에 가장 명확하게 명시된 키트다. RP2040 마이크로컨트롤러가 모터/엔코더의 실시간 제어를 전담하고 Jetson은 AI/비전을 담당하는 dual-controller 구조라 DIY로 직접 만들려는 아키텍처를 이미 패키징해 놓았다고 볼 수 있다.
**트레이드오프**: 이 키트는 자체 Jetson Nano 4GB Dev Kit(구형)를 묶음으로 판매하는 것으로 보여, 이미 구매한 Orin Nano Super와 별개로 보드가 하나 더 생길 가능성이 있다. Orin Nano Super와의 호환 여부(모듈만 교체 가능한지)는 waveshare.com 공식 페이지가 자동 접근을 차단해 직접 확인하지 못했다 — **구매 전 Waveshare에 직접 문의 필요**. 정확한 가격도 공식 페이지에서 확인하지 못해 유사 제품 시세로 추정했다.

### 3위: Yahboom ROSMASTER X3 (Plus 아닌 기본형)
**이유**: 조사한 키트 중 유일하게 벤더 페이지에 "Jetson NANO 4GB / Orin NANO SUPER / Orin NX SUPER / Raspberry Pi 5" 중 선택 가능하다고 명시되어 있어, 이미 산 Orin Nano Super를 재사용할 가능성이 가장 높다(단, 이 옵션이 "보드 포함" SKU인지 "보드 미포함(BYO)" SKU인지는 확인 필요). ROS2 기반이라 Python 커스텀 제어 루프 작성이 자유롭고, 커뮤니티/튜토리얼도 어느 정도 갖춰져 있다.
**트레이드오프**: 정작 핵심 기준인 **엔코더 탑재 여부가 벤더 페이지에 명시적으로 나오지 않음** — Yahboom ROS 라인업이 관행적으로 encoder gear motor("520 motor")를 쓰는 경향은 있지만 확정하지 못했다. 가격도 $659(세일가, 정가 $1,189)로 DIY 대비 3~4배 비싸고, 리뷰상 문서화 품질이 사람마다 평가가 갈린다("초보자에겐 불친절" 의견 존재).

---

## 비교표

| 플랫폼 | 가격 (약, 출처/날짜) | 엔코더 | IMU | 카메라 | LiDAR | 대상 보드 | SW 개방성 | 조립 난이도 |
|---|---|---|---|---|---|---|---|---|
| **DIY** (chassis+encoder motor+driver+IMU) | ~$150–250 (LiDAR 추가 시 +$180–220) — Pololu/DFRobot/Adafruit, 2026-09 | **있음** (직접 선택, 확정) | 별도 구매 (예: BNO055 ~$16–30) | 별도 (USB웹캠/Jetson CSI) | 추가 가능 (RPLidar A1 ~$180–220) | Jetson Orin Nano Super (보유 중인 것 그대로 사용) | 완전 개방 (Python/C++ 직접 작성) | 높음 (배선·캘리브레이션 직접) |
| **Waveshare JetBot ROS AI Kit** (Pro, RP2040+Jetson) | 미확정, 유사 제품 시세로 $300–400대 추정 — waveshare.com (접근 차단, 미확인) | **있음** (11선 AB상 홀 엔코더, 벤더 명시) | **있음** (내장) | 있음 | 일부 문구에 "Lidar Mapping" 언급 있으나 표준 포함 여부 미확인 | Jetson Nano 4GB 번들 (Orin Nano Super 호환 **미확인**) | 개방적 (ROS, Python, dual-controller) | 중간 (벤더 튜토리얼 있음, 리뷰 엇갈림) |
| **Waveshare JetBot AI Kit** (기본/non-ROS, 오리지널 NVIDIA JetBot) | ~$272 — sunsky-online(3rd-party), 2026-09 | **없음** (오픈루프 설계) | 없음 | 있음 | 없음 | Jetson Nano | 개방 (NVIDIA JetBot repo) | 낮음 |
| **Yahboom ROSMASTER X3** | $659 세일가 (정가 $1,189) — yahboom.net, 2026-09 | 명시 안 됨 — 제품군 특성상 encoder motor 가능성 있으나 **미확인** | 명시 안 됨 (**미확인**) | 있음 | 본체엔 없음(옵션 상이) | Jetson Nano 4GB / Orin Nano Super / Orin NX Super / RPi5 중 택1 (보드 포함 여부 확인 필요) | 개방적 (ROS2, Python) | 중간~높음 (리뷰 엇갈림) |
| **Yahboom ROSMASTER X3 PLUS** | $1,229 세일가 (정가 $1,729) — yahboom.net, 2026-09 | 상동, 미확인 | 미확인 | 있음 (뎁스카메라) | **있음** (A1M8, 삼각측량, 0.15–12m, 8K 샘플링) | 상동 | 상동 | 상동 (부품 더 많아 난이도 ↑) |
| **Hiwonder JetAuto (Standard)** | $1,016.99 (Jetson Nano 4GB 버전) — ozrobotics, 2026-09 | **있음** ("high-performance encoder motor" 명시, JetAuto Pro는 "magnetic encoding motors") | 명시 안 됨 (**미확인**) | 있음 (3D 뎁스카메라) | **있음** | Jetson Nano / Orin Nano / Orin NX 중 선택 가능 언급 (SKU별 보드 포함 여부 확인 필요) | 개방적 (ROS1/ROS2, TensorRT) | 중간 (벤더 튜토리얼 제공) |
| **Freenove 4WD Smart Car Kit** | $69.99 (Pi 미포함) — store.freenove.com, 2026-09 | **없음** | 없음 | 있음 | 없음 | Raspberry Pi 3B+/4B/5 전용, **Jetson 미언급/사실상 미지원** | 오픈소스 Python 코드 제공 (RPi.GPIO 기반) | 낮음 (조립 쉬움, 디지털 튜토리얼 우수, 종이 매뉴얼 없음) |
| **LeRobot SO-101 arm** | $499 완제품 키트 (DIY 소싱 시 ~$300) — roboticscenter.ai, 2026-09 | 관절 서보(Feetech STS3215) 내부 위치 피드백 있음, 단 바퀴가 없어 "wheel encoder" 해당 없음 | 무관 | 별도 구매 | 무관 | Jetson 등 USB serial 가능한 컴퓨터면 무관 | 완전 개방 (HuggingFace LeRobot) | 낮음 (~60분, 나사 조립만) |
| **LeRobot LeKiwi 모바일베이스** | $179 (베이스만) — seeedstudio.com, 2026-09. SO-ARM101/RPi5/카메라 등 추가 시 총액 **미검증** (대략 $700–900대 추정) | 불명확 — 서보 내부 피드백은 있으나 전통적 quadrature wheel encoder 여부는 페이지에 명시 안 됨 | 미확인 (언급 없음) | 별도 구매 (RGB 카메라 2대 권장) | 무관 | **Raspberry Pi 5** 대상 (Jetson 아님) | 개방적(LeRobot Python)이나 서보 자체 내장 PID 때문에 "직접 PID 구현"엔 제약 | 문서화상 조립 난이도 명시 안 됨 (커뮤니티 평가로는 중간) |

---

## 후보별 상세 노트

### 1. NVIDIA JetBot 계열 (Waveshare 제작)
- **JetBot AI Kit (기본, non-ROS)**: 오리지널 NVIDIA JetBot 오픈소스 설계를 그대로 따름 — 카메라 기반 오픈루프 제어만 지원, **엔코더도 IMU도 없음**. 가격은 3rd-party 리셀러 기준 ~$272. Jetson Nano(구형) 대상.
- **JetBot ROS AI Kit (Pro/Dual-Controller)**: RP2040 마이크로컨트롤러가 모터를 전담하고 "11선 AB상 홀 스피드 엔코더"로 PID 폐루프 속도 제어 + wheel odometry 계산을 지원, IMU 내장. 구조상 KF(encoder odometry + IMU) 구현에 가장 적합한 완제품이지만, 번들되는 Jetson Nano Dev Kit 4GB가 이미 산 Orin Nano Super와 별개일 가능성 — 확인 필요.

### 2. Yahboom Jetson 로봇 키트 (ROSMASTER 시리즈)
- ROSMASTER X3/X3 PLUS는 "520 고출력 모터", 음성인식 모듈, HD 7인치 디스플레이 등을 포함. X3 PLUS는 A1M8 LiDAR와 6DOF 로봇팔까지 포함해 SLAM/A* 실습까지 확장 가능하지만 가격이 뛴다($1,229 세일가).
- Jetson NANO 4GB / Orin NANO SUPER / Orin NX SUPER / RPi5 중 컴퓨팅 보드를 선택할 수 있다고 명시되어 있어 **Jetson 세대 호환성 측면에서는 가장 유연**하다. 단, 엔코더·IMU 스펙은 페이지에서 명시적으로 확인되지 않아 별도 문의가 필요하다.
- 리뷰: 한 사용자는 "기술지원과 문서화가 인간적"이라 평가했지만 다른 사용자는 "문서가 충분히 명확하지 않다", "어느 정도 기초가 있는 사용자에게 적합"이라 평가 — 완전 초보에게는 다소 진입장벽이 있을 수 있음.

### 3. Hiwonder Jetson 로봇 키트 (JetAuto / JetAuto Pro)
- JetAuto Standard(Jetson Nano 4GB 버전) 기준 $1,016.99. Mecanum wheel 서스펜션, LiDAR, 3D 뎁스카메라, 마이크 어레이, HD 디스플레이 포함.
- 일반 제품군 소개에서 "high-performance encoder motor"(JetAuto), "magnetic encoding motors"(JetAuto Pro)라는 표현이 명확히 확인됨 → **엔코더 있음으로 판단**. 다만 개별 제품 상세 페이지에서 IMU 스펙은 확인하지 못함.
- ROS1/ROS2 지원, TensorRT 가속 딥러닝 프레임워크 통합, 커스텀 코드 삽입 가능 — 소프트웨어 개방성은 양호. Jetson Nano/Orin Nano/Orin NX 버전이 있다고 하나 정확히 어떤 SKU가 Orin Nano Super와 호환되는지, 보드가 포함인지 별매인지는 확인 필요.

### 4. Freenove 4WD Smart Car Kit (코스 스태프 추천 키트)
- $69.99 (Raspberry Pi, 배터리 별매), Raspberry Pi 3B+/4B/5 전용 설계. **엔코더 없음, IMU 없음** — 초음파 센서, 카메라(라인/얼굴 트래킹), 서보 팬틸트로 구성된 저가 입문용 로봇.
- **Jetson 호환성**: 공식 자료에서 Jetson 언급을 찾지 못함. 모터 드라이버 보드(PCA9685 기반 PWM 등)는 I2C를 쓰므로 배선 자체는 Jetson 40핀 헤더에도 물리적으로 연결 가능성이 있지만, Freenove가 제공하는 Python 구동 라이브러리는 RPi.GPIO/Raspberry Pi OS를 전제로 작성되어 있어 Jetson.GPIO 환경에 맞게 **직접 다시 작성**해야 한다. 사실상 코스 스태프가 의도한 경로는 "Raspberry Pi를 따로 사서 쓰라"는 쪽에 가까워 보인다.
- 소스코드는 완전 공개(Python), 조립 난이도 낮음, 디지털 튜토리얼(웹 링크, GitHub) 품질은 Freenove 쪽이 정평이 나 있으나 종이 매뉴얼은 없음.
- 결론: 가격은 가장 싸지만 **엔코더가 없어 KF 과제엔 부적합**, Jetson 생태계와도 어긋난다 (아래 "피해야 할 것" 참고).

### 5. LeRobot 생태계 (SO-101 arm / LeKiwi)
- **SO-101 arm**: 완제품 키트 $499 (부품 직접 소싱 시 ~$300, 저가형 구성은 $100대부터 시작한다는 자료도 있음 — 구성에 따라 편차 큼). Feetech STS3215 시리얼 버스 서보 사용, HuggingFace LeRobot과 네이티브 연동. 조립 ~60분, 난이도 낮음, 문서화 매우 우수(허깅페이스 커뮤니티+영상자료 풍부, sentdex st일 콘텐츠와 결이 맞음). 다만 **바퀴가 없는 팔이라 differential-drive odometry/KF 과제와 직접 관련 없음** — "actuator 구동" 요건은 채우지만 주력 과제 플랫폼으로는 부적합, 나중에 모바일 베이스 위에 얹는 확장용으로 고려할 만함.
- **LeKiwi 모바일베이스**: 베이스만 $179, 완전한 시스템을 만들려면 SO-ARM101, Raspberry Pi 5, RGB 카메라 2대, 배터리/충전기를 추가로 사야 한다 (총액 미검증, 대략 $700–900대로 추정). **Raspberry Pi 5 대상으로 설계**되어 있어 Jetson과는 다른 컴퓨팅 경로다. 3-wheel Kiwi-drive를 Feetech 서보로 구동하는데, 이 서보들은 내부에 자체 위치제어 루프(사실상 내장 PID)를 갖고 있어 **"내 손으로 PID를 처음부터 구현"하려는 과제 요건과는 궁합이 안 좋다** — 서보의 서보-레벨 PID를 우회하지 않는 한 학생이 짜는 것은 상위 레벨 궤적/속도 명령이지 저수준 폐루프 제어 자체가 아니게 된다. IMU 탑재 여부도 페이지에서 확인되지 않음.
- 종합: LeRobot 생태계는 "VLM/LLM 재미" 요건(모방학습, VLA 데모, sentdex st일 유튜브 콘텐츠 풍부)에는 최고의 선택이지만, **채점 대상인 classical algorithm 구현체로 쓰기엔 무리**가 있다. 하드웨어 챌린지 통과용 메인 로봇이 아니라, 메인 로봇(1위 DIY 또는 2/3위 키트)을 먼저 완성한 뒤 "보너스 VLM 데모"용으로 SO-101을 얹는 방식을 권장.

### 6. DIY 루트 (chassis + encoder DC motor + motor driver + IMU)
- 구성 예시 (가격은 2026-09 기준 근사):
  - Chassis + encoder gear motor 세트: DFRobot Baron-4WD (2×encoder motor 포함) ~$50, 또는 Pololu Romi 섀시 + 25D encoder gearmotor(64 CPR) 4개 조합 ~$80–150 (문서화 품질이 가장 좋은 편)
  - Motor driver: TB6612FNG 브레이크아웃(~$8) 또는 Cytron 듀얼 드라이버(~$25)
  - 실시간 모터 제어용 마이크로컨트롤러: Arduino Nano/ESP32 (~$10–15) — Jetson은 하드 리얼타임 인터럽트 카운팅에 약하므로, encoder tick 카운트와 PID 속도 루프는 이 보드가 맡고 USB serial로 Jetson과 통신하는 구조 권장 (Waveshare JetBot Pro가 쓰는 것과 동일한 패턴)
  - IMU: Bosch BNO055 (~$16–30, 9-DOF 센서퓨전 내장, I2C, Jetson에서 Python(smbus)으로 바로 읽힘)
  - (선택) LiDAR: RPLidar A1 (~$180–220, SLAM/A* 실습용, 컨트롤러·어댑터 포함 시 체감가는 더 올라감)
- 소프트웨어: 100% 직접 작성 — Jetson Orin Nano Super(이미 보유) 위에서 Python으로 고수준 알고리즘(KF/PID/A*)을, 마이크로컨트롤러에는 C++/Arduino로 저수준 모터 제어를 짠다. 벤더 앱/SDK에 종속되지 않음.
- 조립 난이도: 가장 높음 — 배선, 극성 확인, encoder 캘리브레이션, 시리얼 프로토콜 설계를 스스로 해야 함. 다만 부품별 documentation은 개별적으로는 우수한 편(Pololu·Adafruit·DFRobot 모두 데이터시트/튜토리얼 충실).
- 과제 적합도: **가장 높음** — 선택한 어떤 classical algorithm이든(특히 PID on wheel speed, KF on odometry+IMU) 직접 구현 경험을 100% 제공. SLAM/A*를 하려면 LiDAR 추가만 하면 됨.

---

## 피해야 할 것과 이유

1. **Freenove 4WD Smart Car Kit을 "그대로" 메인 하드웨어로 쓰는 것** — 엔코더가 없어 KF 과제의 핵심 전제(odometry measurement)를 충족 못 하고, Jetson이 아닌 Raspberry Pi 생태계용이라 별도 Pi 구매 또는 드라이버 재작성이 필요하다. 코스 스태프 추천 키트이긴 하나, 그 추천은 "Raspberry Pi/Arduino 학생" 기준일 가능성이 높고 Jetson Orin Nano Super를 이미 산 상황과는 맞지 않는다.
2. **Waveshare JetBot AI Kit (기본/non-ROS, "JetBot"이라는 이름만 보고 사는 것)** — 오리지널 JetBot 오픈소스 설계 자체가 엔코더 없는 오픈루프 제어를 전제로 하므로, 이름이 같은 "ROS AI Kit(Pro)"와 혼동하면 안 된다.
3. **LeKiwi를 메인 채점용 플랫폼으로 삼는 것** — 서보 내장 PID 때문에 "내가 직접 PID/KF를 구현"한다는 과제 취지와 어긋나고, Raspberry Pi 5 대상이라 Jetson 경로와도 다르다. VLM 보너스용 사이드 프로젝트로는 좋음.
4. **보드 포함 여부를 확인하지 않고 Yahboom/Hiwonder 키트를 구매하는 것** — 여러 Jetson 세대를 지원한다고 광고하지만, 실제로 어떤 SKU가 "보드 포함"이고 어떤 SKU가 "보드 미포함(BYO)"인지 이번 조사로는 명확히 가려내지 못했다. 잘못 고르면 이미 산 Orin Nano Super와 중복 구매가 될 수 있다 — 반드시 벤더에 직접 확인.

## "엔코더 없는 키트를 샀을 때" 무엇이 불가능해지는지 (요약)

- 바퀴 회전량을 측정할 방법이 없으므로 **wheel odometry(dead-reckoning으로 x, y, θ 추정) 자체가 불가능** → IMU와 encoder odometry를 융합하는 정석적인 **Kalman filter 과제를 구현할 데이터 소스가 없음**.
- 모터를 "속도" 기준으로 닫힌 루프 제어할 수 없어 **PID도 wheel-speed 제어가 아니라 초음파 거리오차/비전오차 기준의 유사-PID**로만 가능 — 강의에서 다루는 표준적인 PID-on-wheel-speed 구현과는 결이 달라짐.
- Particle filter로 로봇 위치를 추정해도 **비교할 ground-truth 이동량(odometry)이 없어 검증이 어려움**.
- LiDAR를 추가해 SLAM을 한다 해도, 표준적인 "odometry + LiDAR scan matching" 융합 구조를 쓸 수 없어 LiDAR 단독 스캔매칭에만 의존해야 하므로 구현 난이도가 오히려 올라감.

---

## 확인이 필요한 항목 (미검증 플래그)

- Waveshare JetBot ROS AI Kit(Pro)의 정확한 가격, 그리고 Jetson Orin Nano Super 모듈로 교체/호환이 가능한지 — 공식 페이지(waveshare.com/jetbot-ros-ai-kit.htm, waveshare.com/wiki/JetBot_ROS_AI_Kit)가 자동 접근을 차단해 직접 확인하지 못함.
- Yahboom ROSMASTER X3/X3 PLUS의 엔코더·IMU 탑재 여부 — 제품 페이지에 명시적 스펙이 없었음.
- Hiwonder JetAuto의 IMU 탑재 여부, 그리고 Orin Nano Super 대응 SKU의 정확한 가격 — 공식 제품 페이지(hiwonder.com/products/jetauto)가 요청 시 상세 스펙을 반환하지 않음(사이드바/네비게이션만 반환됨).
- LeKiwi 완성 시스템(베이스+SO-ARM101+RPi5+카메라) 총액, IMU 탑재 여부, 조립 난이도 — 개별 제품 페이지에서 명확히 확인되지 않음.
- Yahboom/Hiwonder 키트에서 "컴퓨팅 보드 포함 SKU"와 "보드 미포함(BYO) SKU"가 실제로 구분 판매되는지 여부.

---

## 출처

- [JetBot ROS AI Kit - Waveshare Wiki](https://www.waveshare.com/wiki/JetBot_ROS_AI_Kit)
- [JetBot Professional Version ROS AI Kit — Waveshare](https://www.waveshare.com/jetbot-ros-ai-kit.htm)
- [Waveshare JetBot AI Kit, AI Robot Based on Jetson Nano](https://www.waveshare.com/jetbot-ai-kit.htm)
- [Waveshare JetBot AI Kit — Sunsky-online (3rd-party price)](https://www.sunsky-online.com/p/ZY23043968/Waveshare-JetBot-AI-Kit-AI-Robot-Based-on-Jetson-Nano.htm)
- [Waveshare JetBot Professional Version ROS AI Kit — Amazon](https://us.amazon.com/JetBot-Professional-ROS-Kit-Controllers/dp/B0BNVCYVRV)
- [ROSMASTER X3 PLUS — Yahboom](https://category.yahboom.net/products/rosmaster-x3-plus)
- [NVIDIA Jetson Developer Kits & AI Robots — Yahboom](https://category.yahboom.net/collections/jetson)
- [Hiwonder JetAuto AI Robot Kit](https://www.hiwonder.com/products/jetauto)
- [Hiwonder JetAuto ROS Robot Car (Standard Kit, Jetson Nano) — ozrobotics](https://ozrobotics.com/shop/hiwonder-jetauto-ros-robot-car-powered-by-jetson-nano-with-lidar-depth-camera-standard-kit/)
- [Hiwonder JetAuto Pro](https://www.hiwonder.com/products/jetauto-pro)
- [Freenove 4WD Smart Car Kit for Raspberry Pi — Freenove Store](https://store.freenove.com/products/fnk0043)
- [Freenove 4WD Smart Car Kit — Amazon](https://www.amazon.com/Freenove-Raspberry-Tracking-Avoidance-Ultrasonic/dp/B07YD2LT9D)
- [Hiwonder SO-ARM101 / LeRobot SO-101](https://www.hiwonder.com/products/lerobot-so-101)
- [SO-101 Robot Arm — Specs & Integration — Robotics Center](https://www.roboticscenter.ai/hardware/so-101)
- [LeKiwi Kit (12V Version) — Seeed Studio](https://www.seeedstudio.com/Lekiwi-Kit-p-6501.html)
- [LeKiwi — GitHub (SIGRobotics-UIUC)](https://github.com/SIGRobotics-UIUC/LeKiwi)
- [Lekiwi in Lerobot — Seeed Studio Wiki](https://wiki.seeedstudio.com/lerobot_lekiwi/)
- [Pololu 19:1 Metal Gearmotor with 64 CPR Encoder](https://www.pololu.com/product/1442)
- [Pololu Romi Encoder Pair Kit](https://www.pololu.com/product/3542)
- [DFRobot Baron-4WD Mobile Robot Platform with Encoder](https://www.dfrobot.com/product-261.html)
- [Adafruit BNO055 9-DOF IMU Breakout](https://www.adafruit.com/product/2472)
- [SLAMTEC RPLIDAR A1](https://www.slamtec.com/en/lidar/a1)
- [RPLidar A1M8 — RobotShop](https://www.robotshop.com/products/rplidar-a1m8-360-degree-laser-scanner-development-kit)
