# 01 — Jev, Yang & RSI

- 한 줄 요약: 로봇 실습이 아니라 AI 업계 뉴스/의견 모음 영상. RSI(recursive self-improvement) 논쟁, "Jev"라는 신생 구조화 출력(structured output) 엔진에 대한 회의적 리뷰, Andrew Yang의 "탈출한 봇이 인터넷을 오염시켰다"는 주장 비판, OpenAI/Anthropic 안전성 관련 논란을 다룸.
- 로봇 관련성: 낮음 (AI 뉴스 위주 영상이며 로봇 관련 내용은 후반부 한두 문단뿐)

## 하드웨어 (robot, sensors, actuators, compute board, prices if stated)
없음. 로봇 하드웨어는 전혀 언급되지 않음. 로컬 LLM 추론용 워크스테이션의 GPU 4개(RMA로 4번째 GPU 복구) 언급만 있음 — 로봇용이 아니라 벤치마크/모델 비교용.

## 소프트웨어 스택 (OS, SDKs, frameworks, models, languages, sim tools)
- GLM 5.3 Flash, DeepSeek V4.1 Flash 등 로컬 LLM을 턴제 전략 게임(Hollight 등, 약 20개 게임 리스트 보유, StarCraft 2 포함)에서 맞대결시켜 지능을 비교하는 실험을 예고편 형식으로 짧게 보여줌 — 로봇에는 적용되지 않음, "Terminal Bench" 대신 시도할 새 벤치마크 아이디어로 소개.
- NVFP4를 선호 quantization 포맷으로 채택한다고 언급.
- "Jev"(자막 표기, Dio Almeida가 만들었다고 언급되는 신생 엔진/모델)를 구조화 출력(structured JSON) 특화, "auto-regressive가 아니라 병렬 출력"이라는 주장과 함께 소개하고 회의적으로 평가.

## 만드는 과정 — 순서대로
해당 없음. 실습/구현 영상이 아니라 뉴스 논평 영상이라 "만드는 과정"이 존재하지 않음.

## 막힌 곳과 해결법
해당 없음.

## 수업 개념과 연결
없음. KF/PF/PID/SLAM/localization/path planning/control loop/RL 관련 언급 전혀 없음.

## Paul의 Hardware Challenge에 주는 교훈
- 영상 후반, Jev를 로보틱스에 적용하는 아이디어를 비판하며 "로보틱스에서 진짜 어려운 부분은 속도가 아니라 vision(시각 인식)이다"라는 발언이 나옴. Sim-to-real 문제가 결국 vision에서 가장 크게 발생한다는 주장으로, 이는 03번 영상(XGO-mini2)의 실전 경험(HSV mask→VLM fallback, 카메라 위치 설계 고민)과 일치함. Hardware Challenge에서 센서 파이프라인(카메라 등)에 가장 공을 들일 근거가 됨.
- 그 외에는 Paul의 로봇 설계 결정에 직접 참고할 내용이 거의 없음.

## 확인 필요
- "Jev"라는 이름과 개발자("Dio Almeida")가 실제 존재하는 프로젝트/인물인지, 정확한 철자는 자막 기반 추정이라 불확실.
- 비교 대상 모델명 "GBD6 Astra"/"Astra"가 정확한 실제 모델명인지 불확실 (자동 캡션 오타 가능성).
- "GLM 5.3 Flash", "DeepSeek V4.1 Flash" 등의 정확한 정식 명칭도 자막 반복 오타 가능성이 있어 확정하지 않음.
