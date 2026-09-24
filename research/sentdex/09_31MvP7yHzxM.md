# 09 — In search of frontier AI at home
- 한 줄 요약: sentdex가 자신의 4-GPU 워크스테이션에서 GLM 5.2의 여러 quant와 DeepSeek V4 Flash를 terminal-bench v2.1로 직접 벤치마크하고, 의외로 가장 작은 모델인 DeepSeek V4 Flash가 로컬에서 최고 성능을 낸다는 결론에 도달하는 영상.
- 로봇 관련성: 낮음 (로봇은 전혀 등장하지 않음. 다만 "작은 로컬 모델도 충분히 쓸만하다"는 결론은 하드웨어/모델 선택에 참고할 배경 지식)

## 하드웨어 (robot, sensors, actuators, compute board, prices if stated)
- 데스크톱 워크스테이션(Puget 빌드)에 RTX Pro 6000 4장 장착. 대당 약 $11,700 (가격이 계속 오르는 중이라고 언급).
- 2장만으로도 API 없이 돌릴 수 있다고 주장, 4장은 필수 아님.
- 라이저(riser) 케이블 때문에 PCIe3.0으로 다운그레이드해서 운용 중 (본래 PCIe4 카드인데 신호 무결성 문제로 속도 손해).
- 모델별 VRAM: GLM 5.2는 native 16bit 기준 매우 크고(클라우드용 784GB급), DeepSeek V4 Flash는 160GB로 훨씬 작아 로컬에서 돌리기 적합.
- KV cache를 16bit vs 8bit(FP8/Q8로 추정)로 비교 — 8bit KV cache가 성능을 크게 깎아먹음(52%→24%).

## 소프트웨어 스택 (OS, SDKs, frameworks, models, languages, sim tools)
- 서빙: VLM(=vLLM으로 추정)을 사용, tensor parallelism(TP)으로 concurrency 8까지 운용.
- 벤치마크: terminal-bench v2.1 (89개 task, long-horizon agentic coding/터미널 벤치마크).
- 자신이 만든 매우 단순한 코딩 하니스 "Minion" 사용.
- 비교 모델: GLM 5.2 (4bit/2bit, NVFP4 REAP 변형 포함), DeepSeek V4 Flash(160GB, native에 가까운 정밀도, MTP 기반 speculative decoding 사용), MiniMax M3(자막상 "Miniax M3"), Tencent Hi3(295B, native mixed precision 아님 → quant 필요), Nemotron 3 Ultra(NVFP4 네이티브 여부 불확실).
- 토큰/초: DeepSeek V4 Flash가 낮게는 150~200, 높게는 800~1200 tok/s (concurrency 8 기준, 코드 생성이 일반 텍스트보다 빠름).

## 만드는 과정 — 순서대로 (what he tried first, next, ... in chronological order; the actual workflow)
1. GLM 5.2를 다양한 quant(4bit/2bit, 8bit/16bit KV cache)로 terminal-bench v2.1 벤치마크.
2. 결과를 보다가 "이 리스트 중 quant 없이 native precision으로 돌릴 수 있는 모델이 있을까?" 라는 질문에서 DeepSeek V4 Flash를 벤치마크에 추가.
3. DeepSeek V4 Flash가 56%로 GLM52 4bit(52%)를 능가하는 것을 확인 → 이후 며칠~일주일 이상 DeepSeek V4 Flash를 메인 모델로 실사용.
4. NVFP4 GLM52 REAP(가지치기/lobotomized) 변형도 하룻밤 벤치마크 시도했으나 완주하지 못함(REAP는 성능 저하 우려로 회의적).
5. 벤치마크 결과를 카테고리별(Git, Python, build/compile 등)로 분해해서 quant 강도에 따라 어떤 능력이 먼저 무너지는지 분석.
6. concurrency별 tok/s 집계를 llama.cpp(pipeline parallelism)와 vLLM(tensor parallelism)으로 비교.

## 막힌 곳과 해결법 (failures, bugs, surprises, and how he debugged or worked around them)
- 8bit KV cache가 GLM52 점수를 52%→24%로 크게 깎음 — 원인 추정만 하고 명확한 해결책은 제시하지 않음(그냥 16bit KV cache 권장).
- vLLM에서 concurrency=2일 때만 유독 처리량 이득이 없는 버그성 현상 발견 (원인 불명, 시청자에게 질문 던짐).
- terminal-bench 점수가 "human-out-of-the-loop" 가정이라 사람이 개입하면 쉽게 통과했을 task도 timeout으로 실패 처리됨 — 벤치마크 신뢰도에 대한 회의적 시각.
- 공식 벤치마크 점수보다 자신의 로컬 측정치가 대체로 낮게 나옴 — 태스크별로 직접 확인했지만 원인은 명확히 규명하지 못함.

## 수업 개념과 연결 (any link to KF / PF / PID / SLAM / localization / path planning / control loops / RL; write "없음" if none — do not invent links)
- 없음.

## Paul의 Hardware Challenge에 주는 교훈 (concrete, 2–5 bullets)
- 이 영상의 하드웨어(RTX Pro 6000 x4)는 Paul의 챌린지와 규모가 전혀 다름 — 참고할 것은 "작은 모델도 충분하다"는 결론뿐. Jetson Orin Nano Super에서는 애초에 이런 거대 모델은 후보가 아니고, 수 B급 경량 모델만 검토 대상.
- KV cache quantization이 정확도에 생각보다 큰 타격을 준다는 사실은, Jetson처럼 메모리가 극히 제한적인 보드에서 모델을 양자화할 때 "가볍게 8bit로 낮추면 되겠지"라고 가정하면 안 된다는 경고로 참고할 만함.
- tokens/sec, time-to-first-token 같은 지표가 실사용 체감에 큰 영향을 준다는 강조는, 로봇 제어 루프(특히 PID처럼 실시간성이 중요한 부분)에 LLM을 절대 넣지 말고, 클래식 알고리즘으로 제어 루프 자체는 구현해야 한다는 방향성을 재확인해줌.
- Hardware Challenge는 "로컬에서 개인 프로젝트에 쓸만한 실용적 하드웨어"를 요구하므로, 이 영상 수준의 인프라(멀티 GPU, 수천 달러대 카드)는 스코프 밖 — Freenove/XGO-mini2 + Jetson Orin Nano Super 조합이 훨씬 합리적이라는 점을 재확인.

## 확인 필요 (anything ambiguous in the captions — mark as uncertain rather than guessing)
- RTX Pro 6000 가격 "$11,700"은 자막 그대로 인용했으나 변동성이 크다고 본인도 언급 — 시점에 따라 다를 수 있음(불확실).
- "MiniMax M3"(자막상 "Miniax M3")와 "MiniMax M2.7"의 정확한 명칭/버전 표기가 자막에서 혼용되어 불확실.
- NVFP4, FP8, Q8 등 양자화 포맷 간의 정확한 대응관계는 발표자 본인도 "이 부분은 오기(misnomer)일 수 있다"고 말해 불확실.
- concurrency=2에서 처리량이 늘지 않는 현상의 원인(MTP=2 관련 추정)은 발표자도 확신하지 못함 — 원인 불명으로 처리.
