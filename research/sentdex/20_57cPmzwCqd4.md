# 20 — Vibe Coding a Robotic Hand to Crawl (Inspire RH56DFQ)

- 한 줄 요약: 21번 영상(RH56DFQ 손 초기 통신 성공) 바로 다음 편. Cursor+Claude로 rock-paper-scissors gesture를 완성하고, 손가락 굽힘 순서만으로 손 전체가 책상 위를 약 2.5피트(76cm) "기어가게" 만드는 동작을 원샷으로 성공시킴.
- 로봇 관련성: 높음

## 하드웨어 (robot, sensors, actuators, compute board, prices if stated)
- 동일 Inspire RH56 로봇 손 (오른손, right hand 명시). 21번 영상에서 확인된 물리적 제약(굽힘은 강함, 펴는 힘은 고무줄 수준으로 약함)이 이번 영상 crawling 알고리즘 설계의 핵심 전제로 재사용됨.
- Thumb는 양방향 회전이 가능하고, 이 회전력으로 손 전체를 들어올려 다른 finger를 재배치(reposition)하는 데 사용됨 — crawling 동작의 핵심 메커니즘.
- 특정 가격/추가 하드웨어 언급 없음.

## 소프트웨어 스택 (OS, SDKs, frameworks, models, languages, sim tools)
- Cursor agent + Claude (auto-accept/"YOLO" 모드는 신뢰하지 않아 쓰지 않음), Python 3.10 (버전 문제 재발).
- 이전 영상에서 만든 interactive CLI/모듈을 그대로 재사용. 코드는 "100% AI가 작성", 사람이 손댄 부분은 파일 맨 위 메모 정도뿐이라고 강조.
- 완성된 코드를 GitHub에 공개 (레포 공개 시점 기준 "6명이 star"했다고 언급).

## 만드는 과정 — 순서대로
1. 이전 영상 결과물(CLI/interactive script) 재사용 — README부터 읽게 하고 interactive mode로 연결 확인.
2. Python 버전 문제(3 vs 3.10) 재발 → 재지정하여 해결.
3. "rock, paper, scissors" 세 gesture 생성 요청. 핵심 제약을 사람이 직접 지정: 닫을 때 엄지를 마지막에 넣고, 열 때는 엄지를 먼저 뺄 것.
4. 세 gesture를 한 번에 코드로 구현, 실제 손에서 테스트 → 거의 다 의도대로 나옴 (paper는 살짝 다르게 나왔지만 수용).
5. CLI가 간헐적으로 "hand not connected"라고 잘못 보고하는 버그 발견 (재현/원인 불명).
6. 새로운 과제 "crawling"을 매우 길게(음성 인식으로 받아쓴 긴 문단) 텍스트로 설명: 손바닥이 바닥을 향한 채, 손가락을 안으로 굽히는 힘은 강하지만 밖으로 펴는 힘은 약하다는 물리적 제약을 알려주고, 엄지 회전으로 손을 들어 손가락을 재배치하라는 힌트를 줌.
7. LLM이 이해한 내용을 요약("finger closing으로 당기고, 무게를 들어 다음 스텝 준비")하고 crawl 스크립트를 생성.
8. 첫 단독 스텝(single step) 실행 → 눈에 보이는 전진 발생, 사람이 놀람.
9. 여러 스텝을 연속 실행(steps 파라미터, 최대 8 steps까지 시도) → 책상 위에서 약 2.5피트(76cm) 전진 성공. "원샷(zero-shot)으로 크롤링 손을 만들었다"고 평가.

## 막힌 곳과 해결법
- Python 3 vs 3.10 혼동 재발 → 재지정으로 해결.
- Interactive CLI가 간헐적으로 "hand not connected"라고 잘못 보고 → 재실행하면 해결되지만 근본 원인 불명. 일부 스크립트가 공용 모듈을 직접 쓰지 않고 우회했을 가능성만 추정.
- Crawling 요구사항이 복잡해서 한 번에 길게(구두로 받아쓴 긴 텍스트) 설명해야 했음 — 복잡한 물리적 제약은 짧게 나눠 말하기보다 한 번에 자세히 명세하는 편이 LLM 계획 수립에 효과적이었다고 언급.

## 수업 개념과 연결
없음. KF/PF/PID/SLAM 등 직접 언급 전혀 없음. 다만 "약한 힘(고무줄) vs 강한 힘(모터)"이라는 비대칭 제약 아래 다단계 동작 시퀀스를 설계한 것은 개념적으로 PID 같은 연속 제어보다는 규칙 기반 순서 제어(rule-based sequencing)에 가깝다.

## Paul의 Hardware Challenge에 주는 교훈
- 액추에이터의 힘의 방향/비대칭성(굽힘 강함, 펴짐 약함) 같은 물리적 제약을 사람이 명확히 언어로 설명해주면, LLM이 그 제약 아래에서 새로운 동작 시퀀스(crawling)를 스스로 설계할 수 있음 — Hardware Challenge에서도 실제 로봇의 기계적 한계를 먼저 정확히 파악·문서화해두는 게 중요.
- 트레이닝 데이터에 딱히 없을 법한 새로운 태스크도 LLM이 유사한 지식(사람이 기어가는 방식 등)을 유추해 그럴듯한 해를 한 번에 낼 수 있음 — 단, 반복 검증이 필요하고 항상 되는 건 아님.
- YOLO/auto-accept 모드는 편하지만 간헐적 버그(연결 실패 등)를 놓치기 쉬움 → 실습 중엔 단계별 직접 확인이 안전.
- AI가 작성한 코드도 처음부터 git/GitHub로 버전 관리하는 습관이 실전에서 중요하다고 강조 — Paul도 Hardware Challenge 코드는 초기부터 커밋 단위로 관리할 것.

## 확인 필요
- crawling 스텝당 실제 이동 거리는 불명확 (합계 "2.5피트, 최대 8 steps"만 언급, 스텝당 평균 거리는 캡션에 없음).
- finger position 0번이 정확히 엄지 회전(rotation)인지는 21번 영상과 마찬가지로 추정 수준이며 확정되지 않음.
