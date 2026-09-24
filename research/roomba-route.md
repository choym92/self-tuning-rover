# Roomba / iRobot Create 해킹 루트 리서치

**리서치 목적**: GT OMSCS CS7638 Robotics Hardware Challenge (2026-12-10 마감, 파트타임 약 11주) — 센서 읽기 + actuator 구동 + PID(wheel speed) / Kalman filter(encoder odometry + IMU fusion) 중 1개 알고리즘을 실제 로봇에 구현. Jetson Orin Nano Super를 로봇 위에 얹고 USB serial로 연결하는 구성을 전제로, "중고 Roomba/Create를 해킹해서 베이스로 쓰는" 루트를 검증.

**리서치 방법**: 공식 iRobot Create 2 Open Interface (OI) Specification PDF (Adafruit 호스팅본)를 직접 다운로드해 `pdftotext`로 원문을 추출하고 grep으로 packet ID·opcode·핀아웃 원문을 확인함 (아래 인용은 대부분 이 1차 자료 기준). 그 외 항목은 web search로 보강했고, 출처·날짜를 표기함. **미검증(⚠️) 표시가 없는 기술 스펙 수치는 공식 spec 원문에서 직접 확인한 것.**

---

## 1. 어떤 모델이 Open Interface(OI)를 노출하는가

| 모델군 | OI 지원 여부 | 근거 |
|---|---|---|
| **Roomba 500 series** (510, 530, 550, 560, 570, 580) | ✅ 공식 지원 — 별도의 "iRobot Roomba 500 Open Interface (ROI) Specification" 문서 존재 | [cfpm.org PDF](http://cfpm.org/~peter/bfz/iRobot_Roomba_500_Open_Interface_Spec.pdf) |
| **Roomba 600 series** (614, 620, 630, 635, 645, 650, 655, 660, 690) | ✅ 공식 지원 — Create 2 OI spec 자체가 "based on the iRobot Roomba 600"이라고 명시. 사실상 Create 2와 동일한 메인보드/펌웨어 계열 | Create 2 OI spec 원문 표지 (직접 확인) |
| **iRobot Create 2** (RC65099) | ✅ 100% 공식 문서화, 가장 안전한 선택. 다만 **단종**된 상태 — Adafruit, The Pi Hut, Little Bird Electronics 등에서 "discontinued/no longer available"로 표기 (2026-09-22 검색 기준) | [The Pi Hut](https://thepihut.com/products/irobot-create-2-programmable-robot), [Little Bird Electronics](https://littlebirdelectronics.com.au/products/irobot-create-2-programmable-robot) |
| **Roomba 700 series** (760, 770, 780, 790) | ⚠️ **미공식/불확실** — iRobot이 700 시리즈용 OI spec을 공식 발행한 적이 없음. RobotReviews 포럼 보고에 따르면 SCI/ROI/COI와 "비슷하지만 하위호환 안 되는 방식으로 다른" 시리얼 프로토콜을 노출한다고 함 | [RobotReviews 포럼 스레드](http://www.robotreviews.com/chat/viewtopic.php?t=15138) |
| **Roomba 800 series** (860, 870, 880, 890) | ⚠️ **미공식/불확실** — 공식 OI spec 문서를 찾지 못함. 물리적 시리얼 인터페이스(전기적 스펙 115200bps N81)는 500~800이 공유한다는 보고가 있지만, command set(OI opcode) 호환성은 확인되지 않음 | 커뮤니티 소스 종합, 공식 문서 없음 |
| **Roomba i/s/j series, Combo (Wi-Fi 전용 최신 라인업)** | ⚠️ **사실상 불가 (강한 커뮤니티 컨센서스, 완전 확증은 못함)** — iRobot HOME 앱/클라우드로만 제어되는 구조이며, 물리적 Mini-DIN OI 포트가 없다는 것이 하비스트 커뮤니티의 정설. 이번 검색으로 "포트가 없다"는 iRobot 공식 문서를 직접 찾지는 못했음 — **구매 전 반드시 실물에서 후면 우측 Mini-DIN 커넥터(스냅 도어 아래) 유무를 눈으로 확인할 것** | 일반 하비스트 지식, 직접 1차 확증 실패 (⚠️ 미검증) |
| **iRobot Create 3** | ❌ **고전적 시리얼 OI 없음** — 공식 문서에 "there is no simple UART serial-style control interface for the Create 3"라고 명시. 대신 BLE 기반 Python SDK 또는 ROS 2 (Wi-Fi / Ethernet-over-USB)로만 제어. 구조 자체가 다름 (Raspberry Pi 4 컴패니언 보드, ROS2 필수) | [Create 3 Docs GitHub Discussion #315](https://github.com/iRobotEducation/create3_docs/discussions/315) |

**검색할 모델명**: Roomba 500 시리즈 — 510/530/560/570/580, Roomba 600 시리즈 — 614/620/630/650/655/660/690, iRobot Create 2 (RC65099). **700/800/900/i/s/j/Combo는 피할 것.**

---

## 2. OI가 실제로 제공하는 것 (공식 Create 2 OI spec 원문 확인)

### 센서 패킷 (Sensors, opcode 142 / Query List opcode 149 / Stream opcode 148)

| Packet ID | 이름 | 데이터 | 비고 |
|---|---|---|---|
| **43** | Left Encoder Counts | unsigned 16-bit, high byte first, range 0–65535 | "cumulative raw left encoder counts... will roll over to 0 after it passes 65535" (원문 인용) |
| **44** | Right Encoder Counts | unsigned 16-bit, range 0–65535 | 위와 동일, rollover 있음 |
| **19** | Distance | signed 16-bit mm, range -32768~32767 | "이전 요청 이후 이동거리, 양 wheel 이동거리 합/2와 동일". ⚠️ **펌웨어 버그**: Create 2/Roomba 500·600의 firmware 3.3.0 이전 버전은 mm 단위 센서값이 부정확하게 나옴. 시리얼로 `7`(soft reset) 전송 시 나오는 welcome 메시지에서 펌웨어 버전 확인 가능 |
| **20** | Angle | signed 16-bit degree, CCW가 양수 | 마지막 요청 이후 회전각 |
| **7** | Bumps and Wheel Drops | 1 byte bitmask | bump left/right, wheel drop left/right/caster |
| **9/10/11/12** | Cliff Left / Front Left / Front Right / Right | 각 1 byte, 0=no cliff, 1=cliff | |
| **21** | Charging State | 1 byte, 0~5 code | |
| **22** | Voltage | unsigned 16-bit mV, 0~65535 | |
| **23** | Current | signed 16-bit mA | 음수=방전, 양수=충전 중 |
| **24** | Temperature | signed 8-bit °C | |
| **25** | Battery Charge | unsigned 16-bit mAh | |
| **26** | Battery Capacity | unsigned 16-bit mAh | |

### 구동 명령 (Actuator Commands)

| 명령 | Opcode | 파라미터 | 비고 |
|---|---|---|---|
| **Drive** | 137 | velocity(mm/s, signed 16-bit) + turn radius(mm, signed 16-bit) | 앞뒤 평균 속도 + 회전 반경 방식. 직진/제자리 회전은 special radius 값 사용 |
| **Drive Direct** | 145 | right velocity + left velocity, 각각 signed 16-bit, **범위 -500~500 mm/s** | 좌우 바퀴 속도 독립 제어 — **PID on wheel speed에 쓸 명령이 이것** |
| **Drive PWM** | 146 | right PWM + left PWM, 각각 signed 16-bit | raw duty cycle 직접 제어(open-loop, 속도 아님) |

Drive/Drive Direct/Drive PWM 모두 **Safe 또는 Full 모드에서만 동작** (Passive에서는 무시됨) — 원문 확인.

### 업데이트 주기 / 대역폭

- "Roomba updates these values internally every **15 ms**. Do not send these commands more frequently than that." — 원문 인용.
- Stream(148)으로 자동 스트리밍 시에도 15ms마다 전송.
- **대역폭 제한**: 115200 baud 기준 15ms 슬롯에 최대 172 byte까지만 전송 가능(계산식: 15ms / 10bit(8data+start+stop) × 115200bps = 172.8). 이보다 많은 packet을 스트리밍 요청하면 데이터가 깨짐(checksum으로 확인 가능) — 원문 인용.
- 컨트롤 루프에서는 Query List(149)로 매 tick 필요한 packet ID만 골라 요청하는 방식이 스트리밍보다 예측 가능하고 안전함.

### 바퀴 1회전당 encoder count / count당 거리

⚠️ **공식 spec 원문에는 이 수치가 없음** — PDF 전체를 grep했지만 "revolution", "wheel diameter", "ticks" 관련 서술이 전혀 없었음. 커뮤니티에서 널리 인용되는 값은 **508.8 counts/revolution**이지만 이는 iRobot 공식 문서가 아니라 Synthiam 로봇 스킬 문서 등 2차 출처에서 나온 값이며, 실제 로봇마다 계산치가 안 맞는다는 보고도 있음(예: "1m 주행하도록 508.8 tick 계산했는데 실제로는 80cm만 움직임" — GitHub 이슈). **실전 권장**: 이 미검증 상수에 의존하지 말고 (a) Distance/Angle 패킷(19/20)을 그대로 쓰거나 (b) 로봇을 고정 거리로 주행시켜 raw encoder count 변화량을 직접 재서 자체 캘리브레이션할 것.

출처: [Synthiam iRobot Roomba Movement Panel](https://synthiam.com/Support/Skills/Movement-Panels/iRobot-Roomba-Movement-Panel?id=19164), [create_autonomy Issue #32 "Roomba 780 Incorrect Odometry"](https://github.com/AutonomyLab/create_autonomy/issues/32) — 모두 ⚠️ 미검증(2차 출처).

---

## 3. 물리적 연결

- **커넥터**: 7-pin female **Mini-DIN**, 로봇 후면 우측에 탈착식 플라스틱 커버 아래 위치 (원문 확인).
- **핀아웃** (top view, 공식 spec 원문 그대로):

| Pin | 이름 | 설명 |
|---|---|---|
| 1, 2 | Vpwr | Roomba 배터리 + (unregulated) |
| 3 | RXD | 0–5V serial input to Roomba |
| 4 | TXD | 0–5V serial output from Roomba |
| 5 | **BRC** | Baud Rate Change (겸 wake-up 핀) |
| 6, 7 | GND | Roomba 배터리 GND |

- **전압**: **5V TTL이 맞고 RS-232 아님** — 원문에 "two-way, serial communication at TTL (0–5V) levels"라고 명시. PC의 RS-232 시리얼에 물리려면 레벨 시프트가 필요하다고 spec 자체가 경고함.
- **Baud rate**: 기본값 **115200** (Create 2/600 시리즈부터). "What's new in Create 2" 부록에 "The default baud rate has changed from 57600 to 115200 kbps"라고 명시 — 즉 **구형 Roomba(500 이전 세대)는 기본 57600**이었다가 Create 2/600에서 115200으로 바뀜. 19200으로 강제 전환하려면 BRC 핀(pin5)을 전원 인가 2초 후 50~500ms짜리 low pulse 3번.
- **USB-시리얼 어댑터**:
  - iRobot 정품 "Create (2) USB cable" — 레벨시프트+Mini-DIN이 한 케이블에 통합된 순정 액세서리. Create 2 단종으로 신품 구하기 어려울 수 있음.
  - 커뮤니티에서 흔히 쓰는 대안: **EZSync018 (USB to DIN Serial Cable for Roomba/Create 2)** — Amazon에 정확히 이 용도로 판매 중, plug-and-play. [Amazon 링크](https://www.amazon.com/EZSync-Serial-Roomba-Create-EZSync018/dp/B06XDPMY4Z) (⚠️ 가격 미확인 — 리스팅만 확인, 금액은 직접 조회 필요)
  - DIY 대안: 일반 **FTDI TTL-232R (5V 버전)** USB 케이블 + mini-DIN 7핀 커넥터/브레이크아웃을 직접 배선 — Roomba TXD/RXD가 5V TTL이므로 FTDI의 5V 버전과 전압이 맞아 별도 레벨시프터 없이 연결 가능 (출처: [nrqm.ca Roomba Report](https://nrqm.ca/nrqm.ca/roomba-report/hardware/index.html)).
- **3.3V 보드용 레벨 시프터 필요 여부**: **USB-시리얼 어댑터를 거쳐 Jetson에 USB로 연결하는 이번 구성에서는 불필요** — 어댑터의 USB 쪽은 USB 프로토콜이므로 Jetson의 3.3V UART 핀이 Roomba의 5V TXD에 직접 노출되지 않음. 반대로 **Jetson의 bare GPIO/UART 핀에 Roomba RXD/TXD를 직결**한다면 반드시 로직 레벨 시프터가 필요함 (Roomba TXD 5V → 3.3V 수신 핀에 직결 시 손상 위험) — 이 경고는 Raspberry Pi Zero 연결 사례에서 실제로 언급됨. 이번 프로젝트 계획(USB serial)에서는 해당 없음.
- **외부 전자장치 전원 공급 가능 여부**: **가능하지만 매우 제한적**. Pin 1/2(Vpwr)는 배터리 직결(unregulated)이며 **200mA PTC 리셋 퓨즈**를 거침 — 원문: "The continuous draw from these two pins together should not exceed 200 mA. Do not draw more than 500 mA peak from these pins, or the fuse will reset." **Jetson Orin Nano Super 같은 컴퓨트 모듈은 이 200mA로 절대 못 돌림** — Jetson은 별도의 자체 전원(USB-C/베럴잭, 수 A급)을 써야 하고, Vpwr 핀은 IMU 브레이크아웃 보드처럼 아주 작은 주변장치 전원 정도로만 고려할 것.

---

## 4. 사람들이 보고한 Gotcha

1. **OI 모드 타임아웃/슬립**: Passive 모드에서 5분간 입력 없으면 로봇이 절전모드로 빠짐(원문 확인: "Roomba will sleep after 5 minutes of inactivity"). 방지하려면 5분 안에 BRC 핀(pin5)을 주기적으로 low pulse — 원문 예시는 "1분마다 1초간 low"지만, baud rate 변경 시퀀스(연속 3회 pulse)를 우발적으로 트리거하지 않도록 pulse 패턴에 주의하라고 spec 자체가 경고함.
2. **Safe/Full 모드에서는 절대 잠들지 않지만 충전도 안 됨**: 원문 인용 — "In Safe and Full modes, Roomba will never sleep, and if left in this state for an extended period of time, will deeply discharge its battery, **even if plugged into the charger**. The charger will power Roomba in all modes, but **it will not charge the battery in Safe or Full mode**." → 작업 끝나면 반드시 Passive나 Stop으로 돌려놓을 것. 안 그러면 도킹된 채로도 배터리가 서서히 방전됨.
3. **도킹 상태에서 BRC로 깨우기 안 되는 구형 펌웨어**: ⚠️ (2차 출처, 이번 세션에서 원문 직접 확인은 못함) "Create 2와 Roomba 500/600의 release-3.8.2/release-stm32-3.7.7 이전 펌웨어는 도킹된 상태에서 BRC pulse로 안 깨어난다"는 보고가 있음. 구형 개체를 살 경우 펌웨어 버전 체크 권장.
4. **펌웨어별 Distance/Angle 버그**: firmware 3.3.0 이전은 mm 단위 센서값(Distance 등)이 부정확 — 시리얼로 `7`을 보내 리셋하면 뜨는 welcome 메시지에서 `r3_robot/tags/release-X.X.X` 형식의 버전 확인 가능 (원문 인용).
5. **시리즈간 프로토콜 차이**: 700 시리즈는 공식 미문서화 + 비하위호환 변형 프로토콜 가능성 (섹션 1 참고). 800/900/Wi-Fi 계열은 더 불확실.
6. **Encoder rollover (65535)**: Left/Right Encoder Counts(43/44)는 unsigned 16-bit라 65535를 넘으면 0으로 롤오버 — 원문에 명시. PID/Kalman 코드에서 delta 계산 시 wraparound(모듈로 연산 또는 int16 wrap 처리)를 직접 다뤄야 함. 이건 실수하기 정말 쉬운 부분이라 미리 단위 테스트할 것.
7. **Wheel slip**: OI spec 자체는 다루지 않는 물리적 이슈 (⚠️ 일반 로보틱스 지식, 특정 출처 없음) — encoder-only odometry는 slip 때문에 드리프트하고, 이게 바로 이번 과제에서 IMU와 Kalman filter로 fusion하려는 이유 자체와 정확히 일치함.
8. **Baud rate 세대차**: 구형(57600 기본) vs Create2/600(115200 기본) — 옛날 코드/예제를 그대로 갖다 쓰면 baud mismatch로 "깨진 데이터만 들어옴" 버그를 겪기 쉬움. 부록에서 원문 확인.

---

## 5. 중고 시장

⚠️ **가격 데이터는 전반적으로 약함** — eBay는 스크립트 접근이 막혀(403) 실시간 시세를 제대로 못 긁었고, 아래는 단발성 검색 스냅샷 + 일반 지식 조합임. **구매 전 반드시 eBay "Sold listings" 필터로 직접 최신 시세 확인 권장.**

- **Roomba 690** (600 시리즈): eBay 리스팅에서 **$49.99** 확인 (단일 리스팅, 2026-09-22 검색 스냅샷 — sold 가격인지 asking 가격인지 불명확, ⚠️ 검증 약함).
- **Roomba 650**: 여러 리스팅 존재하나 가격 파싱이 불완전 — 한 리스팅은 "충전기 포함, 배송비 $60.95"만 확인됨 (본체 가격 미확인). (2026-09-22, ⚠️ 검증 약함)
- **일반적인 시세 감** (⚠️ 특정 출처 없는 배경 지식, 참고용): 정상 작동하는 600 시리즈 개체가 eBay/Facebook Marketplace에서 대략 $30~80, "for parts/미작동" 개체는 $10~20 수준, Create 2(구할 수 있다면)는 목적 특화 제품이라 프리미엄 붙어 $80~150+ 수준으로 거래되는 경우가 많다고 알려져 있음. **이 구간은 직접 재확인 필요.**
- **iRobot Create 2 신품**: **단종 확인됨** — Adafruit/The Pi Hut/Little Bird Electronics 모두 "discontinued"/"no longer available"로 표기 (2026-09-22 검색 기준). 신품은 사실상 구할 수 없고 중고/재고 잔량만 가능하며, 있다면 프리미엄 가격일 가능성 높음.
- **구매 전 체크리스트**:
  1. 전원이 들어오는가 (Clean 버튼 눌러서 불 들어오는지)
  2. 도킹 시 충전 인디케이터가 정상 작동하는가 (배터리+충전 회로 건강도 간접 확인)
  3. **충전 독(dock) 포함 여부** — 독만 따로 사면 중고 기준 대략 $15~20 (eBay 스니펫 기준, ⚠️ 단일 출처)
  4. 배터리 연식/건강도 — NiMH 팩은 2~4년이면 열화되는 게 보통이므로, 판매자에게 배터리 교체 이력 확인하거나 아예 교체 예정으로 잡을 것
  5. **후면 우측 Mini-DIN 포트 실물 확인** — 스냅 도어를 열어 7핀 커넥터가 실제로 있고 손상 안 됐는지 확인 (특히 모델명이 불확실한 리스팅일수록 중요)
  6. 침수/파손 이력, "for parts" 표기 리스팅은 섀시·모터만 재활용할 목적이 아니면 피할 것
- **교체 배터리 비용**: Tenergy 브랜드가 500/600/700/800 시리즈용 NiMH(3500/3850/4500mAh) 및 Li-ion(5200mAh) 대체 배터리를 Amazon에서 다수 판매 중 (SKU 다수 확인됨, [예시](https://www.amazon.com/Tenergy-Extended-Rechargeable-Replacement-Batteries/dp/B078XNPTXR)). ⚠️ **이번 세션에서 실제 판매가는 확인 못함** — 일반적으로 NiMH 3.5~4.5Ah급은 대략 $25~45, 5200mAh Li-ion 버전은 $40~60 선으로 알려져 있으나 **이 숫자는 미검증이므로 구매 전 Amazon 페이지에서 직접 재확인할 것**.

---

## 6. 소프트웨어

| 라이브러리 | 유지보수 상태 | 비고 |
|---|---|---|
| **pycreate2** ([MomsFriendlyRobotCompany/pycreate2](https://github.com/MomsFriendlyRobotCompany/pycreate2), PyPI) | 최신 릴리스 0.8.1 (2021-02-22) — 사실상 유지보수 멈춘 상태지만, OI 프로토콜 자체가 안 바뀌어서 "완성된 채로 안정적"인 상태. 미국 공군사관학교 ECE387 로보틱스 수업에서 실제 사용된 이력 있어 검증됨 | pure Python, pyserial 기반. `Create2(port)`로 연결 열고, `.get_sensors()`가 packet 값을 named tuple로 반환(이름/인덱스 양쪽 접근 가능), `.drive_direct(right, left)`로 좌우 바퀴 속도 독립 명령, `.drive_pwm()`/`.drive_stop()`도 제공 |
| **BreezyCreate2** ([simondlevy/BreezyCreate2](https://github.com/simondlevy/BreezyCreate2), PyPI) | simondlevy가 유지 중인 얇은 wrapper | `setForwardSpeed`, `playNote`, `getBumpers` 등 초보자 친화적 API. PID/Kalman처럼 저수준 타이밍 제어가 필요한 작업엔 추상화가 너무 높아서 첫 "hello world" 테스트용으로만 추천, 본 과제 구현체로는 pycreate2나 raw pyserial 쪽이 나음 |
| **raw pyserial 직접 구현** | 해당 없음(직접 구현) | OI가 바이트 단위로 완전히 문서화된 프로토콜(opcode 137/145/146 구동, 142/149 센서 읽기, 148 스트리밍)이라, 다수 하비스트가 라이브러리 없이 `/dev/ttyUSBx`를 pyserial로 직접 두드림. 컨트롤 루프 타이밍을 직접 쥐고 싶다면(=PID/Kalman 구현 목적) 오히려 이 방식이 더 투명함 |
| **ROS 드라이버**: [AutonomyLab/create_autonomy](https://github.com/AutonomyLab/create_autonomy) (ROS1, libcreate C++ 래핑) / [AutonomyLab/create_robot](https://github.com/AutonomyLab/create_robot) (ROS2, Foxy/Humble/Iron/Rolling 지원) | 활발히 유지되는 편(ROS2 브랜치 존재) | 나중에 ROS2/Nav2까지 확장하고 싶으면 "배터리 포함" 옵션. 다만 이 드라이버는 보통 `robot_localization` 패키지의 EKF로 fusion을 이미 대신 해주는 구조라서, **과제 취지상(PID/Kalman을 직접 구현해야 하는 것)** pyserial/pycreate2로 로우레벨을 직접 만지는 편이 오히려 적합함 |

**"encoder 읽고 바퀴 굴리기" 최소 루프 (설명, 코드는 생략)**:
1. 115200 baud로 OI 포트 시리얼 연결 오픈.
2. Start(opcode 128) 전송 후 Safe(opcode 131) [또는 책상 위 bring-up 단계에서 cliff/bump 안전정지를 끄고 싶으면 Full(opcode 132)]로 모드 전환 — Drive 계열 명령은 이 모드에서만 먹힘.
3. 고정 주기(로봇 내부 갱신 주기인 15ms 근방, 예: 15~30ms)로 루프:
   a. Query List(opcode 149)로 packet 43/44(raw encoder) 혹은 19/20(사전계산된 distance/angle) 요청 후 응답 바이트를 spec대로 signed/unsigned 정수로 언패킹.
   b. delta encoder count / dt로 바퀴 속도 계산 (65535 rollover 처리 필수).
   c. 측정 속도 vs 목표 속도로 PID 계산, 그리고/또는 encoder delta + IMU 값을 Kalman filter에 입력.
   d. Drive Direct(opcode 145)로 새 좌우 바퀴 속도(-500~500mm/s) 명령 전송.
4. 종료 시 Stop 혹은 Passive 모드로 반드시 복귀 — 안 그러면 Full 모드로 도킹된 채 방치되어 배터리가 조용히 방전됨(섹션 4-2 참고).
- pycreate2를 쓰면 2~4단계의 opcode 바이트 패킹을 `.start()`/`.safe()`(또는 `.full()`)/`.get_sensors()`/`.drive_direct()` 호출로 대신해주면서도 매 tick의 raw 센서값은 그대로 받아볼 수 있음.

---

## 7. 솔직한 평가: Roomba 해킹 vs 파츠로 처음부터 빌드

**전제**: 하드웨어 경험 없음, 풀타임 직장 병행, 파트타임 11주, 2026-12-10까지 PID(wheel speed) + Kalman(encoder+IMU fusion)을 실물 로봇에서 데모해야 함.

**Roomba/Create 루트가 유리한 이유**:
- 가장 실패 확률이 높은 부분(모터, 기어박스, 바퀴, 섀시, 배터리, 모터 드라이버가 이미 통합되어 정상 동작하는 differential-drive base)이 이미 다 해결되어 있음. 하드웨어 경험 없는 사람 기준으로, H-bridge 배선 실수/모터 드라이버 태워먹기/바퀴 정렬/전원 분배 같은 흔한 실패 지점 대부분을 원천적으로 건너뜀.
- Encoder가 이미 배선되어 있고, 하나의 잘 문서화된 프로토콜(OI)로 바로 읽을 수 있음 — 직접 encoder를 고르고 장착하고 캘리브레이션할 필요가 없음.
- pycreate2 같은 기존 코드와 이번에 확인한 공식 spec이 있어서, "내가 만든 H-bridge와 encoder 배선을 새벽에 디버깅"하는 대신 검증된 베이스 위에서 곧장 PID/Kalman(=실제 채점 대상)을 구현할 수 있음.
- 11주 파트타임이라는 빠듯한 일정 감안 시, (OI 지원이 확실한) 중고 유닛을 $50~150 사이에 구해서 "encoder 읽고 바퀴 굴리기"까지 1~2주 안에 끝내면, 남은 ~9주를 알고리즘 구현과 Jetson/IMU 통합에 온전히 쓸 수 있음.

**이 루트 고유의 리스크**:
- 중고 개체 컨디션 리스크(배터리 열화, 모터 마모) — 600 시리즈/Create 2로 한정하고 구매 전 Mini-DIN 포트 실물 확인 + 전원 켜짐 테스트로 완화 가능.
- 전기적 통합 리스크: Jetson Orin Nano(3.3V 로직, 자체 전원 필요 — Roomba의 200mA Vpwr로는 절대 못 돌림)와 외부 IMU를 Roomba의 5V TTL 시리얼과 깔끔하게 통합하는 작업 — 실재하지만 범위가 명확한 엔지니어링 과제지, 리서치 문제는 아님.
- 15ms/172byte 대역폭 상한을 모르고 고주파 스트리밍을 시도하면 데이터가 깨짐 — 이번 문서로 미리 인지했으니 시행착오로 시간 낭비할 필요는 없음.
- **가장 큰 리스크**: 700/800/900/Wi-Fi 계열을 잘못 사서 OI가 아예 안 되거나 포트가 없는 경우 — 11주 중 상당 시간을 막다른 길 디버깅에 날릴 수 있음. 이건 600 시리즈/Create 2만 고수하고 구매 전 포트 확인하는 것만으로 완전히 피할 수 있는 리스크임.

**결론**: 하드웨어 경험이 없고 파트타임 11주뿐이라는 조건에서는, 중고 Roomba 600 시리즈 또는 Create 2를 해킹하는 쪽이 PID+Kalman을 데모 가능한 상태로 만드는 데 더 빠르고 리스크가 낮은 경로일 가능성이 높음. 단, (a) 500/600 시리즈나 정품 Create 2만 고수하고 700/800/900/i/s/j/Combo는 피하며, (b) 구매 전/직후 물리적 Mini-DIN 포트와 전원·도킹 충전을 직접 확인하고, (c) 초반 한 주말은 온전히 "encoder 읽기 → 바퀴 굴리기 → 5분 슬립 타임아웃 극복"이라는 bring-up 마일스톤에 배정해두는 것을 전제로 함. 반대로 파츠부터 직접 조립하는 루트는 모터·인코더·섀시·모터드라이버·배터리를 각각 고르고 배선하고 신뢰할 수 있는 첫 센서값을 얻기까지 자체로 11주 중 여러 주를 소모할 가능성이 크며, 풀타임 직장을 병행하는 일정에서는 특별한 이유(Roomba로는 안 되는 폼팩터가 필요하다거나, 이미 파츠를 보유하고 있다거나)가 없다면 더 리스크가 큰 선택임.

---

## 출처 종합 (접속일 2026-09-22)

- [iRobot Create 2 Open Interface Specification (Adafruit 호스팅, PDF, 1차 자료로 직접 다운로드·파싱함)](https://cdn-shop.adafruit.com/datasheets/create_2_Open_Interface_Spec.pdf)
- [iRobot Roomba 500 Open Interface (ROI) Specification](http://cfpm.org/~peter/bfz/iRobot_Roomba_500_Open_Interface_Spec.pdf)
- [iRobot Create 3 Docs — Serial Communication](https://iroboteducation.github.io/create3_docs/lessons/ros2/intro/serial-communication/)
- [Create 3 with Arduino/ESP32 — GitHub Discussion #315](https://github.com/iRobotEducation/create3_docs/discussions/315)
- [RobotReviews 포럼 — Roomba 780 해킹 가능성 논의](http://www.robotreviews.com/chat/viewtopic.php?t=15138)
- [pinoutguide.com — iRobot Roomba Open Interface (OI) pinout](https://pinoutguide.com/Electronics/irobot_roomba_serial_pinout.shtml)
- [nrqm.ca — Roomba Report, Hardware (FTDI/레벨시프트 논의)](https://nrqm.ca/nrqm.ca/roomba-report/hardware/index.html)
- [EZSync018 USB to DIN Serial Cable — Amazon](https://www.amazon.com/EZSync-Serial-Roomba-Create-EZSync018/dp/B06XDPMY4Z)
- [MomsFriendlyRobotCompany/pycreate2 — GitHub](https://github.com/MomsFriendlyRobotCompany/pycreate2)
- [simondlevy/BreezyCreate2 — GitHub](https://github.com/simondlevy/BreezyCreate2)
- [AutonomyLab/create_autonomy — GitHub (ROS1)](https://github.com/AutonomyLab/create_autonomy)
- [AutonomyLab/create_robot — GitHub (ROS2)](https://github.com/AutonomyLab/create_robot)
- [pkyanam/ArduRoomba — GitHub (모델 호환성 언급)](https://github.com/pkyanam/ArduRoomba)
- [The Pi Hut — iRobot Create 2 (discontinued 표기)](https://thepihut.com/products/irobot-create-2-programmable-robot)
- [Little Bird Electronics — iRobot Create 2 (no longer available 표기)](https://littlebirdelectronics.com.au/products/irobot-create-2-programmable-robot)
- [Synthiam — iRobot Roomba Movement Panel (508.8 counts/rev 언급, ⚠️미검증 2차 출처)](https://synthiam.com/Support/Skills/Movement-Panels/iRobot-Roomba-Movement-Panel?id=19164)
- [create_autonomy Issue #32 — Roomba 780 Incorrect Odometry](https://github.com/AutonomyLab/create_autonomy/issues/32)
- [Tenergy 교체 배터리 예시 (Amazon, 가격 미확인)](https://www.amazon.com/Tenergy-Extended-Rechargeable-Replacement-Batteries/dp/B078XNPTXR)
- eBay 개별 리스팅 (Roomba 690 $49.99 등) — 검색 스냅샷, 2026-09-22, sold/asking 구분 불명확, ⚠️ 재확인 권장
