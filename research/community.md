# 커뮤니티 리서치 — 첫 로봇 빌드 (Reddit 제외)

조사 범위: robotics.stackexchange.com, forums.developer.nvidia.com, discourse.ros.org,
Hacker News, electronics.stackexchange.com, Arduino/RobotShop 포럼, JetsonHacks,
개인 빌드 로그, Chief Delphi(FRC), Limelight/OpenCV 문서. Reddit은 세션에서 차단되어
`reddit.md`에 별도 기록됨 (본 파일에서는 다루지 않음).

**신뢰도 표기 규칙**: 이 파일에서 `[FULL-READ]`는 WebFetch로 원문을 직접 읽은 출처,
`[SNIPPET]`는 WebSearch 요약(모델이 생성한 2차 요약)만 확인하고 원문 전체는
읽지 못한 출처를 의미함. `[SNIPPET]` 항목은 원문 왜곡 가능성이 있으므로
구매/설계 결정의 유일한 근거로 쓰지 말 것.

---

## 요약 (가장 반복되고 중요한 조언 8-12개)

1. **바퀴형(differential-drive)이 첫 로봇의 사실상 표준 추천.** 밸런싱 알고리즘이
   필요 없고, 기구학이 단순해서 SLAM/PID/Kalman 같은 알고리즘 학습에 자원을
   집중할 수 있다는 것이 반복되는 논리. 로봇 팔은 다른 스킬(역기구학, 서보 제어)을
   가르치지만 "첫 로봇"으로는 덜 추천됨. [SNIPPET 다수 일치]
2. **Encoder 없는 모터로 시작해서 나중에 후회하는 패턴이 실제로 보고됨.**
   RobotShop 커뮤니티 스레드는 "지금 기본 제어도 익숙하지 않다면 encoder는
   나중에 추가해도 된다"면서도, 동시에 구체적 추천 키트(Dagu Rover 5)에 대해서는
   "encoder 버전을 사라, 나중에 붙이기 어렵다"고 말함 — **이 두 조언은 서로
   긴장 관계**임(아래 "모순" 참고). [SNIPPET]
3. **카메라 auto-exposure/auto-white-balance는 색 기반 검출을 가장 많이 망가뜨리는
   원인으로 반복 지목됨.** FRC(Chief Delphi/Limelight) 커뮤니티의 표준 해법은
   "exposure를 최대한 낮추고(mostly black 이미지) + 밝은 LED로 타겟만 노출 +
   HSV 공간에서 hue로 threshold + contour 모양/크기로 2차 필터링"이라는
   4단계 방어선. 수천 팀이 수년간 실전에서 검증한 접근이라 신뢰도가 높음. [FULL-READ]
4. **Jetson Orin Nano 계열은 전원 공급 문제가 반복적으로 보고됨.** 정품/정격
   전원(≥4.75V 유지)이 아니면 랜덤 power-off, 재부팅 불가 상태가 발생하고,
   최악의 경우 NVIDIA가 RMA(반품)를 권함. [FULL-READ, 2025-2026 스레드 다수]
5. **밀폐된 케이스에 Orin Nano를 넣고 AI 워크로드를 돌리면 열 문제가 빠르게
   발생.** 한 실사용자는 개방 환경 45-50°C였던 기기가 밀폐 박스에서 62°C →
   100°C까지 올라갔다고 보고 (thermal throttle 트리거는 SoC 다이 99°C,
   shutdown은 105°C). [FULL-READ]
6. **"내비게이션/SLAM만 할 거면 Raspberry Pi 5로 충분하고, GPU 딥러닝 추론이
   필요할 때만 Jetson"이라는 논조가 여러 블로그에서 반복됨.** 다만 이 조언들은
   원문 전체를 확인하지 못한 블로그 요약 수준이라 확정적으로 인용하기는 조심스러움.
   Paul은 이미 Jetson Orin Nano Super를 구매하기로 했으므로 참고용으로만 기록.
   [SNIPPET]
7. **PID를 실제 DC 모터에 붙이면 "지터(jitter)"가 흔한 첫 관문.** 한 Arduino+ROS
   빌드 로그에서는 PWM 주파수가 모터 드라이버에 비해 너무 높은 것과, MCU의
   부동소수점 연산 지연이 원인으로 지목됨 (Arduino Mega → Due로 교체 고려).
   [FULL-READ, 2021년 글이라 3년 기준 초과하지만 문제 패턴 자체는 여전히 유효]
8. **EKF-SLAM을 처음부터 끝까지(시뮬레이션 + 실제 로봇) 구현하는 데 실제로
   걸린 시간은 약 10주라는 개인 빌드 로그가 있음** (TurtleBot3 Burger 사용,
   2024년 2월). "노이즈 파라미터와 landmark association 튜닝에 시간이 많이
   들었다"는 것이 핵심 회고. Paul의 12/10 데드라인(~11주 남음, 오늘 9/22
   기준)과 규모가 비슷해 참고 가치가 큼. [FULL-READ]
9. **센서 동기화(encoder ↔ camera frame ↔ ground truth)가 EKF-SLAM에서
   반복적으로 발목을 잡는 지점으로 지목됨.** Duckietown 팀도 "비동기 데이터
   동기화"와 "노이즈 파라미터 과소/과대 시 filter divergence 또는 paralysis"를
   실전 난점으로 명시. [FULL-READ]
10. **AprilTag/ArUco 같은 fiducial marker는 조명 변화에 대한 robustness가
    색상 기반 검출보다 훨씬 높다고 일관되게 언급됨** (오검출률 낮음, 각도/거리에
    강함). SLAM landmark로도, 순수 위치 추정용으로도 초보자에게 실용적 대안으로
    반복 등장. [SNIPPET, 다만 AprilTag 원 저장소/문서 자체가 이 특성을 설계
    목표로 명시하므로 신뢰도는 준수]
11. **"싼 키트 vs TurtleBot 계열"의 선택은 커뮤니티 지원 유무로 갈린다는 의견.**
    TurtleBot3는 배우는 데 든 비용 대비 커뮤니티/문서가 압도적으로 많고,
    저가 대안(GoPiGo3 등)은 ROS2화 자체가 노동집약적이라는 실사용자 코멘트가
    있음 ("ROSification... is just too hard"). [FULL-READ, 다만 이 스레드는
    응답이 거의 없어 단일 의견에 가까움]
12. **Encoder 없이 하는 dead-reckoning(타이밍 기반)은 원리상 오차가 누적되어
    금방 못 쓰게 된다는 설명이 학술/교육 자료에서 일관되게 나옴** — "속도나
    방향 측정 오차가 시간에 따라 누적"된다는 표현. Reddit 스윕이 요구한
    "IMU-only, visual odometry로 어떻게 보완하는가"에 대한 실전 스레드는
    이번 조사에서 로그인 차단(403) 등으로 원문 확보 실패 — 아래 "검증 못한 것" 참고.

---

## 첫 로봇 선택 (wheels vs arm vs legged) — 커뮤니티 논리

- **바퀴형(2-wheel differential drive)이 압도적으로 추천됨.** 이유는 한결같음:
  balancing 알고리즘이 필요 없고, 기구학이 단순해서 초보자가 "로봇 하드웨어"가
  아니라 "알고리즘"에 집중할 수 있다는 것. 흔히 언급되는 구성은 2-3인치 바퀴,
  5-8V 모터, 6V NiMH 배터리, $80-120대 마이크로컨트롤러. [SNIPPET, 다수 소스
  일치하지만 각 소스가 서로를 재인용하는 블로그류라 "커뮤니티 합의"라기보다
  "업계 표준 조언 템플릿"에 가까움]
- **Legged robot은 이번 조사에서 초보자에게 추천하는 목소리를 거의 찾지 못함.**
  검색 결과 자체가 legged를 별도로 다루는 실전 스레드를 내지 않았음 — 이는
  "다리형은 비추천"이라는 명시적 조언이라기보다, 커뮤니티 담론에서 legged가
  첫 로봇 논의에 거의 등장하지 않는다는 관찰에 가까움. 단정하지 않음.
- **Robot arm은 "다른 학습 목표"로 프레이밍됨.** Arm은 서보 제어, inverse
  kinematics, working envelope/end-effector 설계를 가르치지만, "이동/탐색/SLAM"을
  배우려는 목적이면 arm은 부적합하다는 논리가 일관됨. Paul의 코스(CS7638:
  Kalman/particle filter/PID/SLAM/path smoothing)는 이동체 알고리즘 중심이므로
  이 논리대로면 바퀴형이 코스 요구사항과 직접 정렬됨.
- **가장 많이 언급되는 "후회 패턴"은 로봇 종류 선택 자체보다 "encoder 없는
  모터를 산 것"과 "커뮤니티 지원이 부실한 저가 키트를 산 것"** — 아래 절 참고.
- **TurtleBot3 계열은 "표준 벤치마크 플랫폼"으로 반복 등장** (ROS Discourse
  공지, EKF-SLAM 빌드 로그, Duckietown 등). SLAM/Nav2 커리큘럼과 자료가
  가장 풍부한 플랫폼이라는 점이 실질적 장점으로 꼽힘. [FULL-READ 다수 교차 확인]

---

## 키트와 엔코더: 사기 전에 확인할 것

- **Quadrature encoder 유무를 최우선으로 확인하라는 것이 가장 구체적이고
  실행 가능한 조언.** RobotShop 커뮤니티 스레드(원문 fetch는 403으로 실패,
  검색 요약만 확보 — [SNIPPET])에 따르면:
  - Encoder는 "로봇이 이동한 정확한 거리/속도를 알아야 할 때" 필요 — 직진성
    보정, 지도 작성 시 자기 위치 추정에 필수로 언급됨.
  - 동시에 "처음 시작하는 단계면 기본 제어에 익숙해지기 전까지 encoder
    통합이 쉽지 않으니 서두르지 말라"는 상반된 톤도 같은 스레드에 존재.
  - 그러나 구체적 구매 조언은 명확함: "Dagu Rover 5를 살 거면 encoder
    버전을 사라 — 나중에 추가하기 어렵다." **즉 "당장 encoder 코드를 쓸
    준비가 안 됐어도, 하드웨어 자체는 encoder 있는 걸 사라"는 것이
    이 스레드의 실질적 결론.**
- **Encoder 없을 때의 대안(IMU-only, timing-based dead reckoning, visual
  odometry)에 대한 실전 커뮤니티 스레드는 이번 조사에서 직접 확보하지
  못함.** 학술/강의자료 수준에서는 "타이밍 기반 dead reckoning은 속도·방향
  측정 오차가 누적되어 정확도가 급격히 떨어진다"는 설명만 확인. 실제
  하비스트가 "그래서 어떻게 버텼는지"에 대한 1차 증언은 Google/HN/SE
  검색으로 찾지 못했음 — **이 부분은 검증 실패로 남김.**
- **PID 튜닝 단계에서 나오는 흔한 하드웨어 문제**: Arduino+ROS turtlebot
  빌드 로그(2021, [FULL-READ])에서 DC 모터가 "매우 지터가 심함" → 원인 후보로
  ① PWM 주파수가 모터 드라이버 스펙보다 높음, ② Arduino Mega의 부동소수점
  연산 미지원으로 제어 루프가 느려짐. 최종 해결 여부는 스레드에 기록되지
  않아 미확인.
- **Encoder가 있어도 노이즈/wheel slip은 별개 문제로 남는다**는 것이
  EKF-SLAM 빌드 로그들의 공통 결론 (아래 "몇 주 안에" 절 참고).

---

## 카메라와 조명: 실패 유형과 순위별 해법

실전에서 가장 많이 보고되는 실패 원인 (심각도/빈도 순, FRC·ROS·OpenCV
커뮤니티 교차 확인):

1. **Auto-exposure가 프레임마다 밝기를 재조정하면서 색 기반 검출이 완전히
   무너짐.** 카메라 위치가 바뀌거나 조명이 변하면 이미지가 "거의 흰색 ↔
   정상 ↔ 거의 검은색"을 오가며 색 threshold가 무의미해진다는 설명이
   여러 출처에서 일치. [SNIPPET, ROS Answers 스레드는 403으로 원문 확보 실패]
2. **가장 검증된 해법(FRC 커뮤니티, 수년간 실전 사용): exposure를 수동으로
   최대한 낮추고, 타겟에 강한 조명(LED)을 비춰 "거의 검은 배경 + 밝은 타겟"
   이미지를 만든 뒤 HSV의 Hue 채널로 얇게 threshold.** 이후 contour의
   크기/종횡비/"fullness"(면적 대비 convex hull 비율)로 2차 필터링해서
   천장 조명이나 반사광 잔여 노이즈를 제거. [FULL-READ, Limelight 공식 문서]
3. **White balance는 "Once" 모드로 한 번만 계산해 고정하고, Continuous
   모드(계속 재조정)는 피하라는 조언.** 흰색/무채색 기준 물체(흰 종이 등)를
   두고 한 번 캘리브레이션하는 방법도 언급됨. [SNIPPET]
4. **HSV/색공간 선택 자체가 중요하다는 합의: RGB보다 HSV(Hue 기준)가 밝기
   변화에 강함.** 밝기(Value)와 색(Hue)이 분리되어 있어서 조명 강도가
   변해도 Hue 임계값은 비교적 안정적이라는 설명. [FULL-READ, Limelight]
5. **AprilTag/ArUco 같은 fiducial marker로 아예 색상 기반 검출을 우회하는
   접근이 로버스트니스 측면에서 가장 강하게 추천됨** — 각도/조명 변화에도
   오검출률이 낮다고 설계 문서 및 비교 자료에서 일관되게 언급. Paul의 코스가
   이미 particle filter/SLAM을 다루므로, 색상 검출 대신 AprilTag를 랜드마크로
   쓰는 것이 Hardware Challenge 범위에서 실용적일 가능성. [SNIPPET, 다만
   AprilTag 공식 저장소·기존 로보틱스 지식 자체가 이 특성을 설계 목표로
   명시하므로 신뢰도는 준수]
6. **OpenCV에서 수동 exposure 설정은 카메라 드라이버별로 동작이 다르고,
   "exposure 값만 지정해서는 안 되고 반드시 auto-exposure를 명시적으로
   꺼야 한다"는 실전 함정이 언급됨.** 이 항목은 OpenCV 공식 Q&A 원문이
   403으로 막혀 검색 요약으로만 확인. [SNIPPET]

---

## Jetson 실전 경험: 마찰 지점과 전원 문제

- **전원 공급이 가장 빈번한 실패 지점.** 2025-2026 NVIDIA 개발자 포럼
  스레드 다수에서 "랜덤 power-off 후 재부팅 불가", "두 개의 다른 전원/콘센트로
  테스트해도 부팅 안 됨" 같은 보고가 이어짐. 한 케이스는 recovery mode
  재플래시(SDK Manager)까지 시도했지만 실패해 결국 RMA로 안내받음.
  [FULL-READ: [파워오프 스레드](https://forums.developer.nvidia.com/t/jetson-orin-nano-powers-off-itself-randomly-and-i-cant-power-on-again/380872)
  (2026-08-21~24), [파워 실패 스레드](https://forums.developer.nvidia.com/t/jetson-orion-nano-super-dev-power-failure/377685)
  (2026-07-22~31)]
- **정격 전원(≥4.75V 유지) 미달 시 brownout이 발생한다는 것이 일반적으로
  알려진 원인.** 배터리로 로봇에 물릴 계획이면 DC 배럴잭 전압 범위를
  반드시 확인하라는 논의가 별도 스레드에도 존재. [SNIPPET]
- **밀폐 케이스 + 높은 워크로드 조합에서 열 문제가 빠르게 심각해짐.**
  실사용자 보고: 개방 환경 45-50°C → 밀폐 박스에서 62°C 시작 → AI 워크로드
  중 100°C까지 상승 (팬을 최고 속도로 돌려도). NVIDIA/커뮤니티 응답은
  "부하가 클수록 폐열이 커지는 건 당연하다"는 물리적 한계를 인정하고,
  해법으로 알루미늄 섀시를 방열판으로 활용, 부분 통풍, 또는 성능 모드를
  낮추는 것(전력을 줄여 발열 자체를 줄임)을 제안. [FULL-READ, 2025-08-15]
- **Thermal throttle/shutdown 임계값이 공식 스펙으로 확인됨: SoC 다이
  99°C에서 throttle 시작, 105°C에서 shutdown.** NVIDIA 엔지니어는 "throttle을
  강제로 끄면 다음 안전장치는 shutdown뿐"이라며 throttle 비활성화를 만류.
  [FULL-READ, 2026-08]
- **Orin Nano Super는 2024년 12월 출시 당시 $249로 가격이 절반으로
  인하되며 25W 전력 모드가 추가돼 기존 15W 대비 30-70% 성능 향상을 제공.**
  단, 출시 초기 수요 폭증으로 정식 유통사 재고 부족, 리셀러 가격 급등
  문제가 있었음(현재는 안정화됐을 가능성 높음, 확인 필요). [FULL-READ,
  JetsonHacks 2024-12-17]
- **"SLAM/Nav2 같은 고전 모바일 로보틱스 작업은 Raspberry Pi 5로도 충분하고,
  Jetson은 GPU 가속 비전/딥러닝 추론이 필요할 때만 쓰라"는 논조가 여러
  비교 블로그에서 반복됨.** 초보자에게는 "SDK Manager로 펌웨어 플래싱하는
  과정 자체가 1시간 이상 걸리고 호스트 머신이 필요해, 이게 ROS 로봇 만들기의
  가장 어려운 부분이 되지 않게 하라"는 취지의 조언도 있음. **다만 이 항목은
  원문 전체를 읽지 못한 블로그 비교글 요약이라 확정적 근거로 보기 어려움.**
  Paul은 이미 Jetson을 구매하기로 결정했으므로, 이 조언은 "SDK Manager
  플래싱에 넉넉한 시간을 배정하라"는 일정 관리 관점의 참고 사항으로만
  기록. [SNIPPET]
- **Hacker News 스레드들(2024-12, Jetson Orin Nano Super 발표 시점)은
  주로 가격 대비 연산 성능(TOPS/TFLOPS) 비교와 LLM 추론 용도에 대한
  논의였고, 로봇 하드웨어 실전 경험 공유는 검색 요약 수준에서 확인되지
  않음** — 이번 리서치 목적(로봇 실전 마찰)에는 낮은 관련성으로 판단,
  깊이 파고들지 않음. [SNIPPET]

---

## 몇 주 안에 현실적으로 가능한 범위 (KF/PID/SLAM 관점)

- **가장 직접적으로 참고할 만한 데이터 포인트: 개인 빌드 로그 하나가
  "EKF-SLAM을 시뮬레이션부터 실제 TurtleBot3 Burger까지 구현하는 데
  10주가 걸렸다"고 명시.** (2024년 2월 작성). 핵심 회고 인용 요지:
  "real wheels on the real world slip, motors do not respond ideally" —
  시뮬레이션 검증만으로는 충분하지 않았고, 실제 로봇에서 "EKF의 노이즈
  파라미터와 landmark association 파라미터를 많이 튜닝"해야 했음. 최종
  비교에서 순수 odometry 추정 오차 (x,y,theta)=(0.02, 0.24, -0.67)
  vs SLAM 보정 후 (-0.02, 0.01, -0.06) — SLAM이 odometry 단독보다 명확히
  나은 결과를 보였다는 것도 기록됨. [FULL-READ]
  → **Paul의 데드라인(12/10, 오늘 9/22 기준 ~11주)과 거의 동일한 스케일.**
  단, 이 빌드 로그는 아마 대학원 수업 프로젝트로 전업 학습 시간을 투입한
  결과일 가능성이 높고, Paul은 Data Science Lead로 풀타임 잡을 병행하므로
  "10주 전업 투입 = 몇 주 파트타임"이 아님을 감안해야 함 — 실제 가용 시간
  기준으로는 더 보수적으로 잡아야 할 것.
- **SLAM 튜닝에서 반복적으로 발목 잡는 지점 (Duckietown 팀, [FULL-READ]):**
  - 센서 동기화: "wheel encoder, camera frame, (있다면) ground-truth 데이터가
    비동기적으로 들어오는 것"을 맞추는 작업 자체가 별도 난제로 명시.
  - Filter tuning의 근본적 트레이드오프: "노이즈 파라미터를 너무 작게 잡으면
    overconfidence로 발산, 너무 크게 잡으면 filter paralysis(사실상 필터가
    아무것도 안 믿는 상태)" — 이 표현이 실전 튜닝의 어려움을 가장 잘
    요약함.
  - Sim-to-real gap: "실제 로봇은 완벽한 기구학대로 움직이지 않고, 카메라엔
    방사 왜곡이 있고, 연산에는 비결정적 지연(latency)이 있다."
  - AprilTag 기반 landmark 검출 자체도 "조명 아티팩트와 얕은 시야각에서의
    pose ambiguity로 non-Gaussian 오차"를 유발한다고 명시 — 카메라/조명
    문제와 SLAM 문제가 서로 독립적이지 않고 얽혀 있다는 증거.
- **PID는 하드웨어 레벨(PWM 주파수, MCU 연산 속도)에서부터 막힐 수 있다는
  것이 실전 사례로 확인됨** (위 "키트와 엔코더" 절의 Arduino+ROS 빌드
  로그). 알고리즘을 맞게 짜도 모터 드라이버 스펙/MCU 성능이 안 맞으면
  지터가 발생 — Hardware Challenge에서 "actuator 구동"을 저사양 마이크로
  컨트롤러로 할 경우 이 함정을 미리 점검할 필요.
  [FULL-READ, 2021 — 다만 원 스레드가 최종 해결책을 기록하지 않아 결론은
  미확인]
- **정리하면, 커뮤니티 근거로 볼 때 "몇 주 안에 KF/PID 중 하나를 실제
  로봇에서 돌리는 것"은 현실적이고, "SLAM까지 안정적으로 튜닝해서 보여주는
  것"은 풀타임 10주 사례가 하한선에 가까워 보임.** Hardware Challenge
  요구사항이 "코스 알고리즘 하나"이므로, PID나 Kalman filter(전체 SLAM이
  아닌 localization만) 쪽이 시간 대비 성공 확률이 높다는 것이 이 리서치에서
  나온 합리적 추론 — 단, 이는 내가 종합한 결론이지 커뮤니티가 명시적으로
  "PID를 선택하라"고 말한 것은 아님.

---

## 검증하지 못한 것 (정직하게 기록)

- Reddit은 세션 정책상 접근 불가 — 별도 `reddit.md` 참고, 본 파일에서
  대체 시도 안 함.
- Encoder 없는 로봇에서 IMU-only / timing-based dead reckoning / visual
  odometry로 실제로 "버틴" 1차 실전 후기는 찾지 못함 (검색 결과가 학술
  자료로만 수렴).
- ROS Answers의 usb_cam auto-exposure 스레드, OpenCV 공식 Q&A 스레드,
  RobotShop encoder 스레드는 모두 403(접근 차단)으로 원문을 직접 읽지
  못했고 WebSearch 요약에만 의존함 — 표시된 `[SNIPPET]` 항목 전체가
  이 제약의 영향을 받음.
- robotics.stackexchange.com에서 "첫 로봇 wheeled vs arm" 관련 구체적
  질문 스레드를 특정해서 찾지 못함 — 검색 엔진이 이 도메인의 개별
  스레드를 잘 인덱싱하지 않는 것으로 보임. 해당 사이트의 검색 기능을
  직접 쓰면 더 나은 결과가 나올 가능성이 있음 (이번 조사에서는 시도만
  하고 실패).
- Jetson Orin Nano Super의 최근(2026년 기준) 재고/가격 안정화 여부는
  확인하지 못함 — 2024년 12월 출시 당시 정보만 확보.

---

## 출처

- [Jetson Orin Nano powers off itself randomly](https://forums.developer.nvidia.com/t/jetson-orin-nano-powers-off-itself-randomly-and-i-cant-power-on-again/380872) — forum thread (NVIDIA Developer Forums), 2026-08-21~24 [FULL-READ]
- [Jetson Orion Nano Super Dev power failure](https://forums.developer.nvidia.com/t/jetson-orion-nano-super-dev-power-failure/377685) — forum thread (NVIDIA Developer Forums), 2026-07-22~31 [FULL-READ]
- [Help Needed – Jetson Orin Nano Overheating in Enclosed Outdoor Setup](https://forums.developer.nvidia.com/t/help-needed-jetson-orin-nano-overheating-in-enclosed-outdoor-setup/342224) — forum thread, 2025-08-15 [FULL-READ]
- [Thermal Throttling](https://forums.developer.nvidia.com/t/thermal-throttling/379779) — forum thread, 2026-08 [FULL-READ]
- [Just Super! $249 Jetson Orin Nano Super Developer Kit](https://jetsonhacks.com/2024/12/17/jetson-orin-nano-super-developer-kit/) — blog (JetsonHacks), 2024-12-17 [FULL-READ]
- [EKF SLAM (project page)](https://maxpalay.com/projects/ekf-slam/) — personal build log, 2024-02 [FULL-READ]
- [Extended Kalman Filter SLAM for Duckiebots](https://duckietown.com/extended-kalman-filter-slam-for-duckiebots/) — company/community blog (Duckietown), 2025-04-26 [FULL-READ]
- [Building a "cheap" ROS + Arduino Turtlebot](https://forum.arduino.cc/t/building-a-cheap-ros-arduino-turtlebot-need-help-with-code-hardware/876026) — forum thread (Arduino Forum), 2021-06-18~19 [FULL-READ] (3년 기준 초과, 문제 패턴 참고용)
- [ROS2 Robot Cost Comparison: GoPiGo3 vs TurtleBot3 vs TurtleBot4](https://forum.dexterindustries.com/t/ros2-robot-cost-comparison-gopigo3-vs-turtlebot3-vs-turtlebot4/9217) — forum thread (Dexter Industries Forum), 2022-10-31 (2023-10 업데이트 요청 有) [FULL-READ, 응답 거의 없어 사실상 단일 의견]
- [Questions about robot vision](https://www.chiefdelphi.com/t/questions-about-robot-vision/470114) — forum thread (Chief Delphi, FRC), 2024-08-21 [FULL-READ]
- [Limelight Docs — Additional Theory (retro-theory)](https://docs.limelightvision.io/docs/docs-limelight/pipeline-retro/retro-theory) — official practitioner documentation (FRC vision), 날짜 미상(최신 버전 문서) [FULL-READ]
- How to use a quadrature encoder — RobotShop Community forum thread (원문 403으로 fetch 실패, WebSearch 요약만 확인) [SNIPPET]
- Problem with usb_cam package auto exposure / white balance — ROS Answers archive (원문 403으로 fetch 실패) [SNIPPET]
- How do I set exposure time of Logitech C922 webcam on OpenCV — OpenCV Q&A Forum (원문 403으로 fetch 실패) [SNIPPET]
- Raspberry Pi 5 vs Jetson Orin Nano Super 비교 블로그류 (openelab.io, kunalganglani.com 등, 원문 미확인, 검색 요약만) [SNIPPET]
- Hacker News threads on Jetson Orin Nano Super launch (news.ycombinator.com, 2024-12, 검색 요약만, 로봇 실전 관련성 낮음) [SNIPPET]
- AprilTag design goals / fiducial marker robustness — AprilRobotics GitHub, Robotics Knowledgebase 비교 글 (검색 요약만) [SNIPPET]
