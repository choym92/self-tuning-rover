# 10 — Could Open Source AI be Banned?

- 한 줄 요약: sentdex가 이전 영상(GLM-5.2 로컬 구동 소개)에 대한 후속으로 "5만 달러짜리 컴퓨터가 없어도 로컬 AI를 돌릴 수 있다"는 점을 반박·보충하고, Anthropic의 오픈소스 AI 규제 로비(NSA 해킹 루머, 2024년 "sleeper agents" 논문 등)를 비판하며, 저사양 GPU에서 돌릴 만한 소형 모델과 로컬 구동 도구(llama.cpp, Hermes, Minion)를 소개하는 영상.
- 로봇 관련성: 낮음 (로봇 관련 내용 없음, 다만 로컬 컴퓨팅/오픈소스 모델 선택지 언급은 어느 정도 참고 가치 있음)

## 하드웨어 (robot, sensors, actuators, compute board, prices if stated)
- 화자 본인 환경: RTX Pro 6000 x4 + 새 파워서플라이(12핀 레일 2개로 케이블 정리).
- 시청자 대상 권장: "3090이나 4090 한 장이면 필요 작업의 70~90%는 로컬로 커버 가능", 최소 스펙으로 "1,500달러짜리 GPU"면 충분하다고 강조.
- "VRAM 24GB 이상이면 소개하는 소형 모델들을 쾌적하게 돌릴 수 있다"고 언급.

## 소프트웨어 스택 (OS, SDKs, frameworks, models, languages, sim tools)
- GLM-5.2 양자화 단계별 비교: 2bit(약 217GB)까지 낮춰도 실사용상 큰 차이를 못 느꼈다고 주장. 단, "8bit KV 캐시는 공짜"라는 통념이 GLM-5.2에는 안 통하며, 1K~8K 컨텍스트부터 품질 저하가 체감되어 16bit KV 캐시가 필요하다고 지적.
- 벤치마크 도구: Terminal-Bench v2.1(장기 에이전틱 코딩/터미널 벤치마크)로 양자화 단계를 직접 비교 중(결과는 미완, 다음 영상 예고).
- 저사양용 로컬 모델 추천: Qwen3-Coder(80B total/약 3B activated로 추정), Qwen3 계열 MoE 소형 모델(자막상 "Quen 3635B A3B", Unsloth의 MTP 버전 언급, 정확 명칭 불확실), DeepSeek V4 Flash.
- 구동 엔진: llama.cpp + GGUF(가장 애용, 고강도 양자화에도 관대함) vs vLLM/SGLang(더 빠르지만 메모리 더 필요, NVFP4 빌드 언급) — GPU 전용/GPU+CPU 오프로드/CPU+RAM 전용/통합메모리(Mac mini, DGX Spark, Dell GB10 등) 구동 방식 다양하다고 소개.
- 코딩/에이전트 하네스 2종 실시간 비교: Hermes(범용 에이전트, OpenClaw 유사, 웹서치·메신저 연동 등 뭐든 가능하지만 컨텍스트를 많이 씀 — 예시로 17,700 토큰 vs Minion 659 토큰) / Minion(자체 제작, 코딩 전용, 가볍고 빠름).
- API 대안: OpenRouter, Together AI(직접 사용 시 체감 속도가 낫다고 평가)로 GLM-5.2를 저렴하게 이용 가능(Opus 대비 약 1/5 가격 예시).

## 만드는 과정 — 순서대로 (what he tried first, next, ... in chronological order; the actual workflow)
1. 이전 영상 반응(주로 "너무 비싼 컴퓨터가 필요하다"는 오해) 확인 후 반박 목적의 후속 영상 제작.
2. 새 파워서플라이로 케이블 정리.
3. GLM-5.2를 3bit → 2bit로 낮춰가며, KV 캐시 비트수(8bit vs 16bit)를 바꿔 품질 저하 원인을 실험적으로 특정.
4. Terminal-Bench v2.1로 2bit vs 4bit 성능을 정량 비교 중(진행형).
5. 저사양 사용자를 위해 자신이 거쳐온 모델 이력을 소개: Qwen3-Coder → MiniMax M2.7 → MiniMax M3 → GLM-5.2.
6. Hermes와 Minion 두 하네스를 실시간으로 켜서 응답 속도·컨텍스트 사용량을 비교 시연(Hermes가 느리고 컨텍스트를 더 씀을 직접 보여줌).

## 막힌 곳과 해결법 (failures, bugs, surprises, and how he debugged or worked around them)
- GLM-5.2에서 KV 캐시를 8bit로 압축하면 컨텍스트 1K~8K부터 성능이 눈에 띄게 저하되는 문제 발견 → 16bit KV 캐시로 전환해 해결.
- MiniMax 계열의 sparse attention 이슈(이전 영상에서도 언급)는 이번에도 "16bit attention으로 다시 M3를 공정하게 재평가해야 한다"고만 언급, 아직 미해결/보류 상태.
- Hermes 하네스가 첫 응답에서 심하게 느려짐(GPU 클릭 소리까지 언급) → 재시도했지만 근본 원인은 특정하지 못한 채 "컨텍스트가 너무 크다"는 정황 설명만 제시.
- Together AI API가 광고된 처리량(200 tokens/s)보다 느려지는 경우(체감 5 tokens/s까지 저하)에 대해 크레딧 환불을 요구해야 한다고 주장 — 본인의 해결책이라기보다는 업체에 대한 요청 사항.

## 수업 개념과 연결 (any link to KF / PF / PID / SLAM / localization / path planning / control loops / RL)
없음

## Paul의 Hardware Challenge에 주는 교훈 (concrete, 2–5 bullets)
- "3090/4090 한 장 + 필요할 때만 API 호출"이라는 하이브리드 전략은 Hardware Challenge 본체(엣지 보드에서 KF/PF/PID/SLAM 구현)와는 무관하지만, 로봇 프로젝트와 별개로 홈랩에서 로컬 LLM/VLM 실험을 병행하고 싶다면 진입장벽이 생각보다 낮다는 참고 정보.
- Qwen3-30B-A3B류의 "활성 파라미터 3B" MoE 소형 모델(GGUF로 양자화 가능)은 향후 Jetson Orin Nano Super급 보드에서 온보드 VLM/LLM을 시도할 때 "작은 모델도 쓸만하다"는 방향성 참고가 될 수 있음 — 단, 이 영상의 벤치마크는 3090/4090 기준이라 Jetson 성능으로 직접 환산은 불가.
- llama.cpp + GGUF 조합이 "다루기 까다로운 하드웨어에서도 억지로 돌아가게 해준다"는 경험칙은, 엣지 보드에 모델을 억지로 얹어야 하는 상황이 오면 참고할 도구 후보.
- Hardware Challenge 자체와는 직접 관련이 없으므로 시간 배분 우선순위는 낮음.

## 확인 필요 (anything ambiguous in the captions — mark as uncertain rather than guessing)
- "Quen 3635B A3B" 표기가 실제 모델명(예: Qwen3-30B-A3B)과 일치하는지 불확실, 자막 숫자가 뒤섞였을 가능성.
- "MiniMax M2.7"과 "M27" 표기가 영상 내에서 혼용됨 — 동일 모델을 가리키는 것으로 보이나 정확한 버전 넘버링은 불확실.
- "cap percent"라는 용어와 "exploit bench" 벤치마크 축(y축이 무엇을 의미하는지)을 화자 본인도 "I don't even know"라고 인정 — 의미 불확실.
- "wolf from one"이라는 벤치마크/출처 이름이 언급되나 화자도 정확히 기억 못함("I wish I knew") — 실제 명칭 불확실.
- KV 캐시 비트수 관련 수치(1K/8K 컨텍스트 저하 시점)는 화자의 체감 설명이며 정량 데이터로 제시되지 않음.
