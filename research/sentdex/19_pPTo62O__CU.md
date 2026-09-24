# 19 — Unboxing the Unitree G1 Edu Humanoid

- 한 줄 요약: Unitree G1 EDU Ultimate B 휴머노이드를 언박싱하고, 공식 C++ SDK 문서만으로는 개발이 막막해 Codex(o3)의 도움으로 Python wrapper API를 직접 만들어 기본 기립·보행 테스트까지 성공한 시리즈 1편.
- 로봇 관련성: 높음

## 하드웨어 (robot, sensors, actuators, compute board, prices if stated)
- 로봇: Unitree G1 EDU Ultimate B (일명 G1 EDU U4), Dex3-1 촉각센서 탑재 3지 손(hand) 버전. 시뮬레이션 로봇 학습 스타트업 "Lucky Robots"에서 어드바이저 역할로 받음.
- 가격 구조(자막 기준): 기본 G1은 $16,000(세금/관세 제외), 미국 배송 시 실제로 ~$24,000. 기본형은 손이 기능 없는 빈 장갑이고 SDK도 없음. EDU 베이스(SDK 제공, 손 여전히 없음) → EDU Ultimate(Dex3-1 촉각 있는/없는 버전, 또는 Inspire 손 버전; 신형 Dex5-1은 당시 미출시)로 갈수록 비쌈. 영상 속 모델(EDU Ultimate B, Dex3-1 촉각형)은 중국 현지 현금가 $56,900, 미국 관세/세금 포함 시 6만 달러 중반 이상.
- 몸체: 키 약 135cm(4.5ft), 무게 약 38kg(85lb), 매우 밀도 높음(들기 힘듦).
- 짐벌/거치대(gantry): 로봇을 안전하게 매달아 R&D 하는 용도, 별도 구매 시 약 $1,500. 주문 시 함께 오는지 Unitree와 판매처(RoboStore) 사이 의견 차이 있었음. 아직 못 받아서 임시로 개 목줄 거치대(game hanger)를 대체 사용. 대안으로 의료용 호이어 리프트(Hoyer lift, 거동 불편 환자용 리프트)를 추천 — 정식 gantry의 절반 가격, 오히려 더 나을 수도 있다고 언급.
- 관절 가동범위(자막 근거, 대략치): 발목(좌우 롤+상하), 무릎, 허벅지 ~320° 회전, 엉덩이 좌우 약 180°+전후, 몸통 300°+ 회전, 손(Dex3) 엄지 약간 회전+손가락마다 2관절, 손목 좌우/전후 움직임+약 300° 회전, 팔꿈치는 인체와 비슷한 가동범위, 어깨 약 300° 회전+상하 스윙+어깨 아래 추가 피벗.
- 헤드: RGB 카메라, 뎁스 카메라, 3D LiDAR 탑재. 목 뒤에 USB-C 4개, LAN 2개 포트. 머리가 상하로 약간 움직이는 것도 발견했지만, 이게 실제 addressable 모터/자유도인지는 본인도 확신 못함.
- 컴퓨팅: 내부적으로 로봇 자체 컴퓨터 + (EDU 이상) 보조 컴퓨터로 Jetson Orin NX(자막에서 "Nano"와 혼용 언급, 불확실) 탑재. SDK는 이 Jetson을 통해 통신. 쿼드러페드(사족 로봇)는 라즈베리파이 기반이라 더 쉽지만 G1은 다름.
- 배터리: 리튬이온(리튬인산철 아님, 본인이 헷갈렸다가 정정). 일상 사용 시 1~2년 정도면 성능 저하 예상.

## 소프트웨어 스택 (OS, SDKs, frameworks, models, languages, sim tools)
- Unitree 공식 SDK: GitHub 공개, C++ 기반 예제(high-level / low-level) 제공. 문서(매뉴얼 28쪽, 절반은 중국어)와 온라인 문서 있으나 "읽고 바로 개발 시작"하긴 부족하다고 평가(그래도 타 로보틱스 대비 상대적으로 양호).
- DDS(Data Distribution System) 통신, 약 2ms 주기 저수준 제어 루프 — 이런 결정론적 저수준 제어(균형 유지 등)는 Python으로 신뢰 못하고 C++ 영역이라고 판단. 반면 "토르소 높이", "손 목표 위치" 같은 고수준 명령은 Python으로 보내도 무방.
- 개발 도구: OpenAI의 터미널 에이전트 Codex + 모델 "03"(자막 표기, 문맥상 OpenAI o3 모델을 지칭하는 것으로 보임 — 확실친 않음) 사용. 이 LLM에게 "Python API를 만들어달라"고 요청해서 C++ SDK를 감싸는 Python wrapper(facade)를 제작.
- 네트워크: 로봇 내부 컴퓨터 192.168.123.161(외부 접근 불가), 보조 개발보드(Jetson) 192.168.123.164 (SSH 계정 unitree, 기본 비번 "123" — 즉시 변경 권장, root 권한급 위험 경고).

## 만드는 과정 — 순서대로 (what he tried first, next, ... in chronological order; the actual workflow)
1. 언박싱 → 임시 거치대(게임 행거)로 로봇을 안전하게 매달 방법부터 확보.
2. 공식 매뉴얼/온라인 문서 확인 → SDK GitHub 저장소 확인, high-level/low-level C++ 예제 구조 파악.
3. 이더넷 유선으로 Jetson 보조 컴퓨터에 연결(듀얼 LAN: 하나는 로봇용, 하나는 인터넷용), subnet 123 설정 확인.
4. 가장 기본적인 공식 예제(ankle swing, low-level)부터 실행 — 초기화 → 준비 → 발목을 계속 앞뒤로 움직이는 상태로 진입하는 것을 확인, 통신/빌드가 제대로 됐는지 검증하는 용도.
5. C++ 저수준 코드가 너무 장황해서(300줄대에 실제 로직) Python으로 감싸는 API가 필요하다고 판단 → Codex/o3에게 요청해 C++ wrapper + Python facade 제작.
6. Python API로 로봇을 제어하려다 계속 "감쇠(damp) 상태까지는 가는데 균형 잡힌 보행 상태로 못 감" 문제에 부딪힘 → 발에 충분한 압력/접지가 있어야만 balance stand 진입이 허용된다는 것을 LLM과 함께 예제를 하나씩 뜯어보며 알아냄.
7. 상태 순서를 지켜야 함을 발견: damp → (단순) stand up("멍청한 직립", 균형 아님) → 다리를 서서히 펴는 루프를 반복 실행해야 어느 순간 자동으로 balance stand 진입 → stand height 설정 → continuous gait(보행) 진입.
8. R&D 스크립트로 실제 시연: damp → 기립 → balance stand 진입 성공, 로봇을 밀고 당겨도 스스로 균형 복원(다리 안 움직이고 모터 힘만으로) 확인.
9. R&D walk 스크립트로 전진 시연: bot_move(전진/좌우/회전 속도, 지속시간) 같은 함수 사용, continuous=True 플래그 필요, 그리고 명령을 자주(약 5초 이내) 재전송하지 않으면 안전 메커니즘으로 continuous gait 상태에서 자동 이탈함을 발견.
10. FSM state(모드: 0=balance stand, 1=continuous gait)를 쿼리해 디버깅하는 방법 정리, 다음 영상 계획(손 API, 팔 위치제어, LiDAR/뎁스카메라 API 연동)으로 마무리.

## 막힌 곳과 해결법 (failures, bugs, surprises, and how he debugged or worked around them)
- gantry가 주문에 포함되는지 Unitree와 RoboStore 사이 답변이 엇갈림 → 결국 임시 거치대로 대체.
- 라이브 데모 중 R&D 스크립트가 갑자기 안 됨 → ping으로 연결 확인, 재시작(restart)으로 해결(원인 불명).
- 가장 큰 삽질: "균형 잡힌 기립"에 도달하는 조건(발 압력 + 상태 진입 순서)이 문서화돼 있지 않아, 예제 코드를 뜯어보고 LLM과 대화하며 경험적으로 알아냄.
- 다리를 서서히 펴는 반복 루프가 왜 필요한지(정적으로 한 번에 목표 높이를 설정하면 왜 안 되는지) 본인도 끝까지 이해하지 못함 — "왜 되는지 모르겠다"고 명시적으로 밝힘.
- continuous gait 진입 후 짧은 시간 내 새 명령을 안 보내면 로봇이 안전상 자동으로 gait 모드를 이탈하는 것을 원인 모른 채 헤매다가 발견.

## 수업 개념과 연결 (any link to KF / PF / PID / SLAM / localization / path planning / control loops / RL; write "없음" if none — do not invent links)
없음 — 이 영상은 언박싱과 초기 소프트웨어 아키텍처(상태 머신, Python/C++ 분리) 탐색에 집중되어 있고, KF/PF/PID/SLAM/경로계획 관련 내용은 등장하지 않음.

## Paul의 Hardware Challenge에 주는 교훈 (concrete, 2–5 bullets)
- 헤드라인 가격 외에 부속 장비(거치대/짐벌, 케이블, 어댑터 보드 등) 비용과 리드타임을 반드시 별도로 확인할 것 — Freenove/XGO-mini2/Jetson Orin Nano Super 조합도 액세서리 예산을 따로 책정해야 함.
- 액추에이터가 있는 로봇을 다룰 땐 초기 개발 단계에서 "안전하게 매달거나 고정할 방법"부터 확보하는 것이 우선 — Paul의 챌린지 플랫폼에서도 초기 테스트 시 낙하/충돌 위험을 줄이는 지그(jig)나 받침대를 먼저 마련하는 게 좋음.
- 저수준 결정론적 제어(예: PID 루프)는 빠른/실시간 언어 영역에, 고수준 명령은 Python으로 분리하는 구조가 실전에서 잘 작동함 — Paul이 마이크로컨트롤러+PC 조합을 쓸 경우 이런 역할 분리를 참고할 만함.
- SDK/펌웨어가 특정 상태 순서를 요구하는 경우가 흔함(예: 조건 충족 전엔 명령 거부) — 처음부터 상태를 조회/로깅하는 디버깅 도구를 만들어 두면 삽질 시간을 크게 줄일 수 있음.
- 문서가 부실한 SDK를 다룰 때 LLM(코딩 에이전트)에게 "예제를 읽고 Python wrapper를 만들어달라"고 시키는 접근이 실제로 개발 속도를 크게 높였다는 점 — Paul도 Freenove/XGO SDK가 빈약하면 유사 전략을 고려할 만함.

## 확인 필요 (anything ambiguous in the captions — mark as uncertain rather than guessing)
- "03"이 실제로 어떤 모델(예: o3)을 가리키는지는 자막 표기라 확실하지 않음(문맥상 OpenAI 모델로 추정).
- 머리의 상하 움직임이 실제 addressable 모터/자유도인지 여부는 본인도 모른다고 명시.
- gantry 가격이 자막에서 "$1,500"와 "$1,600"으로 혼재해 언급됨 — 정확한 금액 불확실.
- 보조 컴퓨터가 "Jetson Orin NX"인지 자막 중간에 "Nano Jetson"으로도 언급되어 표기가 오락가락함 — 정확한 모델명 불확실.
