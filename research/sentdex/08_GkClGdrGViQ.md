# 08 — You Can Just Download More Tokens/Sec
- 한 줄 요약: DeepSeek V4 Flash + "DSpark"(개선된 speculative decoding)로 300+ tok/s를 실시간 시연하며, "속도도 지능만큼 중요하다"는 주장과 함께 대형 프론티어 모델(Fable/Opus급, GPT-5.6 Soul, Kimi K3)이 실사용에는 과하다는 논지를 전개하는 영상. 하드웨어 업그레이드(PCIe 스위치 준비, UPS, 낙뢰 대비)도 소개.
- 로봇 관련성: 낮음 (로봇은 전혀 등장하지 않음. LLM/하드웨어 인프라와 모델 트렌드 위주의 "AI 뉴스+인프라" 성격 영상)

## 하드웨어 (robot, sensors, actuators, compute board, prices if stated)
- 기존 Puget 워크스테이션(4.5년 된 구형): PCIe4 슬롯 7개(x16/x8/x4 혼재), ECC DDR4 RAM 1TB(구형이지만 대용량).
- 이번 영상 시점엔 RTX Pro 6000 2장만 x16 PCIe4에 직결해서 운용(4장 중 2장, TP2). DeepSeek는 어텐션 헤드 수 제약으로 TP3 불가 — TP는 2,4 배수 단위로만 가능(MiniMax M2.7은 48 attention head라 TP3 가능한 예외).
- 리서(riser) 케이블은 신호 무결성 문제로 "쓰지 말라"고 강하게 경고 — PCIe 스위치(SlimSAS/MCIO 기반) 도입 준비 중.
- UPS를 "double online conversion" 방식의 고급형(4.5~5kW)으로 교체 — 낙뢰가 잦은 지역이라 전작 UPS/네트워크 스위치가 여러 번 고장난 경험. 태양광 PV 배선과 지하 매설 이더넷 케이블에도 SPD(surge protection device) 설치.
- 중고/리퍼 UPS 판매처 "Greenlight UPS" 이용(배터리 교체 포함, 정가 대비 절반 가격).

## 소프트웨어 스택 (OS, SDKs, frameworks, models, languages, sim tools)
- 서빙: vLLM(자막상 VLM)으로 DeepSeek V4 Flash + DSpark(스펙큘레이티브 디코딩 모듈, DeepSeek 자체 추가 모듈) 구동, TP2에서 300+ tok/s, TP4면 이론상 ~400 tok/s.
- Speculative decoding의 발전 과정 설명: 별도 draft model 방식(수십% 속도 향상) → 모델 내장 MTP(Multi-Token Prediction) 레이어 → DeepSeek의 DSpark(추가 spec 모듈, MTP 위에 50% 추가 속도 향상).
- 코딩 에이전트 "Minion"으로 레포 전체를 컨텍스트에 읽어들여 prefill 속도 시연(90K 토큰 컨텍스트).
- prefill 속도 비교: GLM 5.2 로컬 ~1000~1100 tok/s (90K 토큰 채우는 데 약 80초 소요) vs DeepSeek V4 Flash ~100,000 tok/s (1초 미만).
- 언급된 신규/경쟁 모델: Kimi K3(2.8조 파라미터, 4bit로도 1.4TB라 로컬 불가능하다고 판단), Qwen 계열 대형 모델(2.4조 파라미터, 자막상 "Quen 38" — 정확한 버전명 불확실, 4bit면 1.2TB+200GB 컨텍스트로 이론상 실행 가능하다고 추정), Thinking Machines(전 OpenAI 인물 창업)의 오픈웨이트 모델(자막상 "Inkling" — 1조 파라미터 대형판은 별로였고, 276B "small"판은 DeepSeek V4 Flash와 비슷한 성능), Grok 4.5 및 동반 CLI "Grok Build"(레포 전체와 git 히스토리를 xAI 클라우드로 업로드한 프라이버시 논란 사례로 언급).
- 오픈소스 CLI "Minion"을 프라이버시 대안으로 소개(추적 없음 주장).

## 만드는 과정 — 순서대로 (what he tried first, next, ... in chronological order; the actual workflow)
1. 이전 영상 이후 2주 새 GPT-5.6 Soul, Kimi K3, Qwen 신모델 발표 등 급변한 모델 지형을 언급하며 시작.
2. DeepSeek V4 Flash + DSpark의 속도를 실시간 코드 생성으로 시연(302~322 tok/s).
3. Minion에게 저장소 전체를 읽게 해서 컨텍스트를 90K 토큰까지 채운 뒤, "이 레포를 1~10점으로 평가해봐" 같은 질문을 던져 prefill 속도 차이(GLM52 대비 DeepSeek V4 Flash가 압도적으로 빠름)를 시연.
4. 오픈라우터(OpenRouter)에서 제공되는 DeepSeek V4 Flash+DSpark FP8 API 점수가 GLM52보다 높게 나오는 것을 보고, 해당 제공자가 실제로는 FP4로 서빙하면서 FP8이라 광고하는 것 아니냐는 의심을 제기(확정은 아님).
5. 업데이트된 하드웨어(PCIe 스위치, UPS, SPD) 소개로 전환.
6. 최근 공개된 모델들(Kimi K3, Qwen 대형모델, Thinking Machines 오픈웨이트, Grok 4.5)을 하나씩 훑으며 자신의 하드웨어로 돌릴 수 있는지 가늠.
7. 마지막에 "왜 다들 Fable/GPT-5.6 Soul 같은 초대형 모델이 필요하다고 착각하는가"에 대한 개인적 주장을 길게 전개(모델이 느려서 사람이 집중을 못 하고 결국 "완전히 맡기는" 워크플로를 원하게 된다는 논지).

## 막힌 곳과 해결법 (failures, bugs, surprises, and how he debugged or worked around them)
- 오픈라우터 제공자가 광고한 정밀도(FP8)와 실제 서빙 정밀도가 다를 수 있다는 의심 — 본인도 "누구인지 특정하지 않겠다"며 명확한 검증 방법은 제시하지 못함(추정 수준).
- Kimi K3(2.8조 파라미터)는 1TB RAM + 약 300GB VRAM을 갖고도 4bit 기준 1.4TB가 필요해 도저히 로컬 실행 불가 판정 — 여러 대의 구형 GPU(RTX 8000 등)를 총동원해도 3~4 tok/s 수준일 것으로 추정, 포기.
- Grok Build CLI가 전체 레포+git 히스토리를 클라우드로 업로드한 사건을 계기로, 사실 모든 클라우드 LLM API 사용이 근본적으로 코드/IP를 유출하는 것과 다르지 않다는 프라이버시 논지로 확장.

## 수업 개념과 연결 (any link to KF / PF / PID / SLAM / localization / path planning / control loops / RL; write "없음" if none — do not invent links)
- 없음.

## Paul의 Hardware Challenge에 주는 교훈 (concrete, 2–5 bullets)
- "긴 컨텍스트일수록 prefill 지연이 커진다"는 포인트는, Jetson Orin Nano Super처럼 연산력이 제한된 보드에서 LLM/VLM을 돌릴 때 프롬프트/컨텍스트를 최대한 짧게 유지해야 응답 지연을 줄일 수 있다는 시사점으로 연결됨 — 로봇 제어 루프에 LLM을 얹는다면 특히 중요.
- "속도(latency)가 지능보다 실사용성에 더 중요할 수 있다"는 핵심 주장은, Hardware Challenge에서 굳이 "가장 똑똑한" 모델을 Jetson에 무리해서 올리기보다, 훨씬 작고 빠른 모델(또는 아예 고전적 알고리즘)로 실시간성을 확보하는 쪽이 낫다는 방향을 뒷받침.
- 이 영상의 하드웨어 스케일(PCIe 스위치, 1TB RAM, 수천 달러대 UPS)은 Paul의 챌린지와 무관 — 다만 "GLM52/DeepSeek V4 Flash급 모델은 애초에 소형 보드의 후보가 아니다"라는 점을 재확인시켜줌. Jetson에는 1~4B급 매우 작은 모델만 현실적 후보.
- 클라우드 LLM API를 통한 프라이버시/IP 유출 논지는 학교 과제 맥락에선 직접적 리스크는 낮지만, 로봇에 어떤 형태로든 LLM을 연동한다면 로컬 추론이 비용/지연/프라이버시 모두에서 유리하다는 일반 원칙은 유효.

## 확인 필요 (anything ambiguous in the captions — mark as uncertain rather than guessing)
- "Quen 38"로 들리는 모델명이 정확히 어떤 Qwen 버전(예: Qwen3.8 혹은 다른 표기)인지 불확실 — 2.4조 파라미터라는 수치만 확실히 언급됨.
- Thinking Machines의 오픈웨이트 모델명이 자막상 "Inkling"으로 표기되나, 실제 정식 모델명과 다를 가능성이 높음(자동 자막 오류로 추정) — 불확실.
- "GBD56 소울"은 문맥상 GPT-5.6 Soul로 추정되나 정식 명칭 표기는 불확실.
- "DSpark"의 정확한 공식 명칭과 기술적 구현 디테일(레이어 수 등)은 발표자도 "정확히 모른다"고 밝힘 — 불확실.
