# 05 — All Roads Lead back To GLM 5.3!
- 한 줄 요약: 새로 나온 GLM 5.3 Flash(비전 지원)가 fast-fail·빠른 속도 덕에 새로운 최애 로컬 모델이 되었다고 소개하고, 그 비전 능력을 XGO mini 로봇의 물체 인식·제어에 실제로 적용해 보여주는 영상. GPU 한 장이 고장 나 RMA 삽질도 함께 다룸.
- 로봇 관련성: 높음 (GLM 5.3 Flash의 vision으로 XGO mini 로봇을 카메라 기반으로 직접 제어하는 데모가 핵심 내용)

## 하드웨어 (robot, sensors, actuators, compute board, prices if stated)
- RTX Pro 6000 중 한 장(구매한 지 2개월밖에 안 된 "가장 어린" 카드)이 GSP(GPU System Processor) 관련 펌웨어 버그로 에러 상태에 빠지길 반복하다 결국 완전히 사망.
- Nvidia 커뮤니티 포럼에 동일 증상 사례 다수 확인(재부팅으로 일시 복구되다가 결국 안 됨). RMA 경로가 불명확 — Nvidia는 "구매처(vendor)에 문의"라 하고 vendor는 "Nvidia에 문의"라 함, 엔터프라이즈용 RMA 링크에 워크스테이션 카드 시리얼을 넣으면 인식 안 됨.
- 결과적으로 GPU 3장 체제로 운용(TP3), NVFP4 양자화와 결합 시 prefill 속도가 느려지는 부작용 언급.
- XGO mini 로봇: 카메라(전방/측면 웹캠) 장착, 팔(어깨/팔꿈치/그리퍼) 및 바퀴형 이동 구조.

## 소프트웨어 스택 (OS, SDKs, frameworks, models, languages, sim tools)
- GLM 5.3(full) 및 GLM 5.3 Flash(320B, full 모델의 절반 이하 크기) 공개, Flash 버전은 비전(멀티모달) 지원 — Z.ai API로 프리릴리즈 상태 테스트(가중치 공개 전이라 안전성 검수로 실제 값이 바뀌었을 가능성 있어 "참고용"으로만 취급).
- Native precision GLM53 Flash(대부분 FP8 + 비전 타워는 BF16)가 발표자의 새로운 최애 로컬 모델.
- 벤치마크(terminal-bench v2.1) 상 fail까지 걸리는 시간(time-to-fail) 비교: GLM53 Flash 21.9분, DeepSeek V4 Flash 0731 25분, GLM52(3.25bpw) 16분 — fail이 빠를수록 human-in-the-loop 워크플로에서 유리하다는 논지.
- solve까지 걸리는 시간: GLM53 Flash 3.2분, DeepSeek V4 Flash 7.3분.
- 토큰/초: DeepSeek V4 Flash ~350, GLM52(3.25bpw) ~100, GLM53 Flash ~170~180(중간 수준).
- OpenRouter 제공자들이 광고한 정밀도(FP8 등)보다 실제로는 낮은 정밀도로 서빙할 수 있다는 의심을 재차 제기(직접 검증은 못 함).
- Vision 활용: bounding box를 XYXY 좌표 + confidence + label의 구조화된 JSON으로 출력받아 물체 인식(HSV 마스킹 같은 고전 CV 대체).
- 외부 벤치마크(Skalski/Roboflow로 추정, 자막 "Skolski")가 GLM53 Flash의 물체 인식이 나쁘다고 주장한 트윗에 대해, 발표자가 직접 같은 이미지(바나나 농장 사진 등)로 재현해보고 반박 — 프롬프트 구체성과 모델의 자기 반복 보정(자신이 낸 bounding box 결과를 다시 자신에게 보여주고 스스로 교정하게 하는 방식)이 품질을 크게 좌우한다고 주장.
- 대안 파이프라인 비교: DeepSeek V4 Flash(로직) + Qwen(자막 "Quen 3827B", 비전)을 분리해서 쓰는 방식도 작동하지만 모델 간 호출 오버헤드로 지연이 더 큼. 반면 GLM53 Flash처럼 비전+지능이 한 모델에 통합돼 있으면 더 빠르고 매끄러움.
- 비교 대상으로 GPT-5.6 Soul(API, 자막 "GBD56 소울")도 같은 로봇 픽업 태스크에 시켜봤는데, 반응이 4~5분(때로는 20분)씩 걸리고 위치를 overshoot/undershoot 하며 반복 보정하는 등 훨씬 느리고 부자연스러웠다고 설명.

## 만드는 과정 — 순서대로 (what he tried first, next, ... in chronological order; the actual workflow)
1. GLM 5.3 / 5.3 Flash 공개 소식을 API로 우선 테스트, terminal-bench 점수 확인(잠정치로 취급).
2. time-to-fail / time-to-solve 지표를 여러 모델 간 비교하며 "빠른 실패"가 human-in-the-loop에 유리하다는 논지 전개.
3. 영상 중간 RTX Pro 6000 한 장이 죽은 사건과 RMA 시도 과정을 별도로 다룸.
4. 화제를 비전으로 전환 — GLM53 Flash의 object detection 성능에 대한 외부 비판(Skalski/Roboflow 트윗)을 직접 재현 테스트로 검증.
5. XGO mini 로봇에 카메라를 연결해 GLM53 Flash가 직접 SDK를 통해 전진/회전/팔 관절/그리퍼를 제어하는 데모를 실행 — 별도 학습(VLA/ACT) 없이 프롬프트만으로 작동.
6. 같은 태스크를 DeepSeek V4 Flash+Qwen 조합, GPT-5.6 Soul API와 비교해 속도/체감을 대조.
7. 다음 영상에서 "LLM으로 로봇을 제어하는 개념"을 더 깊이 다루겠다고 예고(→ 배치의 02번 영상으로 이어짐).

## 막힌 곳과 해결법 (failures, bugs, surprises, and how he debugged or worked around them)
- GPU GSP 에러 → 재부팅으로 임시 복구되다 결국 카드 완전 사망. RMA 경로 자체가 불명확해 워크스테이션 카드의 공식 지원 프로세스가 사실상 없다시피 함 — 완전히 해결하지 못한 채 "RMA 기다리는 중"으로 영상 마무리.
- 외부 비전 벤치마크와 자신의 체감이 달랐던 이유를 정밀도(quant) 차이로 추정 — Skalski 쪽이 OpenRouter를 사용했을 가능성이 있고, 앞서 여러 영상에서 지적한 "제공자가 광고 정밀도보다 낮게 서빙할 수 있다"는 문제와 연결지어 설명(확정적 검증은 아님).

## 수업 개념과 연결 (any link to KF / PF / PID / SLAM / localization / path planning / control loops / RL; write "없음" if none — do not invent links)
- 없음. 다만 "카메라를 보고 스스로 행동을 교정하는 루프"는 넓은 의미의 폐루프(closed-loop) 피드백과 개념적으로 유사하지만, Kalman/Particle Filter나 PID 같은 구체적 기법과는 무관함.

## Paul의 Hardware Challenge에 주는 교훈 (concrete, 2–5 bullets)
- Vision-LLM으로 카메라 기반 물체 인식을 대체하는 방식은 흥미롭지만, GLM53 Flash(320B)급 모델은 Jetson Orin Nano Super로는 절대 못 돌림 — Hardware Challenge에서 vision을 쓰려면 별도의 경량 CV(예: OpenCV 색상/윤곽 검출)나 아주 작은(1~4B) 로컬 VLM 정도가 현실적 상한선.
- GPT-5.6 Soul(클라우드 API) 같은 대형 모델은 응답이 4~5분(때로는 20분)까지 걸려 실시간 로봇 제어에는 전혀 맞지 않는다는 사례는, Paul의 로봇 제어 루프(PID/KF/PF 등)에는 절대 클라우드 LLM 호출을 끼워 넣으면 안 된다는 경고로 유효 — LLM을 쓰더라도 상위 레벨 목표 설정에만 국한해야 함.
- "빠른 실패(fast-fail)가 human-in-the-loop에 유리하다"는 관점은, Hardware Challenge 실험 때도 알고리즘이 잘못된 방향으로 갈 경우 최대한 빨리 감지하고 사람이 개입할 수 있는 구조(예: 짧은 주기의 디버그 출력, 타임아웃)를 설계하면 디버깅 시간을 아낄 수 있다는 일반 원칙으로 참고 가능.
- GPU 고장/RMA 삽질 에피소드는 "고가 하드웨어도 예고 없이 고장난다"는 점을 보여줌 — Paul의 저가 하드웨어(Freenove/XGO-mini2 + Jetson)에서도 부품 여분(케이블, 센서 등)을 미리 확보해두는 것이 안전.

## 확인 필요 (anything ambiguous in the captions — mark as uncertain rather than guessing)
- 외부 비전 벤치마크 저자 이름이 자막에 "Skolski"로 들리나 실제로는 다른 철자(예: Skalski)일 가능성이 높음 — 불확실.
- "GBD56 소울"은 문맥상 GPT-5.6 Soul로 추정되나 정확한 정식 명칭 표기는 불확실.
- 비전 모델 조합에서 언급된 "Quen 3827B"는 Qwen 계열의 특정 버전(3.8B 혹은 27B 등)으로 추정되나 정확한 모델명/파라미터 수는 자막만으로 확정하기 어려움.
- GLM53 Flash의 "320억"이 아니라 "3200억(320B)" 파라미터라는 점은 자막에서 "320 billion"으로 명확히 언급되었으나, 전체 GLM53(full) 모델과의 정확한 파라미터 비율은 "절반 이하"라는 정성적 언급뿐이라 정확한 수치는 불확실.
