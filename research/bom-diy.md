# Differential-Drive Robot BOM — GT OMSCS CS7638 Hardware Challenge

**작성일(가격 확인일): 2026-09-22** — 가격은 며칠~몇 주 단위로 바뀔 수 있으니, 실제 구매 직전에 링크를 다시 열어 확인할 것.

**전제 조건 (요구사항에서 받은 컨텍스트)**
- Jetson Orin Nano Super (8GB) dev kit + USB webcam은 이미 구매 예정 (별도 확인 필요, 아래 참고)
- Mac (M5 Pro 64GB)에서 개발, Jetson은 별도 로봇 두뇌
- 알고리즘 계획: PID on wheel speed + Kalman filter (wheel odometry + IMU fusion), 카메라+AprilTag은 2차 측정치
- **HARD REQUIREMENT: quadrature encoder가 달린 바퀴모터 필수** — encoder 없으면 Kalman filter에 넣을 odometry measurement 자체가 없음
- 마감: 2026-12-10 (약 11주 남음)

---

## 요약 (TL;DR)

| 구성 | 총액 (대략) | 비고 |
|---|---|---|
| **최소 구성 (Minimum Viable)** | **약 $410–450** | Jetson($249)+webcam(~$20) 포함, DFRobot Baron-4WD 완제품 새시+모터 기준 |
| **여유 있는 구성 (Comfortable)** | **약 $650–700** | Pololu 컴포넌트 빌드 + 상위 모터드라이버/MCU/IMU/카메라 |
| Jetson·webcam 제외 순수 로봇 부품 (최소) | 약 $160–200 | |
| Jetson·webcam 제외 순수 로봇 부품 (여유) | 약 $400–450 | |

**가장 중요한 플래그부터:** 사용자가 알고 있던 "Micro Center에서 Jetson Orin Nano Super가 ~$399"라는 가격은 오늘 검색 결과와 다르다. JetsonHacks(2024-12-17 기사)와 Micro Center 검색 스니펫 모두 **$249**를 MSRP로 보여줬고, slickdeals에는 **$219.99** 프로모션 기록도 있었다. Micro Center 제품 페이지(microcenter.com/product/691058)는 봇 차단(403)으로 직접 열람하지 못해 오늘자 실시간 가격을 최종 확인은 못 했음 — **매장/사이트에서 직접 재확인 요망**. $399는 구형 8GB Developer Kit(할인 전) 가격이었거나, 다른 SKU/번들일 가능성이 있음.

---

## 1. 새시 + DC 기어모터 (Quadrature Encoder 필수)

두 갈래 경로를 제시한다. 시간이 부족하고(11주) 기계 조립 경험이 없다면 **경로 A(완제품)**가 안전하고, 리포트에 정확한 encoder CPR 스펙을 명시해야 한다면 **경로 B(Pololu 컴포넌트)**가 더 낫다.

### 경로 A — 추천(기본): DFRobot Baron-4WD Mobile Robot Platform for Arduino with Encoder (SKU ROB0025)
- **가격**: $49.90 (DFRobot 공식몰, 2026-09-22 확인) — https://www.dfrobot.com/product-261.html
- **왜 이걸**: 새시+모터+바퀴가 이미 조립된 4WD 플랫폼. "comes with two sets of encoder ... closed-loop PID control"라고 제품 페이지에 명시. 조립이 거의 없어 비-기계공학자에게 가장 빠른 경로.
- **스펙**: Rated voltage 4.5–6V, wheel diameter 65mm (2.6in). **Encoder CPR(펄스/회전)과 기어비는 이 세션에서 확인하지 못함** — 구매 전 DFRobot Wiki(https://wiki.dfrobot.com/rob0112/)의 모터 datasheet PDF 링크를 열어 CPR을 반드시 재확인할 것. Kalman filter 리포트에 odometry 분해능을 명시해야 하므로 이 숫자가 없으면 시작할 수 없음.
- 4WD지만 좌/우 모터를 각각 병렬 구동하면 전형적인 differential-drive(2-DOF 제어)로 취급 가능.
- **더 저렴한 대안**: Amazon류 범용 "TT motor 2WD/4WD smart car chassis kit" (VBOTCOR 등, 아크릴 섀시+L298N+TT모터+범용 바퀴, 검색상 완제품 자체 가격은 못 찾음, 시중가 대략 $20–30 추정·미검증). **주의**: 이런 저가 키트의 "encoder"는 종종 **단일 채널 speed sensor(슬롯 디스크)**일 뿐 진짜 2-channel quadrature가 아닌 경우가 많다 — 회전 방향을 못 읽으면 Kalman filter의 odometry measurement로 못 씀. 구매 전 리스팅에 "quadrature" 또는 "2-phase" 또는 "A/B channel" 명시 여부를 반드시 확인.
- **더 좋은 대안**: DFRobot HCR Mobile Robot Platform with Dual Encoder DC Motors — $530–643 (DFRobot, 2026-09-22 검색). 10kg payload, 알루미늄 3단 섀시, Kinect/센서 확장성 좋음. 예산이 넉넉하면 고려할 만하나 이번 과제엔 과함.

### 경로 B — 더 정밀함(스펙이 명확, 성적표에 쓰기 좋음): Pololu 25D mm Metal Gearmotor with 48 CPR Encoder (컴포넌트 조합)
개별 부품을 사서 직접 조립 (아크릴/알루미늄 섀시 플레이트는 별도 구매 또는 직접 제작 필요 — Pololu가 25D 사이즈용 완제품 섀시를 안 판다).

| 부품 | 가격 (2026-09-22 확인) | 출처 |
|---|---|---|
| Pololu 99:1 Metal Gearmotor 25Dx69L mm LP 12V w/ 48 CPR Encoder (×2) | $53.95/개 → $107.90 | https://www.pololu.com/product/4887 |
| Pololu 25D mm Metal Gearmotor Bracket Pair | 가격 미확인 (검색에서 못 찾음, 통상 $5 내외로 추정) | https://www.pololu.com/product/2676 |
| Pololu Wheel 70×8mm Pair | 미국 사이트 정가 미확인 (영국 Pi Hut 환산 약 £5.70 ≈ $7 추정) | https://www.pololu.com/product/1425 |
| Pololu Ball Caster (3/8" metal) | 가격 미확인 (검색 실패, 통상 $4–6 추정) | https://www.pololu.com/product/951 |
| 범용 알루미늄/아크릴 섀시 플레이트 (모터 브라켓 나사 구멍 맞춰 직접 뚫거나 조립형 구매) | 대략 $12–20 추정, 미검증 | — |

- **스펙 (99:1 LP 12V 버전, 실측 확인됨)**: gear ratio 98.78:1, no-load speed 57 RPM @ 12V, stall current 0.9A (extrapolated), encoder 48 CPR (모터축 기준) → **gearbox 출력축 기준 4741.44 CPR/회전**. 이 숫자 자체가 이미 Pololu 공식 datasheet에서 계산된 값이라 리포트에 그대로 인용 가능.
- 더 빠른 회전을 원하면 227:1 MP 12V 버전($53.95, https://www.pololu.com/product/4869, no-load current 100mA, stall 1.8A extrapolated)도 있음 — gear ratio가 높을수록 토크↑ 속도↓.
- **왜 이걸**: encoder CPR·기어비·stall current가 전부 Pololu 공식 스펙시트에 정확히 문서화되어 있어, Kalman filter의 measurement noise/odometry 정밀도 계산을 리포트에 정당화하기 쉽다. 교수/TA가 "encoder resolution 근거가 뭐냐"고 물으면 바로 답 가능.
- **단점**: 섀시가 완제품이 아니라 직접 조립/체결 필요 (드릴링 또는 조립형 알루미늄 채널 구매). 비-기계공학자에게는 경로 A보다 시간이 더 듦.
- **더 저렴한 대안**: 경로 A의 DFRobot Baron-4WD ($49.90, 완제품).
- **더 좋은 대안**: Pololu 25D **HP(High Power)** 12V 버전 + 견고한 Dagu Wild Thumper 6WD 섀시(가격 대략 $130–200대, 이번 세션에서 정가는 검색 못 함) — 험지 주행/토크 여유가 필요하면 고려. 6WD라 순수 2-wheel differential-drive는 아니지만 좌우 3모터 병렬 구동으로 동일한 제어 모델 적용 가능.

---

## 2. 모터 드라이버

| 제품 | 가격 (확인일) | 연속전류 | 평가 |
|---|---|---|---|
| **TB6612FNG breakout (Adafruit #2448)** | **$6.95, 재고 있음** (2026-09-22, https://www.adafruit.com/product/2448) | 1.2A/채널 연속, 3.2A/채널 peak | **추천.** MOSFET 기반이라 L298N보다 전압 강하(voltage drop)가 훨씬 작고 발열도 적음. Pololu LP 모터(stall 0.9A)엔 여유 있게 맞음. SparkFun판은 단종(retired)됨 — Adafruit판으로 구매. |
| Cytron MD10C (단채널 13A) | 가격 확인 실패 (Amazon 페이지 403/본문 미노출, cytron.io도 403). 과거 시세 기준 대략 $25–30 추정 — **미검증, 구매 전 cytron.io 직접 확인 필요** | 13A 연속 (5–30V) | 모터 1개당 1개 필요(2모터=2개 구매). Pololu **MP/HP** 고출력 버전(stall 1.8~5A대)을 쓸 경우 TB6612FNG보다 훨씬 여유로워 안전. |
| Cytron MDD10A (2채널 10A) | 정가 미확인, EU 소매가 €22.50(Botland, 참고용) | 10A/채널 | 모터 2개를 보드 1개로 제어 가능해 배선이 더 간단. HP 모터를 쓸 계획이면 이쪽이 TB6612FNG보다 안전한 선택. |
| L298N 모듈 (범용) | 검증 안 함, 통상 시세 $3–6/개 (일반 상식, 오늘 검색 안 함) | 표기상 2A/채널이지만 실사용은 방열판 없이 ~1A 수준 권장 | **비추천/구식.** 바이폴라 트랜지스터 H-bridge라 채널당 1.4–2V가 그냥 전압강하로 날아가 발열·효율이 나쁨. 수업용 데모엔 동작은 하지만 요즘은 안 씀. |

**결론**: Pololu LP 모터(경로 B, 99:1) 또는 DFRobot Baron 기본 모터(4.5–6V 저전류)라면 **TB6612FNG**로 충분. Pololu MP/HP처럼 stall current가 큰 모터를 고르면 **Cytron MDD10A/MD10C**로 올려야 함.

---

## 3. 마이크로컨트롤러 (실시간 encoder 카운팅 + PID 루프)

| 보드 | 가격 (확인일) | Quadrature 디코딩 | Jetson과 USB serial |
|---|---|---|---|
| **ESP32 DevKitC — 추천** | 검색에서 단일 확정가 못 찾음(Amazon 클론 다수, 시중가 대략 $8–15로 추정, **가격 미검증**) | **하드웨어 PCNT(Pulse Counter) 유닛 내장** — quadrature decode 모드를 하드웨어가 직접 지원해 CPU가 인터럽트에 매달릴 필요 없음. 인코더 채널 4개(모터 2개×A/B)를 여유롭게 처리 | USB-UART 브리지(CP2102/CH340) 내장, `/dev/ttyUSB0`로 바로 인식. Micro Center에서 흔히 재고 있음 |
| RP2040 (Raspberry Pi Pico) — 더 저렴한 대안 | 검색 안 함, 통상 $4–5(상식 수준, 미검증) | PIO(Programmable I/O) state machine으로 quadrature decode 구현 가능(공식 예제 있음) — 유연하지만 펌웨어 작업이 ESP32보다 조금 더 듦 | 네이티브 USB device, 인식 쉬움 |
| Teensy 4.0 — 더 좋은 대안 | 검색 안 함, 통상 $23–28(상식 수준, 미검증) | FlexPWM/eFlexPWM 하드웨어 quadrature decoder 채널 다수 내장, 600MHz라 PID 루프 여유 큼 | 네이티브 USB, 매우 쉬움. 다만 가격이 더 비싸고 Micro Center엔 보통 없음 |
| **Arduino Nano Every** | **$12.90 (Arduino 공식 US 스토어, 2026-09-22)** — https://store-usa.arduino.cc/products/nano-every | 하드웨어 quadrature decoder 없음. ATmega4809 기반이라 인터럽트/핀체인지(PCINT) 처리 여유는 있어 소프트웨어 디코딩으로 충분히 가능(고속 회전 아니면 카운트 놓칠 위험 낮음) | USB-C 있고 표준 serial, 매우 쉬움. Arduino 브랜드라 커뮤니티 자료/코스 예제가 제일 많음 |

**결론**: 시간이 없고 안정성이 최우선이면 **ESP32 DevKitC**(하드웨어 quadrature, Micro Center에서 살 수 있고 쌈). 수업 예제/커뮤니티 문서 의존도가 높으면 **Arduino Nano Every**($12.90, 확정가)도 무리 없음 — 이 로봇 속도대(가정: 바퀴 몇백 RPM 이하)에서는 소프트웨어 인터럽트 디코딩으로 충분.

---

## 4. IMU — BNO055 vs BNO085 vs ICM-20948

| 제품 | 가격 (확인일) | 출력 | 평가 |
|---|---|---|---|
| Adafruit BNO055 (STEMMA QT, #4646) | **$29.95** (원래 비-STEMMA #2472는 $34.95) (2026-09-22 검색) — https://www.adafruit.com/product/4646 | Bosch 자체 sensor fusion 펌웨어가 내장 → **절대 방향(absolute orientation)/quaternion을 온보드에서 이미 융합**해서 I2C로 뱉음. Raw accel/gyro/mag 모드도 선택 가능 | 배선/코드가 제일 편함(STEMMA QT 4핀 커넥터). **단, 과제가 "직접 Kalman filter로 IMU를 융합"하는 게 핵심이라면**, BNO055의 내장 fusion을 그대로 쓰면 사실상 이미 답을 얻는 셈이라 학술적으로 애매해질 수 있음 — ACCONLY/GYROONLY 모드로 raw 값만 뽑아 쓰는 걸 권장 |
| Adafruit BNO085 (STEMMA QT, #4754) | 검색 결과 "BNO080과 동일 가격"이라고만 나옴 — **정확한 현재가 이 세션에서 직접 확인 못 함, 대략 $29.95로 추정** — https://www.adafruit.com/product/4754 | BNO055 후속, SH-2 펌웨어로 SPI 타임아웃 버그 수정, AR/VR용 저지연 rotation vector 추가 | BNO055와 동일한 페인포인트/장점. 새로 산다면 이쪽이 더 최신 |
| **SparkFun ICM-20948 (Qwiic) — 추천** | **$21.95, 재고 있음** (2026-09-22, https://www.sparkfun.com/sparkfun-9dof-imu-breakout-icm-20948-qwiic.html) | **Raw 9-DOF (accel+gyro+mag)만 제공, 온보드 sensor fusion 없음** (DMP는 있지만 안 써도 됨) | 가장 저렴하고, "직접 Kalman filter를 짠다"는 과제 취지에 제일 맞음 — raw gyro 각속도를 KF의 process/measurement model에 그대로 넣으면 됨. Qwiic 커넥터라 배선도 쉬움. **가장 덜 골치 아픈 선택**으로 추천 |

**I2C 배선**: 세 제품 다 STEMMA QT/Qwiic(JST-SH 4핀)라 plug-and-play. Jetson Orin Nano의 40핀 헤더(핀3/5, SDA/SCL bus 1)에 직결해 Python(smbus2)으로 읽는 것도 가능하지만, **권장 아키텍처는 IMU를 MCU에 물리고, MCU가 encoder 카운트+IMU raw 데이터를 한 번에 묶어 USB serial로 Jetson에 보내는 것** — Jetson 쪽 Kalman filter 코드가 시간 동기화된 패킷 하나만 받으면 되어 훨씬 단순해짐.

---

## 5. 전원 (Power)

**핵심 원칙 (사용자 요구사항 그대로): 모터 전원과 Jetson 전원은 반드시 분리된 레일이어야 함.** 모터 stall 시 전류 스파이크가 Jetson 쪽 5V/전원 레일에 노이즈를 태우면 보드가 리셋되거나 SD카드/파일시스템이 깨질 수 있음 — 공통 GND만 공유하고 전력 경로는 분리.

### 모터용 배터리
- **3S LiPo (11.1V 공칭, 만충 12.6V) 5200mAh, 하드케이스** — Pololu 12V 모터와 전압이 잘 맞음. 대표 브랜드: Zeee, GOLDBAT, Power Hobby, HOOVO 등 (Amazon, 2026-09-22 검색으로 다수 리스팅 확인했으나 **개별 가격은 스니펫에 안 나와 미검증** — 일반 시세로 $30–45 추정).
- 밸런스 충전기(iMax B6류 클론) 별도 필요, 없으면 시세 대략 $20–30 추정(미검증).
- LiPo 저전압 알람(버저), 방염 파우치(LiPo bag) 권장 — 각 $5내외 추정.
- **더 저렴한 대안**: 알칼라인/NiMH AA 배터리 홀더(2S~4S 상당). 무겁고 방전특성 나빠 PID 튜닝이 지저분해질 수 있어 비추천.
- **더 좋은 대안**: 2S LiPo + 별도 5V UBEC으로 로직 전압만 깔끔하게 분리 공급 — 배선은 한 단계 늘지만 노이즈에 더 강함.

### Jetson용 배터리 + 컨버터
- Jetson Orin Nano dev kit 배럴잭 입력 규격: **DC 9–20V** (NVIDIA 개발자 포럼 다수 스레드 확인, 2026-09-22 검색). 정격 어댑터는 통상 19V/약 3A(약 57W)급.
- 배터리 직결이 아니라 **buck/boost 컨버터로 9–20V 사이 안정 전압을 만들어 공급**해야 함. NVIDIA 포럼 사례에서는 XL4015 벅컨버터로 24V LiPo를 19.1V로 낮춰 공급한 예가 확인됨.
- 구매 시 체크할 스펙: 출력 9–20V 조절 가능, **연속 전류 최소 3A 이상(피크 부하 감안하면 5A 여유 권장)**, 출력 전압 리플이 작을 것(Jetson이 전압 불안정에 민감하다는 포럼 보고 다수).
- 구체 제품 가격은 이번 세션에서 검색 안 함(시간 예산상 생략) — Amazon에서 "adjustable buck converter 5A 9-24V input" 검색해 $15–25대 제품을 찾는 걸 권장, 구매 전 리뷰에서 Jetson 전용 사용 후기 있는 제품 우선.

### 커넥터/퓨즈
- XT60 또는 XT30 커넥터 (배터리↔전원보드): 소량 팩 $5–8 추정
- 인라인 퓨즈 홀더 + 블레이드 퓨즈(모터 레일 보호용, 모터 stall 전류의 1.5배 정도 정격): $5내외 추정
- 로커 스위치(전원 on/off): $3–5 추정
- **위 5가지 전원 항목은 전부 이번 세션에서 실시간 가격 검색을 안/못 했음 — 구매 전 Amazon에서 재확인 필요.**

---

## 6. 기타 (Misc)

| 품목 | 비고 |
|---|---|
| 바퀴 | 경로 A(Baron-4WD)는 포함. 경로 B(Pololu)는 Wheel 70×8mm Pair 별도 구매(가격 미확인, 대략 $7 추정) |
| 캐스터(caster) | Pololu Ball Caster (3/8" metal, #951) — 가격 검색 실패, 통상 $4–6 추정. Baron-4WD는 4WD라 캐스터 불필요 |
| 스탠드오프/나사 세트 | 대략 $6–10 추정(미검증) |
| 점퍼 와이어 (M-M/M-F/F-F 세트) | Micro Center 매장 재고 통상 있음, $5–8대 |
| 브레드보드 | Micro Center 매장 재고 통상 있음, $5–10대 |
| USB 케이블 (Jetson↔MCU 등) | Micro Center 매장 재고 통상 있음, $5–10대 |
| USB 웹캠 | 이미 구매 계획 있다고 함. Logitech C270: camelcamelcamel 기록상 $17.99(2026-06-27 스냅샷, 당시 품절), 통상 시세 $17–29 (2026-09-22 검색). AprilTag 인식 해상도/화각이 더 필요하면 Logitech C920(1080p) 고려, 가격 미검증(대략 $60–70대 추정) |

---

## 7. Micro Center(미국 오프라인) 재고 vs 온라인 주문 필수

**Micro Center 매장에 보통 있음** (일반적으로 알려진 재고 구성, 이번 세션에서 항목별 재검색은 안 함):
- Arduino Nano / Nano Every
- ESP32 개발보드 (매장별 재고 편차 있음, 방문 전 온라인 재고 확인 권장)
- 점퍼 와이어, 브레드보드
- USB 케이블
- Jetson Orin Nano Super Developer Kit (오늘 확인: $249 MSRP, **실시간 재고/가격은 직접 재확인 요망** — 위 "요약" 섹션 플래그 참고)
- USB 웹캠 (Logitech C270/C920 등 일반 브랜드)

**반드시 온라인 주문**:
- Pololu 25D/20D encoder 기어모터, 브라켓, 휠, 볼캐스터 (pololu.com)
- DFRobot Baron-4WD / Devastator / HCR 플랫폼 (dfrobot.com 또는 Amazon)
- TB6612FNG (Adafruit), Cytron MD10C/MDD10A (cytron.io 또는 Amazon)
- BNO055/BNO085(Adafruit), ICM-20948(SparkFun)
- LiPo 배터리/충전기 — 위험물 배송 제약으로 Micro Center 오프라인 매장엔 보통 없음(취급하는 RC/하비샵이나 온라인 별도 필요)
- Buck/boost 컨버터 모듈

---

## 8. 검증 못 한 항목 총정리 (구매 전 반드시 재확인)

1. **Jetson Orin Nano Super Micro Center 실시간 가격** — microcenter.com 제품 페이지가 봇 차단(403)으로 직접 못 열었음. 검색 스니펫상 $249(MSRP)/$219.99(프로모션) 확인, 사용자가 알던 $399와 불일치 — 가장 먼저 확인할 것.
2. DFRobot Baron-4WD 정확한 encoder CPR/기어비 — 제품 페이지/위키에 안 나와 있음, DFRobot Wiki의 모터 datasheet PDF 또는 고객지원에 직접 문의 필요.
3. Pololu 브라켓(#2676), 휠(70×8mm), 볼캐스터(#951) 미국 정가 — 검색에서 못 뽑아냄(영국 사이트 환산치만 확보), pololu.com에서 직접 재확인.
4. Cytron MD10C/MDD10A 정확한 USD 가격 — cytron.io/Amazon 페이지 접근 실패(403/본문 미노출).
5. Adafruit BNO085(#4754) 정확한 현재가 — "BNO080과 동일가"라는 문구만 확인, 페이지 직접 조회는 안 함.
6. ESP32 DevKitC 확정 단가 — 클론 다수라 시세 폭이 큼, 공식 소스 가격 미확인.
7. LiPo 배터리, LiPo 충전기, buck/boost 컨버터, XT60 커넥터, 퓨즈홀더, 스위치, 스탠드오프 — 이번 세션 검색 예산(≈14회) 안에서 개별 가격 검색을 다 못 함. 위 표의 숫자는 전부 **일반 시세 추정치**이며 실가격이 아님.
8. Teensy 4.0, Raspberry Pi Pico(RP2040) 가격 — 검색 안 함, 상식 수준 추정치.

**요약**: 확정 가격/URL/날짜가 있는 항목(Pololu 99:1·227:1 모터, DFRobot Baron-4WD, Adafruit TB6612FNG, Adafruit BNO055, SparkFun ICM-20948, Arduino Nano Every, Jetson MSRP)은 신뢰도 높음. 그 외(전원계·커넥터류·MCU 클론·일부 Pololu 액세서리)는 추정치이니 최종 장바구니 확정 전에 각 벤더 사이트에서 재확인 권장.
