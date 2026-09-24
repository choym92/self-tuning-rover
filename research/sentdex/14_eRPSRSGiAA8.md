# 14 — Testing VLMs and LLMs for robotics w/ the Jetson Thor devkit
- 한 줄 요약: NVIDIA Jetson Thor devkit(128GB 통합메모리, 273GB/s 대역폭, 130W) 리뷰. 로컬 LLM(Qwen3 계열)과 VLM(Moondream 2)을 올려 속도를 측정하고, "메모리는 많은데 대역폭은 느린" 특성을 활용한 pipeline parallelism(다중 서버 병렬 추론)으로 VLM FPS를 2→30까지 끌어올리는 기법을 시연.
- 로봇 관련성: 높음 (Paul이 비교 중인 Jetson Orin Nano Super와 같은 Jetson 제품군의 상위 모델 리뷰이므로 온보드 연산 판단에 참고 가치 큼. 단, 이 영상엔 Orin Nano Super 자체 수치는 나오지 않음)

## 하드웨어
- **Jetson Thor devkit**: 128GB 메모리(비디오 메모리와 공유되는 통합 메모리), 메모리 대역폭 273GB/s, 가격 약 $3,000~3,500, 전력 130W(최대 파워 모드, USB-C로 전원 공급). 실제 로봇에 탑재될 연산 모듈은 데브킷의 방열판/팬을 제외한 작은 보드 하나("T5000 board"로 추정, 불확실)이며 나머지는 캐리어보드+쿨링.
- 포트: 5GbE 이더넷 1개, 4x25Gbit 포트(합계 100Gbit급이지만 실측 처리량은 약 12GB/s 수준으로 병목 있음).
- CPU 코어 수: 14코어 (참고로 DGX Spark는 20코어).
- 비교 대상:
  - RTX 5090: 메모리 대역폭 약 1,790GB/s대(Thor의 273GB/s는 GPU 기준으로는 느림).
  - CPU/RAM 서버급 시스템 기준으로는 273GB/s가 오히려 빠른 편(듀얼 CPU 서버급 필요).
  - Puget Systems 머신(sentdex 개인 보유): RAM 1TB, 대역폭은 측정 안 했지만 150~180GB/s 정도로 추정(불확실).
  - 현재 G1에 탑재된 보드: Orin NX, 메모리 16GB뿐 — Thor(128GB) 대비 압도적으로 적음.
  - DGX Spark(구 Project Digits): Thor와 스펙이 비슷(128GB, 273GB/s)하지만 20코어 CPU, 데스크톱 컴퓨팅 용도로 설계(로봇용 저전력 포지셔닝의 Thor와 용도가 다름). 아직 출시 전이라고 언급.

## 소프트웨어 스택
- PyTorch Docker 컨테이너 + FastAPI로 모델 서버 구동.
- **LLM**: Qwen3-Coder-30B-A3B (MoE, 총 128개 expert 중 8개만 활성화). 로컬 서버 응답 속도 6.8 tokens/sec — 코딩 에이전트로 쓰기엔 느림(본인 기준 20 tokens/sec 이상, 이상적으론 100+ 원함). Qwen3 480B(30B의 상위 형제)는 Thor에서 양자화해도(최소 약 160GB 필요 추정) 못 돌리고, 대신 Puget 1TB 머신에서 양자화 버전을 돌림.
- Open WebUI로 로컬 모델을 쉽게 질의하는 UI 사용.
- **VLM**: Moondream 2 — 오픈소스 VLM(제작자는 "한 명"이라고 언급, 스폰서 관계 아님). 지원 기능: short caption, long caption, visual query(질의응답), object detection(바운딩박스), point(좌표 포인팅). 특이점: 고정된 클래스 목록이 아니라 자유 텍스트로 아무 객체나(예: "빨간 물병", "전자레인지", "음식 데울 물건" 등) 탐지 가능한 open-vocabulary 모델. 본인 경험상 object detection보다 point(좌표 찍기)가 더 정확/안정적이라고 함(이유는 모름).
- Moondream 2를 Thor에서 단독 서버로 돌려 빨간 물병 탐지: 약 2 FPS, 서버당 메모리 약 5GB, 레이턴시 약 500ms(수치는 설명 편의상 예시로 든 것일 수 있음).
- **Pipeline parallelism 기법**: 메모리는 넉넉하지만 대역폭이 병목이라는 점을 이용해, Moondream 서버를 여러 개(2개, 10개, 15개) 동시에 띄우고 프레임을 라운드로빈으로 분배. 서버 1개당 레이턴시는 동일(~500ms)하게 유지되지만 처리량(FPS)은 서버 개수에 비례해 증가: 2개→약 2배, 10개→약 20FPS, 15개→약 30FPS. GPU 사용률은 최대 97%까지 관측. 15개 서버로 앙상블(평균) 판정을 하면 false positive/negative를 줄이거나, 서버별로 서로 다른 객체를 동시 추적하는 것도 가능하다고 설명.
- VLA(vision-language-action)는 아직 Thor를 실제 로봇에 연결하지 않아 테스트하지 못함(향후 과제로 남김).

## 만드는 과정 — 순서대로
1. Thor devkit 스펙 리뷰(메모리, 대역폭, 전력, 포트) 및 DGX Spark와의 혼동 우려 짚기.
2. BTOP으로 CPU/RAM(=GPU 메모리 공유) 모니터링, nvidia-smi는 신제품이라 아직 완전히 동작하지 않음(다른 구형 Jetson에서는 될 것으로 추정, 불확실).
3. PyTorch Docker 컨테이너 기동 → Qwen3-Coder-30B-A3B를 FastAPI로 서빙 → 로컬 머신에서 질의해 속도(6.8 tok/s) 및 질적 성능(예: 오래된 디젤 트럭의 고압 오일 펌프 시스템 지식) 확인.
4. Qwen3 480B도 다운로드해 Thor에서는 실패, Puget 1TB 머신에서 양자화 버전으로 시도.
5. Open WebUI 소개.
6. Moondream 2 VLM 소개 및 기능 시연(캡션, 쿼리, detection, pointing).
7. Moondream 2를 Thor에 단일 서버로 올려 빨간 물병 탐지 데모 → 2FPS로 느림 확인.
8. 문제(느린 FPS) 해결 아이디어로 "pipeline parallelism"을 LLM이 만들어준 UI로 시각화 설명 → 서버 개수를 2 → 10 → 15로 늘리며 FPS 개선을 실제로 시연, GPU utilization도 함께 관찰.
9. 실물 물병을 움직이며 15개 서버 버전의 부드러움(30FPS)을 시연.
10. 클로징: Thor vs DGX Spark 혼동 정리, Thor는 로봇용으로 최적(저전력 130W), 향후 Jeff의 등에 "백팩"처럼 부착할 계획이라고 언급(G1 몸체에 직접 내장은 불가능하다고 판단).

## 막힌 곳과 해결법
- 30B 모델 응답 속도(6.8 tok/s)가 코딩 에이전트로 쓰기엔 느림 → 해결책은 제시하지 않고 "정답을 한 번에 내면 느려도 낫다"는 트레이드오프만 언급.
- 480B 모델을 Thor에서 못 돌림(메모리 부족, 최소 양자화도 약 160GB 필요 추정) → 대안으로 1TB RAM Puget 머신에서 돌림(별도 영상 예고).
- Moondream 2 단일 서버로는 2FPS로 로보틱스에 쓰기엔 너무 느림 → 메모리가 남아도는데 대역폭이 병목이라는 특성을 이용해 다중 서버 병렬화로 해결(FPS 15배 개선).
- nvidia-smi가 신제품이라 완전히 동작하지 않음 → GPU 사용률 확인은 가능했으나 일부 지표는 불완전.

## 수업 개념과 연결
없음 — 이 영상은 LLM/VLM 추론 속도·아키텍처 비교가 중심이며 KF/PF/PID/SLAM 등 수업 알고리즘과 직접적 연결은 없음. (VLM의 object detection/pointing이 넓게 보면 "perception" 영역이라 SLAM의 관측(observation) 단계와 개념적으로 인접하긴 하나, 영상 내에서 그런 연결이 언급되지는 않으므로 억지로 잇지 않음.)

## Paul의 Hardware Challenge에 주는 교훈
- $3,000~3,500짜리 128GB Jetson Thor에서도 30B 모델이 6.8 tok/s, VLM이 서버 1개당 2FPS 수준이라는 점 — Jetson Orin Nano Super(Thor보다 훨씬 저사양, 메모리도 훨씬 작음)에서 무거운 VLM/LLM을 실시간으로 온보드 추론하는 것은 기대치를 낮게 잡아야 함. Hardware Challenge에서 지각(perception)이 필요하면 무거운 VLM보다 훨씬 가벼운 고전 CV/센서 기반 접근(코스의 KF/PF/SLAM과 궤를 같이하는 방식)이 현실적일 가능성이 큼.
- 로컬 신경망 추론의 실질적 병목은 흔히 raw 연산력(FLOPs)이 아니라 메모리 대역폭이라는 점 — Orin Nano Super 스펙을 볼 때도 대역폭 수치를 꼭 확인할 것(이 영상엔 Orin Nano Super 수치가 없으므로 별도로 찾아야 함).
- Moondream 2는 상대적으로 가벼운(서버당 약 5GB) open-vocabulary VLM이라 소형 보드에서도 이론상 돌아갈 가능성은 있지만, 이 영상에서 보여준 "다중 서버 병렬화로 FPS 확보" 기법은 메모리가 넉넉해야 가능한 전략이라 Orin Nano Super 같은 저메모리 보드에서는 그대로 쓰기 어려움.
- 전력 소모 관점: Thor가 130W인데도 "로봇 치고는 낮은 편"이라고 평가됨 — Orin Nano Super는 이보다 훨씬 낮은 전력(수 W~25W대)일 것으로 예상되며, 배터리 구동 관점에서는 유리하지만 그만큼 연산 여유는 더 적을 것.
- Jetson 제품군 내에서도 세대/모델 간 메모리 용량 차이가 매우 큼(Orin NX 16GB vs Thor 128GB) — Hardware Challenge를 위해 Orin Nano Super를 고를 경우, 이 영상에서 다룬 모델들(Qwen3-30B, Moondream 2)을 그대로 올릴 생각은 접고, 코스 과제(KF/PID/SLAM 등)에 필요한 만큼의 훨씬 가벼운 연산만 목표로 설계하는 게 현실적.

## 확인 필요
- 로봇에 실제 탑재되는 소형 보드의 정확한 모델명("T5000 board")은 자막상 불확실.
- Puget 머신의 메모리 대역폭(150~180GB/s)은 본인이 "측정 안 해봤다"고 명시한 추정치.
- 4x25Gbit 포트의 실효 대역폭("12점 9 정도, 실제로는 12GB/s 정도")은 자막이 매끄럽지 않아 정확한 환산치 불확실.
- nvidia-smi가 "완전히는 동작하지 않는다"는 설명의 정확한 원인(베타 소프트웨어 이슈로 추정)은 본인도 확실치 않다고 밝힘.
- Qwen3 480B의 최소 양자화 용량("약 160 몇 기가")은 자막상 어림값으로만 언급됨.
