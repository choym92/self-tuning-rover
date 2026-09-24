# 06 — The Right Harness is All You Need - For local Frontier AI
- 한 줄 요약: PCIe Gen5 스위치를 여러 머신에 붙여보며 안정화를 시도하는 하드웨어 여정과, 같은 모델이라도 코딩 하니스("Minion" vs "OM")에 따라 벤치마크 점수가 크게 달라진다는 것을 발견하는 영상. 배경으로 Unitree G1 로봇의 ACT 학습도 짧게 언급.
- 로봇 관련성: 중간 (본 내용은 하드웨어/하니스 벤치마크이지만, 말미에 G1 휴머노이드용 ACT 학습·LeRobot 라이브러리 언급이 있음)

## 하드웨어 (robot, sensors, actuators, compute board, prices if stated)
- PCIe Gen5 스위치(100 lane)를 새로 구매해 여러 머신(구형 box 머신, Dell Precision T2 tower, 옛 Puget 워크스테이션 등)에 연결 시도.
- 스위치 안정화의 핵심 조건: Resizable BAR(rebar) + Above 4G Decoding을 모두 지원하는 메인보드 필요. Dell T2 tower는 두 옵션이 켜져 있었는데도 스위치가 OS 부팅 후 계속 꺼짐(원인 불명, Dell 지원팀도 답을 못 줌).
- 결국 스위치 없이 예전 메인 컴퓨터(네이티브 x16 PCIe4 슬롯 2개)에 RTX Pro 6000 2장을 직결해서 이번 벤치마크 진행.
- Dell T2 tower는 PCIe5 지원하지만 슬롯 1개뿐인 초소형 데스크톱 — 조용하고 콤팩트해서 메인 워크스테이션 후보로 고려 중.
- 물리적 배선 설명(참고용): 리타이머(retimer) → MCIO 케이블 2개 → PCIe Gen5 스위치 → 추가 MCIO 케이블 → GPU 어댑터(각 GPU가 스위치 안에서 서로 직접 통신, 마더보드는 병목 아님). "리더 GPU"(전력을 100~150W 더 먹는 카드)는 발열 때문에 옆 카드와 간격을 더 둠.

## 소프트웨어 스택 (OS, SDKs, frameworks, models, languages, sim tools)
- 모델: GLM 5.2의 3.25 bit-per-weight 커스텀 quant(RTX Pro 6000 Discord 커뮤니티 멤버 "Will Falco" 제작, 코딩 전문가 레이어에 비트를 더 배분), DeepSeek V4 Flash 0731(7월 31일 업데이트판).
- 하니스 두 종류 비교: 자체 제작한 매우 단순한 "Minion" vs 다운로드한 "OM"(정확한 정체/철자 불확실 — 훨씬 더 반복적/장황하게 iterate하는 하니스).
- 벤치마크: terminal-bench v2.1 (89 task).
- 결과: GLM52(3.25bpw) + OM = 65/89(73%, 최고점), GLM52 without OM = 61/89(68%) → OM 도입 효과는 제한적. DeepSeek V4 Flash 0731 + Minion = 44/89, + OM = 64/89(72%) → 하니스만으로 20task차 개선(단, 발표자는 이후 "max thinking" 설정이 실제로 적용되지 않았을 수 있다는 의구심을 제기하며 재검증 필요하다고 밝힘).
- 토큰/초: GLM52(3.25bpw) ~75~100 tok/s, DeepSeek V4 Flash+DSpark ~350 tok/s(Gen5 스위치 덕에 향상, 코드 생성 시 400+ 피크).
- 해결까지 걸린 시간: OM 적용 시 GLM52는 약 2배, DeepSeek V4 Flash는 사용 토큰 수가 "엄청나게" 늘어남(수십만 토큰 단위, 정확한 수치는 다음 영상에서 표로 제시).

## 만드는 과정 — 순서대로 (what he tried first, next, ... in chronological order; the actual workflow)
1. PCIe 스위치를 여러 머신(구형 box, Dell T2, 옛 워크스테이션들)에 옮겨가며 rebar/Above4G 지원 여부 테스트 — 대부분 실패.
2. 결국 스위치 없이 기존 메인 컴퓨터에 2장 GPU 직결로 벤치마크 진행 결정.
3. GLM52 3.25bpw 커스텀 quant를 기본으로 벤치마크.
4. OM 하니스를 GLM52에 적용해봄 — 소폭 개선(61→65/89).
5. DeepSeek V4 Flash 0731(신버전)을 Minion으로 테스트 — 예상보다 낮은 점수(44/89)에 놀람("이 모델 쓰레기인가" 의심).
6. 서빙 백엔드 설정 문제를 GPT-5.6 Soul API로 고치려 시도했으나 실패.
7. DeepSeek V4 Flash 자신에게 "네 서빙 설정 문제를 고쳐봐"라고 요청 → 한 번에 문제를 해결(one-shot).
8. 같은 모델을 OM 하니스로 재벤치마크 → 64/89로 급상승, "하니스가 실제로 일을 한 것"이라 해석.
9. 영상 녹화 도중 "max thinking 설정이 실제로 적용되지 않았을 수 있다"는 점을 스스로 깨닫고 당혹 — 재검증을 예고.
10. 배경 작업으로 Unitree G1의 ACT(Action Chunking Transformer) 모델 학습을 돌리며, LeRobot 라이브러리가 G1을 네이티브 지원해 사용이 쉬웠다고 짧게 언급.

## 막힌 곳과 해결법 (failures, bugs, surprises, and how he debugged or worked around them)
- 여러 메인보드에서 rebar/Above4G Decoding이 켜져 있어도 PCIe 스위치가 부팅 후 오프라인이 되는 문제 — Dell 지원팀 문의도 실패, 원인 불명으로 남김. 결론: 스위치 구매 전 반드시 커뮤니티에서 검증된 보드인지 확인 필요.
- DeepSeek V4 Flash 0731의 time-to-first-token/prefill 속도가 예상보다 느려서 GPT-5.6 Soul API로 디버깅 시도했으나 실패 → 모델 자신에게 맡겨서 해결(모델이 백엔드 설정 문제를 스스로 원샷으로 고침).
- 벤치마크 점수 차이(44 vs 64)가 하니스 효과인지, "max thinking" 파라미터 미적용 버그 때문인지 확신하지 못함 — 재벤치마크가 필요하다고 스스로 인정(즉 이 영상의 결론 일부는 잠정적).

## 수업 개념과 연결 (any link to KF / PF / PID / SLAM / localization / path planning / control loops / RL; write "없음" if none — do not invent links)
- 없음 (영상 말미 ACT 학습 언급은 모방학습/로보틱스 맥락이나, KF/PF/PID/SLAM과 직접적 연결은 없음).

## Paul의 Hardware Challenge에 주는 교훈 (concrete, 2–5 bullets)
- "같은 모델도 하니스(에이전트 스캐폴딩)에 따라 성능이 크게 갈린다"는 결론은, Paul이 로봇에 어떤 형태로든 AI 플래너를 붙인다면 모델 선택 못지않게 "얼마나 반복/검증을 시키는가"라는 워크플로 설계가 중요하다는 점을 시사 — 다만 iterate를 많이 시킬수록 느려지므로 실시간 제어에는 부적합.
- 새 하드웨어(PCIe 스위치 등)를 여러 보드에 옮겨가며 rebar/펌웨어 문제로 며칠을 소모한 과정은, Jetson Orin Nano Super에 센서/액추에이터를 새로 연결할 때도 드라이버·펌웨어·전원 관련 디버깅에 예상보다 훨씬 많은 시간이 들 수 있다는 일반적 교훈으로 참고할 만함 — Hardware Challenge 일정(2026-12-10 마감)에 버퍼를 넉넉히 잡을 것.
- "벤치마크 결과가 설정 버그(max thinking 미적용) 때문일 수 있다"를 스스로 인정한 장면은, Paul이 로봇 실험에서 결과가 이상하면 알고리즘보다 먼저 센서 캘리브레이션/설정 파라미터부터 의심해봐야 한다는 실험 방법론적 교훈으로 연결.
- Unitree G1 + LeRobot으로 ACT를 쉽게 학습했다는 언급은, LeRobot 같은 생태계가 소형 로봇에도 있다면(예: 팔이 달린 로봇 킷) 데모 기반 모방학습 실험의 참고가 될 수 있으나, 이는 Hardware Challenge가 요구하는 "수업에서 배운 알고리즘"과는 무관하므로 직접 활용 대상은 아님.

## 확인 필요 (anything ambiguous in the captions — mark as uncertain rather than guessing)
- "OM" 하니스의 정확한 정체(제품명, 철자)는 자막에서 발음으로만 등장하여 불확실 — 실제 도구명이 다를 수 있음.
- GLM 5.2 3.25bpw quant 제작자 이름 "Will Falco"는 자막 표기 그대로 옮겼으나 철자 정확도는 불확실.
- DeepSeek V4 Flash 0731의 "max thinking 미적용 버그" 관련 내용은 발표자 본인도 확신하지 못하며 재검증을 예고한 상태 — 이 영상 내 벤치마크 수치(특히 OM 적용 44→64 상승폭)는 잠정치로 간주해야 함.
