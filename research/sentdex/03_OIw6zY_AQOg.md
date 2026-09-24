# 03 — Everything is LLM - Vibe coding a robot task

- 한 줄 요약: XGO mini2(다리+바퀴 하이브리드 quadruped + arm)를 로컬 워크스테이션에서 구동하는 GLM 5.3 Flash LLM으로 고수준 제어(웹 UI 생성, gait 제어, 물체 탐지, 바닥의 초록 큐브를 approach→grab→들어올리기까지)하는 전 과정을 실시간으로 보여주는 영상. VLA/teleop 대신 "LLM이 다 한다"는 철학을 실증.
- 로봇 관련성: 높음 (Paul이 실제로 고려 중인 구성과 거의 동일 — 매우 상세히 정리)

## 하드웨어 (robot, sensors, actuators, compute board, prices if stated)
- 로봇: XGO mini 2-wheel robot (자막상 "XGO mini two-wheel robot", BRIEF에서 말하는 XGO-mini2로 추정). Sentdex는 이 회사를 5년 넘게 팔로우했고 quadruped 계열 로봇을 4대 보유(그중 2대는 arm 장착, LiDAR로 추정되는 "LAR" 장착 모델은 없음 — 자막 표기 불확실).
- 신규 특징인 바퀴(wheels): 다리 끝에 달려 있어 (a) 다리로만 걷기(stepping only), (b) 바퀴로만 굴러가기(wheels only), (c) 걷기+바퀴 동시 구동(mixed) 3가지 gait 모드 지원. 턱/단차를 넘을 때 다리만으론 걸리는 경우가 있는데 바퀴가 돌면서 당겨 넘어가게 해줌.
- Arm: shoulder 회전(신규 특징), elbow joint, gripper. 카메라는 머리(head)에 고정되어 있어 그리퍼가 종종 카메라 시야를 가리는 설계상 한계 지적 — 향후 그리퍼에 카메라를 달거나, 팔뚝/집게를 더 길게 하거나, 카메라 위에 거울 달린 후드를 씌우는 개선안을 제안(미실행, 아이디어 수준).
- 배터리: 로봇 내장형이라 교체 불가, 사용 방식에 따라 약 30~40분 지속. 이번 버전은 충전 중에도 동작 가능(이전 버전들은 불가능했음) — R&D 세션에 매우 유리. 그래도 배터리 밸런스를 위해 주기적으로 충전 사이클은 돌리는 게 좋다고 언급.
- 카메라 3대: 로봇 정면(head) 카메라, 측면(side) 카메라, 그리고 디버깅용 별도 USB 로지텍(Logitech) 웹캠.
- 온보드 컴퓨트: 로봇 자체에 "라즈베리파이 제로(Raspberry Pi Zero)"가 탑재되어 있다고 언급(그러나 이번 실습에서 LLM 추론은 로봇이 아니라 별도 로컬 워크스테이션에서 수행하고 WiFi로 로봇과 통신함 — 로봇 자체 컴퓨트는 저수준 SDK 명령 수신/서보 구동 정도 역할로 추정).

## 소프트웨어 스택 (OS, SDKs, frameworks, models, languages, sim tools)
- 고수준 제어 LLM: GLM 5.3 Flash (자막상 "GLM53 Flash"로 반복 표기, NVFP4 양자화로 로컬 워크스테이션에서 구동, 약 200 tokens/sec). 비교 대상으로 더 크고 똑똑하지만 훨씬 느린 "Astra"(자막상 모델명, 정확한 실제 이름 불확실)도 언급됨 — 실시간 루프에는 Astra가 너무 느려서 부적합하다고 결론.
- Vision 물체 탐지: 기본은 HSV color mask(단순 OpenCV 색상 필터링, 초록 큐브 탐지용). 더 일반적인 물체에는 Segment Anything(SAM) 계열 모델을 대안으로 언급. GLM 5.3 Flash를 vision LLM으로 써서 바운딩 박스를 직접 뽑는 것도 가능하다고 시연/언급 (약 200~500ms/회, 최대 약 3fps).
- Speech-to-text: 로컬 Whisper (클라우드 STT 서비스는 프라이버시 이유로 명시적 거부 — Google Takeout에서 5년 넘은 "Hey Google" 음성 기록이 남아있던 경험을 근거로 듦).
- 로봇 SDK, URDF 파일, STL 메쉬 파일을 통째로 LLM에 복사-붙여넣기하는 방식으로 컨텍스트 제공 (21/20번 영상과 동일한 패턴).
- 웹 기반 front-end(카메라 스트리밍 + gait/arm 컨트롤 버튼)를 LLM이 처음부터 생성.

## 만드는 과정 — 순서대로
1. 새 작업 폴더 생성(자막상 "Xcode" — XGO를 의도한 오타로 추정, 불확실), 터미널 오픈.
2. GLM 5.3 Flash(NVFP4)를 로컬에서 쓰기로 결정.
3. SDK 문서, URDF, STL 메쉬, WiFi 정보(IP+비밀번호)를 통째로 복사-붙여넣기("copy pasta")해서 LLM에 컨텍스트로 제공.
4. 로봇 전원을 깜빡하고 안 켠 것을 뒤늦게 발견, 전원 켜고 재시도.
5. 이후 프롬프트는 대부분 로컬 Whisper로 음성 받아쓰기하여 입력.
6. 요청: 헤드/사이드/로지텍 3개 카메라 스트리밍 + 전후진/회전/body height/IMU 기반 body tilt 조절 + 3가지 gait 모드 전환이 가능한 기본 웹 UI 제작.
7. 처음 생성된 UI는 버튼을 눌러도 전혀 반응 없음 → "테스트도 안 해보고 다 됐다고 하지 말라"고 강하게 지적, 재작업 지시.
8. 재작업 후 부분적으로 동작하지만 명령 반응이 5초 이상 지연되는 심각한 lag 발생, wheels-only 모드는 힘이 너무 약해 아예 못 움직임.
9. "floor pickup pose"(바닥 물체를 집기 위한 자세) 목표 설정: body height 75mm, IMU pitch 목표 약 18~22도를 매번 일관되게 재현해야 함 — 그러나 같은 명령을 내려도 실제 측정치가 매번 달라 반복성 문제 발생.
10. 사람이 실시간으로 관절 각도(elbow -41°/그리퍼 open -65°/shoulder 등)를 직접 조정해보며 LLM과 함께 정확한 조합을 찾고, "이 조합을 floor pickup pose 함수로 코드화해달라"고 요청.
11. LLM이 로봇을 상대로 여러 관절값을 직접 시도(ablation)하며 반복 수렴 → 최종적으로 일관된 floor pickup pose(elbow 먼저 풀기 → gripper open → shoulder 하강 순서, 그리퍼가 카메라 바로 앞에 오도록) 확보.
12. HSV 마스크 기반 "cube detection" 추가.
13. 접근(approach) 알고리즘 설계: 큐브 발견 시 IMU pitch를 14~17도로 낮춤 → 큐브가 화면 하단을 꽉 채우고 "그 아래 픽셀이 없음"을 정지 조건으로 삼아 전진 → floor pickup pose 진입 → 팔 전개(elbow→gripper open→shoulder 하강 순서)하여 grab.
14. 근접 미세조정용 "nudge"(소폭 전후진/회전/strafe) 명령 추가 — 이 중 다수(회전 nudge, strafe)는 버그로 동작 안 함, nudge-forward와 전체 회전만 안정적으로 동작.
15. 수동 end-to-end 테스트 1차 성공(접근→정렬→pose→grab)이지만, 팔을 다시 집어넣을 때(stow) shoulder를 elbow보다 먼저 움직여 로봇 자신의 머리에 부딪히는 버그 발견.
16. "auto pickup" 버튼으로 전체 시퀀스 자동화를 요청 — 초기 자동화는 탐지 지연, stow 시 얼굴 충돌 반복, 그리퍼 힘 부족(큐브를 집어도 움직이지 않음)으로 실패, stow 중 큐브를 머리에 문질러 떨어뜨림.
17. 매 라운드 구체적 버그 리포트(더 세게 grab, stow 시 얼굴 먼저 피하고 elbow부터 움직이기)를 주고 LLM이 반복 수정하도록 맡김(사람은 아침 식사하며 대기).
18. 최종적으로 완전 자동 루프 성공: 큐브 탐지 → 회전으로 중앙 정렬 → 접근 → 자세/높이 검증 → grab range 도달 → 이번엔 충분히 세게 grab → 떨어뜨리지 않고 들어올려 성공. 여기서 영상 종료(박스에 담기 등 후속 단계는 향후 과제로 남김).

## 막힌 곳과 해결법
- 초기 웹 UI 버튼이 전혀 작동 안 함 (LLM은 "완료했다"고 주장) → 강하게 재검증 요구, 재작업으로 부분 해결.
- 명령 반응 5초 이상 지연 / 이후 "control resource busy" 류 에러도 관찰 → 근본 원인 명확히 규명 안 됨 (불확실).
- wheels-only 모드 힘 부족으로 이동 불가 → 별도 수정 필요 항목으로만 플래그, 완전 해결 여부 불명확.
- floor pickup pose의 IMU pitch가 매번 다르게 나오는 반복성 문제 → 사람이 실시간 관측하며 LLM과 함께 관절값을 직접 튜닝(사실상 수동 ablation)해서 해결.
- 팔이 stow 시 자기 머리/카메라에 부딪히는 문제(관절 이동 순서 오류: shoulder를 elbow보다 먼저 움직임) → 순서를 "elbow 먼저, shoulder 나중"으로 고치도록 여러 차례 피드백 후 해결.
- 여러 "nudge" 미세조정 명령(회전, strafe)이 버그로 동작 안 함 → 영상 내에서 완전히 해결되지 않고 우회(전체 회전/nudge-forward만 사용).
- 첫 성공 grab에서 그리퍼 힘 부족으로 큐브가 미끄러짐 → "더 세게 잡아라"라는 피드백으로 다음 라운드에 해결.
- LLM이 "claw lock overreach", "recheck claw after gate fix" 같은 자기 진단 코멘트를 내놓음 — sentdex는 이런 자기 충돌류 버그가 반복 재발하는 걸 보고 "로보틱스 전용 하네스(harness)"가 필요하다고 제안(코딩 에이전트 하네스처럼, URDF/메쉬 정보로 자기 충돌을 자동으로 사전 차단하는 계층).

## 수업 개념과 연결 (KF / PF / PID / SLAM / localization / path planning / control loop / RL과 연결)
- 직접적인 KF/PF/SLAM 언급이나 구현은 없음.
- "목표 IMU pitch(예: 18도)를 반복 명령마다 일관되게 못 맞추는 문제"는 본질적으로 setpoint tracking/제어 문제인데, 이 영상에서는 PID 같은 체계적 제어기 없이 순수 trial-and-error(수동 ablation)로 우회함 — Paul의 수업에서 배운 PID를 여기 적용하면 훨씬 체계적으로 풀릴 법한 지점.
- 접근(approach)~정지 로직은 "큐브가 프레임 하단을 채우고 그 아래 픽셀이 없으면 멈춤"이라는 순수 rule-based reactive 제어이며, 학습된 정책이나 모델 기반 제어는 아님.
- 향후 계획으로 "LiDAR로 추정되는 LAR를 이용해 occupancy grid를 만들고 방 안에서 위치를 파악해 물건을 담을 박스(dropbox) 위치를 찾겠다"는 아이디어를 언급 — 이는 SLAM/localization 개념과 직접 연결되나, 이번 영상에서는 구현되지 않은 향후 계획일 뿐.
- 다리 보행(gait)/걷기 자체는 LLM이 아니라 강화학습(RL)으로 사전 학습된 정책이 처리한다고 명시("30분이면 학습 끝나는 문제") — LLM은 고수준 task planning/perception 담당, 저수준 locomotion은 RL 담당이라는 계층 분리를 명확히 함.

## Paul의 Hardware Challenge에 주는 교훈
- 이 영상의 구성(XGO-mini2 + 로컬 워크스테이션에서 돌리는 LLM + WiFi 통신)은 Paul이 온보드로 고려 중인 Jetson Orin Nano Super 구성과 다르다는 점에 유의: 영상에서 LLM 추론은 로봇 탑재 Pi Zero가 아니라 별도의 다중 GPU 로컬 워크스테이션에서 이뤄짐. Jetson Orin Nano에서 이 정도 속도(200 tokens/sec, 200~500ms/detection)를 그대로 기대하기는 어려움 — 온보드 vs 오프보드 추론 구성을 먼저 결정해야 함.
- "LLM은 고수준 인식/판단, RL/기존 SDK는 저수준 보행 제어"라는 계층 분리가 핵심 — Hardware Challenge 요구사항(센서 읽기+액추에이터 구동+course algorithm 하나)을 만족시키려면, 과제로 요구되는 KF/PF/PID/SLAM 모듈을 LLM이 담당하는 고수준 로직과 명확히 분리된 독립 모듈로 설계하는 게 안전.
- Vision 물체 탐지는 무거운 VLM보다 HSV color mask 같은 단순 OpenCV 기법으로 먼저 시작하고, 실패할 때만 SAM/VLM으로 폴백하는 전략이 실시간 루프에 유리함 (VLM 호출은 최대 ~3fps 수준). 센서 업데이트 주기가 중요한 KF/PF 구현에서는 이 속도 차이가 설계에 직접 영향을 줌.
- 로봇의 자기 충돌(팔이 자기 머리/카메라에 부딪힘) 버그는 LLM이 반복적으로 재발견하는 경향이 있었음 — URDF/메쉬 정보를 사전에 LLM에 줘도 자동으로 완전히 피하지는 못함. 실제 하드웨어 조립 전에 사람이 먼저 자기 충돌 가능 지점을 점검해두면 시간 절약.
- "목표 각도를 일관되게 맞추기 어렵다"는 문제는 사실상 PID로 풀 수 있는 setpoint tracking 문제였는데 이 영상에서는 순수 trial-and-error로 우회함 — 바로 이 지점("자세 안정화")에 수업에서 배운 PID를 직접 적용하는 것이 Hardware Challenge의 좋은 프로젝트 앵글이 될 수 있음.
- 큰 목표(approach→grab→lift 전체 자동화)를 한 번에 요청하지 않고, 먼저 개별 버튼(전진/회전/gait 모드/IMU 타겟/arm pose)으로 서브 기능을 하나씩 검증한 뒤 자동화로 묶는 점진적 개발 방식이 효과적이었음 — Hardware Challenge도 알고리즘 통합 전에 센서 읽기/액추에이터 구동을 각각 먼저 검증하는 순서를 그대로 적용할 수 있음.
- 충전 중에도 동작 가능한 로봇(이 XGO-mini2 최신 버전)을 고르면 R&D 세션이 훨씬 편함 — Freenove/XGO 후보 비교 시 이 스펙도 확인할 가치 있음.
- 프라이버시를 위해 로컬 Whisper로 음성 입력을 받는 워크플로가 실제로 잘 작동했다는 점도 재현 가능한 아이디어.

## 확인 필요
- "LAR"가 LiDAR를 가리키는 자막 오타인지 불확실 (문맥상 "using the LAR로 occupancy grid를 만든다"는 언급이 있어 LiDAR로 추정되나 확정 안 됨).
- 정확한 LLM 모델명 "GLM 5.3 Flash"가 자막에서 "GLM53 Flash", "GLM 53" 등으로 반복적으로 뭉개져 표기됨 — 실제 정식 모델명과 다를 가능성 있음 (자동 캡션 오타로 추정).
- 비교 대상 모델명 "Astra"("GBD6 Astra" 등으로도 표기됨)도 정확한 실제 모델명인지 불확실.
- 작업 폴더명이 자막상 "Xcode"로 나오는데 문맥상 "XGO"를 의도한 것으로 추정되나 확정 안 됨.
- "extreme scale"이라는 표현이 실제로 어떤 시뮬레이션/RL 툴(예: Isaac Gym/Isaac Lab)을 가리키는지 불확실, 자막 오타 가능성 있음.
- 로봇 정식 명칭이 "XGO mini 2-wheel robot"인지 "XGO-mini2"인지 자막상 정확히 특정되지 않음 (BRIEF의 XGO-mini2 표기를 따랐으나 원문 자막 표현과는 약간 차이 있음을 밝혀둠).
