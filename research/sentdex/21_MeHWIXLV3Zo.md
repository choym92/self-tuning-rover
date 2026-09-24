# 21 — Vibe Coding Robot Hands w/ Cursor (Inspire RH56DFQ-2L/R)

- 한 줄 요약: Cursor 에이전트(Claude 3.7 Sonnet)에게 Inspire RH56DFQ-2L/R 로봇 손 매뉴얼 PDF를 통째로 복사-붙여넣기해서, RS485/Modbus 시리얼 통신부터 개별 finger 제어, open/close/pinch/point/three-finger grip gesture까지 약 1시간 만에 구현한 첫 시도 영상.
- 로봇 관련성: 높음 (하드웨어 시리얼 통신, actuator 제어를 처음부터 직접 다룸)

## 하드웨어 (robot, sensors, actuators, compute board, prices if stated)
- Inspire RH56DFQ-2L/R 로봇 손 (왼손 2L, 오른손 2R 각 1개씩 총 2개 보유). Finger는 thumb/index/middle/ring/pinky 5개.
- RS485-to-USB adapter (시스템에서 `/dev/ttyUSB0`로 인식), 전용 power brick(LED로 전원 상태만 표시, hand 자체엔 전원 표시등 없음).
- Actuator는 servo/motor로 굽힘(flexion)만 능동적으로 강하게 구동 가능하고, 펴는(extension) 힘은 고무줄(rubber band) 수준으로 약함 — 이 물리적 비대칭이 이후 20번 영상 crawling 설계의 핵심 제약이 됨.
- Baud rate 기본값 115200 (매뉴얼 명시). 매뉴얼상 "40 sets of actions" 저장 기능 언급되지만 이번 영상에서 사용/검증 안 함.
- 가격 언급 없음. G1 휴머노이드는 "$16,000"이라 광고되지만 실제로는 "contact for real price"였다는 사담(제품 자체와 무관).

## 소프트웨어 스택 (OS, SDKs, frameworks, models, languages, sim tools)
- Cursor IDE, agent 모드, Claude 3.7 Sonnet (auto-select 옵션은 끔 — 켜두면 명령 실행 결과가 채팅창이 아닌 별도 창에 나와서 소통이 끊긴다고 불만).
- Python 3.10 명시적으로 지정 요청 (시스템 `python`/`python3` 기본값이 3.8로 잡혀 있어 버전 혼동 발생).
- pyserial 기반 통신. 최종적으로 Modbus protocol 사용. `inspire_hand.py` 약 770줄 생성, README, interactive CLI 스크립트까지 자동 생성.

## 만드는 과정 — 순서대로
1. PDF 매뉴얼 전체를 Cmd+C로 복사해 Cursor 채팅창에 그대로 붙여넣기 (Cursor가 PDF 직접 읽기를 지원하지 않아서).
2. "Python으로 이 손과 통신하는 코드를 작성해달라"고 요청 → 에이전트가 모듈 구조/README/example 스크립트를 자동 생성.
3. Python 버전 충돌(3 vs 3.10)로 시간 소모, 재지정.
4. 포트 찾고 실행 → 처음엔 손이 전혀 반응 없음 (통신 실패).
5. 시리얼 모니터 스크립트를 만들어 raw data 확인, baud rate를 바꿔보는 등 시도 → 여전히 무응답.
6. RS485 레벨에서 자체 binary 프로토콜을 직접 구현 시도 → 실패.
7. Modbus protocol로 전환 → 에러 레지스터 read 성공 (첫 응답 확인).
8. 실제로 손가락이 움직이기 시작, 여러 grip 동작 성공 확인.
9. Interactive CLI 스크립트 제작 → open/close/pinch/three-finger grip/point 명령 시도.
10. "point" gesture가 처음엔 middle finger로 잘못 나감 → index finger로 고쳐달라고 요청, 수정됨.
11. 개별 finger index + 각도 지정 방식 발견 (position 0=추정상 thumb 회전, 1=pinky, 2=ring, 3=middle, 4=index, 5=thumb flex — 확정 아님).

## 막힌 곳과 해결법
- RS485 자체 프로토콜 무응답 → Modbus protocol로 전환해서 해결 (RS485는 물리 계층, Modbus는 그 위의 통신 프로토콜이라는 개념을 이때 처음 배움).
- 방금까지 동작하던 명령이 갑자기 무반응 (baud rate/전원/연결 문제 아님, 원인 불명) → 재시도하니 다시 동작. 근본 원인은 특정 못함 (불확실).
- "point" gesture가 middle finger로 실행되는 버그 → finger mapping 수정으로 해결.
- 특정 finger 각도 지정 시 "failed" 에러 (엄지가 물리적으로 다른 finger의 펴짐을 막고 있었을 가능성) → 명확한 원인 규명은 안 됨.
- Cursor의 auto-select 모드가 켜져 있으면 명령 실행 로그가 채팅창에 안 보임 → 꺼서 해결.

## 수업 개념과 연결
없음. KF/PF/PID/SLAM/localization/path planning/control loop/RL 등 직접 언급 없음. 다만 서보 actuator + 시리얼 프로토콜(RS485/Modbus) 통신 스택을 처음부터 구축한 경험은 향후 어떤 course algorithm을 얹든 그 아래 계층(하드웨어 통신)의 참고 사례가 됨.

## Paul의 Hardware Challenge에 주는 교훈
- 로봇 벤더 문서가 PDF 매뉴얼만 있고 Python 예제가 전혀 없어도, LLM 에이전트에게 PDF 원문 전체를 복사+붙여넣기하면 통신 프로토콜 코드를 처음부터 생성해낼 수 있음 — Freenove/XGO 등 문서가 부실한 하드웨어에도 바로 적용 가능한 전략.
- 물리 계층(RS485)과 상위 프로토콜(Modbus)을 구분하지 못하면 몇 시간을 낭비할 수 있음 — 센서/액추에이터 데이터시트에서 이 둘을 미리 구분해 확인해둘 것.
- "방금까지 되던 게 갑자기 안 됨 → 재시도하면 됨" 같은 비결정적 실패가 실제 하드웨어 vibe coding에서 흔하게 발생함 — 재현 가능한 디버깅 스크립트(serial monitor 등)를 미리 준비해두면 유용.
- Baud rate, USB 포트, Python 버전 같은 환경설정 문제가 실제 제어 로직보다 시간을 더 잡아먹을 수 있음 — Hardware Challenge 착수 전 환경(usb driver, python venv)부터 검증할 것.
- Cursor의 auto-select/YOLO 모드는 실행 로그가 안 보여 디버깅에 불리함 — 실습 시에는 단계별로 직접 확인하는 워크플로가 낫다.

## 확인 필요
- "40 sets of actions" 저장 기능이 정확히 무엇인지 불명확 (매뉴얼 언급만 있고 실제 사용/검증 안 함).
- Finger index 0번이 정확히 thumb rotation인지는 영상 속 추정일 뿐 확정되지 않음.
- "action sequence"가 하드웨어 자체 온보드 기능인지 소프트웨어 레이어 기능인지 불명확.
