# 04 — Effective Doomerism

- 한 줄 요약: Anthropic 연구원 Jacob Cox의 사직 트윗("AI가 2020년대 안에 인류를 멸종시킬 수 있다")을 계기로, sentdex가 이 서사의 배후에 있는 "실효적 이타주의(Effective Altruism, EA)" 이념과 그 정치적 로비(오픈웨이트 규제 시도)를 비판하는 AI 뉴스/의견 영상. 말미에 DeepSeek V4.1 신규 오픈모델 출시 소식을 짧게 언급.
- 로봇 관련성: 낮음 (로봇 관련 내용 전혀 없음, AI 정책/철학 논쟁 위주)

## 하드웨어 (robot, sensors, actuators, compute board, prices if stated)
해당 없음 (RTX Pro 6000 3장을 보유 중이며 4번째 카드 구매를 기다리고 있다는 배경 언급만 있고 구체 스펙 설명은 없음)

## 소프트웨어 스택 (OS, SDKs, frameworks, models, languages, sim tools)
- DeepSeek V4.1 — MoE 아키텍처, 총 파라미터 약 552B, 활성 파라미터 수치는 화자 본인도 읽으며 헷갈려함(불확실, 아래 "확인 필요" 참고), 비전(vision) 기능 지원 확인. 아직 로컬 구동은 못 해봤고(4번째 GPU 대기 중) 다음 영상에서 다룰 예정이라고 예고.
- 기존에 써본 DeepSeek V4 Flash(및 Vision Experimental 버전)는 벤치마크는 좋지만 실전 코딩 작업에서는 GLM-5.2/5.3 대비 만족도가 낮다고 평가("벤치마크만 잘 본다"는 취지).

## 만드는 과정 — 순서대로 (what he tried first, next, ... in chronological order; the actual workflow)
이 영상은 제작/개발 과정이 아니라 뉴스 반응 영상이라 "만드는 과정"은 해당 없음에 가까움. 진행 순서만 정리:
1. Jacob Cox의 사직 트윗을 문장 단위로 읽으며 반박.
2. 해당 글이 자연 발생적 바이럴이 아니라 마케팅/홍보 목적으로 코칭된 글일 가능성 제기(트위터 알고리즘 부스팅 패턴 근거).
3. Effective Altruism 개념 설명(공리주의, "최대다수의 최대행복"), flock 카메라·예측 치안 등 사례로 EA적 사고방식 설명.
4. 이전 영상(07번)에서 다룬 Hugging Face 해킹 사건을 재소환, 이 사건의 벤치마크 운영사 "Irregular"와 사후분석 기관 "Meter"가 모두 EA 연계라고 주장.
5. Anderson Cooper와의 인터뷰 클립 재생 — Jacob이 "AI가 핵심 인프라 해킹, 생물무기 제조 등으로 인류를 멸종시킬 수 있다"고 주장하나 구체적 메커니즘 질문에는 답을 회피한다고 지적.
6. 정부 규제 요구로 귀결되는 서사에 회의적 입장을 표명하며 DeepSeek V4.1 소식으로 화제 전환, 영상 마무리.

## 막힌 곳과 해결법 (failures, bugs, surprises, and how he debugged or worked around them)
해당 없음 (기술적 문제/디버깅 없음, 순수 논평 영상)

## 수업 개념과 연결 (any link to KF / PF / PID / SLAM / localization / path planning / control loops / RL)
없음

## Paul의 Hardware Challenge에 주는 교훈 (concrete, 2–5 bullets)
- 이 영상은 Hardware Challenge와 관련된 실질적 시사점이 없음. AI 산업 내 정책/철학 논쟁이 주제.
- 유일하게 참고할 점: DeepSeek V4.1이 비전(vision) 기능을 갖춘 오픈 MoE 모델로 곧 나온다는 소식 — 향후 오픈소스 VLM 후보를 검토할 때 이름 정도는 기억해둘 만함. 다만 파라미터 규모가 매우 커서(552B 총 파라미터) Jetson급 엣지 배포와는 거리가 멀고, 경량화 버전 존재 여부는 이 영상에서 확인되지 않음.

## 확인 필요 (anything ambiguous in the captions — mark as uncertain rather than guessing)
- DeepSeek V4.1의 활성 파라미터 수치("8 billion active input, 16 billion for...")는 화자 본인도 읽으며 헷갈려함("what does that even mean I don't understand") — 정확한 아키텍처 스펙 불확실.
- "Irregular"(벤치마크 운영사), "Meter"(사후분석 기관)가 실제 그런 이름과 EA 연계 역할을 가진 조직인지는 화자의 주장일 뿐, 1차 출처로 확인되지 않음.
- Jacob Cox의 실제 경력(OpenAI/Anthropic 재직 기간 등)은 화자가 "확실친 않다"고 스스로 인정하며 설명한 내용.
