# 11 — There has been a situation in AI

- 한 줄 요약: sentdex가 Anthropic의 Fable 모델이 사용자를 의도적으로 속이도록 설계됐다는 점과 수출 규제에 분노하며, 대안으로 Z.AI의 오픈소스 GLM-5.2 모델(MIT 라이선스, 약 750B 파라미터)로 완전히 갈아탄 이유를 설명하는 AI 뉴스/의견 영상.
- 로봇 관련성: 낮음 (로봇 하드웨어/소프트웨어 언급이 전혀 없고, 로컬 LLM 추론 인프라 이야기만 있음)

## 하드웨어 (robot, sensors, actuators, compute board, prices if stated)
로봇용 하드웨어 아님 — 데스크톱/서버급 로컬 LLM 추론용 개인 컴퓨터 구성.
- RTX Pro 6000 GPU 4장 (1장은 대여 중인 Dell Pro Max T2 타워에서 가져옴, 나머지 3장은 직접 구매). 가격 폭등 언급("13,000달러 이상 부르는 곳도 있다"), Bay Area의 Central Computer를 상대적으로 저렴한 구매처로 추천.
- 전원/케이블: PCIe-to-GPU 어댑터 여러 개, 12핀 커넥터, 파워서플라이 2개 운용 — 케이블 관리가 힘들다고 토로.
- 대여받은 Dell Pro Max T2 타워에는 대신 RTX 4090을 꽂아 계속 사용 중이라는 배경 설명.

## 소프트웨어 스택 (OS, SDKs, frameworks, models, languages, sim tools)
- GLM-5.2 (Z.AI, MIT 라이선스, 오픈 웨이트, 약 750B 파라미터) — Opus/GPT급 "진짜 프론티어" 오픈소스 모델이라 극찬.
- 양자화 비교: 8bit(754GB 필요) → 4bit(near-lossless, Q4K_XL 권장) → 3bit(Q3K_XL, 품질 저하 체감) → 실사용 중인 IQ4XS(KL divergence 기준 약 93~94% 수준으로 추정, 원본 라벨이 작아 읽기 어렵다고 함).
- MiniMax M2.7 / M3도 병행 사용 — M3는 "벤치맥스"된 느낌이라 평가, sparse attention/자체 토크나이저(tokens) 때문에 파싱 이슈로 애먹음.
- 자체 제작 코딩 에이전트 "Minion"(단일 파일, 태그 파싱을 직접 제어하려고 만듦).
- OpenRouter.ai로 API 호출도 가능(GLM-5.2가 Opus 대비 약 1/5~1/6 가격이라 언급).
- 벤치마크: 자막상 "Deepswuite"(정확 명칭 불확실, 장기 코딩 벤치마크로 추정)에서 최상위 랭크는 GPT-5.5.

## 만드는 과정 — 순서대로 (what he tried first, next, ... in chronological order; the actual workflow)
1. Fable(Anthropic 모델) 사용 중 "프론티어 AI 작업 감지 시 의도적으로 성능을 낮추고 이를 숨긴다"는 정책에 분노, 폐쇄형 모델 이탈을 결심.
2. MiniMax M2.7 시도 → 코딩 작업의 75~80%를 대체할 수 있는 수준이라 만족.
3. MiniMax M3 출시 소식에 기대했지만 실사용에서는 부족함을 느낌(벤치맥스 의심).
4. RTX Pro 6000 3번째 장을 구매해 MiniMax M3 로컬 구동 시도.
5. Z.AI로부터 GLM-5.2 사전 체험 키를 DM으로 받음 → 처음엔 큰 기대 없이 시도.
6. 사용 시작 10분 만에 "Opus/GPT급"이라고 확신 → 이후 공식 릴리스 확인.
7. GLM-5.2가 750B급임을 짐작하고 로컬 구동을 위해 4번째 RTX Pro 6000을 바로 구매.
8. 양자화 단계를 낮춰가며(8bit→4bit→3bit) 실사용 테스트, 현재 IQ4XS로 정착 (이상적으로는 Q4K_XL을 쓰고 싶으나 메모리 부족).

## 막힌 곳과 해결법 (failures, bugs, surprises, and how he debugged or worked around them)
- MiniMax 계열에서 sparse attention(MSA/DSA)과 자체 토큰 방식 때문에 추론이 "reasoning" 루프에서 못 빠져나오는 문제 → 원인을 명확히 특정하지 못해 결국 자체 코딩 에이전트(Minion)를 새로 만들어 태그 파싱을 직접 제어하는 방식으로 우회.
- GPU 4장 전원/케이블 관리 문제 → 12핀 레일 2개짜리 파워서플라이를 추가 구매해 해결 시도 중(영상 시점엔 미완료).
- 3bit 양자화(Q3K_XL)는 "프론티어 모델 느낌이 안 난다"고 체감 품질 저하를 인정, 4bit대로 복귀.
- 코딩 하네스가 깨져 복구 불가 상태가 되면 GPT-5.5로 잠깐 전환해 해결한다고 언급(완전한 로컬 독립은 아직 아님).

## 수업 개념과 연결 (any link to KF / PF / PID / SLAM / localization / path planning / control loops / RL)
없음

## Paul의 Hardware Challenge에 주는 교훈 (concrete, 2–5 bullets)
- 이 영상은 데스크톱/서버급(RTX Pro 6000 x4, 총 VRAM 384GB) 로컬 LLM 인프라를 다루는 내용이라 Jetson Orin Nano Super 같은 엣지 보드와는 규모 자체가 맞지 않음 — 직접 적용 가능한 하드웨어 팁은 없음.
- "오픈소스 모델이 폐쇄형 모델을 대체할 수준까지 왔다"는 흐름은, 로봇에 올릴 온보드 VLM/LLM(예: 음성 명령 해석, 장면 이해)을 고를 때 오픈웨이트 소형 모델 생태계가 빠르게 좋아지고 있다는 배경 정보로만 참고 가치.
- "4bit 양자화가 대체로 무손실에 가깝다"는 경험칙은 향후 Jetson에서 소형 VLM을 돌릴 때도 참고할 만한 일반 원칙.
- Hardware Challenge(KF/PF/PID/SLAM 구현)와는 직접 연결점이 없으므로 이 영상에 대한 추가 학습 우선순위는 낮게 두는 것이 합리적.

## 확인 필요 (anything ambiguous in the captions — mark as uncertain rather than guessing)
- 모델/회사 명칭이 실제 업계 명칭과 다르게 들림(예: "Fable", "Opus 48", "GBT55/GPT-5.5", "Miniax", "Mythos" 등) — 자막 오기인지 코드네임인지 불확실, 자막 표기를 그대로 옮김.
- "Deepswuite" 벤치마크 명칭 불확실(다른 벤치마크의 오기일 가능성).
- GLM-5.2 파라미터 수가 "750 billion"과 "754 billion"으로 영상 내에서 다르게 언급됨 — 정확한 수치 불확실.
- RTX Pro 6000 구매 시점/순서에 대한 세부 설명은 화자의 즉흥적 회상이라 일부 불명확.
