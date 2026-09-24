# 18 — Unitree G1 LiDAR, SLAM, navigation and control (P.2)

- 한 줄 요약: Livox Mid-360 LiDAR와 KISS-ICP를 이용해 ROS 없이 순수 Python 위주로 실시간 SLAM(점군+odometry)과 occupancy grid, 초보적 경로계획(path planning)까지 구현했지만 ROS/catkin은 4시간 삽질 끝에 포기했고 occupancy grid·경로계획은 아직 불안정한 상태.
- 로봇 관련성: 높음 (Paul의 수업과 가장 밀접)

## 하드웨어 (robot, sensors, actuators, compute board, prices if stated)
- LiDAR: Livox Mid-360. 수평 360°, 상하 약 15°(자막상 불확실) 시야각. 로봇 머리 아래쪽에 "거꾸로(upside down)" 장착되어 있음 — 이는 Unitree의 제조 방식이며 sentdex가 임의로 그렇게 단 게 아님(시청자 질문에 직접 해명).
- 헤드 전방 카메라(RGB+뎁스, RealSense로 추정)는 고정된 기본 자세로 아래를 향해 tilt 되어 있음(하드웨어 기본값, 실시간으로 각도 조절 불가). 이유 추정: 설거지·조리대 작업 등 대부분의 작업이 아래를 보는 동작이기 때문.
- 컴퓨팅 구조: G1에는 컴퓨터가 최소 3개 — (1) G1 자체 컨트롤러, (2) Jetson 보드(주로 통신 상대), (3) LiDAR 유닛 자체도 "그 자체로 하나의 컴퓨터"이며 서브넷 상 자신만의 IP를 가짐. 반면 RGB/뎁스 카메라(RealSense)는 별도 IP가 없는 USB 주변장치에 가까움(확실친 않다고 본인도 언급).
- 유선 이더넷을 계속 사용 중 — Wi-Fi로 전환 시도했으나 문제가 있었음(아래 "막힌 곳" 참고).

## 소프트웨어 스택 (OS, SDKs, frameworks, models, languages, sim tools)
- SLAM 엔진: **KISS-ICP**("Keep It Simple, Stupid" 콘셉트의 ICP 기반 point cloud registration) — odometry와 voxel hashmap을 제공. 대규모(도시 블록 단위) 매핑이나 loop closure가 필요한 경우에는 부족하다고 스스로 평가(자신의 사용 목적엔 충분).
- 시각화: Open3D로 3D 포인트클라우드 인터랙티브 뷰 구현(추후 PyQt로 GUI를 옮기면서 Open3D를 계속 쓰는지 본인도 불확실하다고 언급).
- **먼저 ROS(Robot Operating System) + SLAM 패키지를 시도했으나 catkin_make 관련 문제로 약 4시간 소요, 구글링/여러 LLM(Codex, o3, Claude)까지 총동원했지만 실패, 결국 ROS를 포기**하고 KISS-ICP 기반의 훨씬 단순한 순수 Python(+KISS-ICP 자체는 C++일 가능성) 구현으로 전환.
- GUI: 이전 영상 대비 PyQt(PIQt) 기반으로 개선, keyboard listener로 press-hold-release 방식의 텔레옵 구현(이전엔 press 후 스페이스바로 정지해야 하는 불편한 방식).
- 공식 Unitree Python SDK를 뒤늦게 발견(GitHub "unitreerobotics" 조직, unitree_sdk2_python) — 이전 영상에서 직접 만든 C++ wrapper 대신 앞으로 이 공식 SDK를 fork해서 쓸 계획.

## 만드는 과정 — 순서대로 (what he tried first, next, ... in chronological order; the actual workflow)
1. (이전 영상 이후) LiDAR 통합을 제일 먼저 시도 — 공식 문서는 "이해하고 나면 맞는 말이지만 처음엔 진입장벽이 높다"고 평가.
2. 처음엔 ROS로 SLAM을 구현하려 시도 → catkin_make 빌드에서 약 4시간 삽질, 여러 방법(수동 설정, 구글 검색, 여러 LLM) 모두 실패 → ROS 포기.
3. KISS-ICP를 발견해 적용 → Open3D로 시각화 → 비교적 쉽게 동작하는 라이브 3D 포인트클라우드(odometry 포함) 확보, 로봇 방향(빨강=정면, 파랑=아래, 초록=측면 축)까지 시각화.
4. 포인트클라우드가 만들어지자 이를 기반으로 occupancy grid(2D 점유격자) 계산 시도 → "어떤 높이를 장애물로 볼 것인가" 임계값 설정에서 계속 애를 먹음(자막상 "몇 번이고 왔다갔다 했다").
5. occupancy grid 위에서 더블클릭하면 목표지점까지 경로를 계산하는 root/path planning 프로토타입도 시도 — "아직 똑똑하지 않다", 종종 "No path found", 종종 벽을 통과하는 비상식적 경로를 생성.
6. 부팅 시퀀스 개선: 로봇이 이미 balanced stand 상태인데 재시작하면 damp→stand-up 시퀀스를 다시 밟다가 넘어지는 버그를 겪은 뒤(가슴에 스크래치 발생), "이미 균형 상태면 재부팅 시퀀스를 건너뛰는" hanger boot sequence 로직을 추가.
7. 유선에서 벗어나 로컬 메시 Wi-Fi로 원격 통신을 시도 — LiDAR와 로봇 제어(보행)는 Wi-Fi로 성공했지만 RGB 카메라 스트림만 안 됨(원인 불명) → 설정을 되돌리다가 일시적으로 G1과의 연결이 불안정해짐 → 결국 유선 이더넷으로 복귀해 이번 영상까지는 유선 유지.
8. 라이브 데모: 좁은 실내 공간(거실~복도~주방~침실~화장실)을 걸어다니며 LiDAR 포인트가 실시간으로 누적되는 것, occupancy grid가 점점 채워지는 것을 시연. 창문 너머 나무까지 라이다에 잡히는 현상 발견(레이저가 유리를 투과하는 듯한 결과, 본인도 의아해함).
9. 영상 말미에 공식 Unitree Python SDK가 이미 존재함을 뒤늦게 발견 — 자체 제작 C++/Python wrapper 대신 앞으로 공식 SDK를 fork해서 확장하는 방향으로 전환 예정.

## 막힌 곳과 해결법 (failures, bugs, surprises, and how he debugged or worked around them)
- **ROS/catkin_make 삽질(약 4시간)**: 수동 설정, 검색, 여러 LLM을 총동원했지만 실패 → ROS를 완전히 포기하고 KISS-ICP + Open3D의 훨씬 단순한 스택으로 대체.
- **LiDAR가 거꾸로 장착되어 있어 SLAM 데이터가 뒤집혀 나옴** → 뒤집기(flip) 처리로 해결했으나, 이후 occupancy grid 쪽에서는 LLM(03)이 이미 뒤집힌 데이터를 한 번 더 뒤집는 실수를 해서 이중 반전 버그가 발생(다음 영상에서 수정됨 — 영상 17 참고).
- **occupancy grid의 장애물 높이 임계값이 잘 맞지 않음** — "높이를 여러 번 바꿔봤는데 제대로 반영이 안 된다"고 명시, 미해결 상태로 다음 영상으로 이월.
- **경로계획(root planning)이 신뢰할 수 없음** — 주변에 물체가 너무 많으면 "No path found", 때로는 벽을 뚫고 가는 경로를 생성 — 명확히 "아직 똑똑하지 않다"고 인정, 개선 필요 상태로 남김.
- **Wi-Fi 무선화 시도 실패**: RGB 카메라만 Wi-Fi로 스트리밍이 안 되는 원인을 못 찾음, 설정 되돌리다 연결까지 불안정해져서 Jetson 재플래싱 걱정까지 했음 — 결국 유선으로 복귀해 임시 해결(근본 원인 미해결).
- **재부팅 시 낙상 버그** — 이미 균형 상태에서 재시작하면 damp→기립 시퀀스를 다시 밟다가 넘어짐(실제로 한 번 넘어져 가슴에 스크래치) → "이미 balanced standing이면 boot sequence 스킵" 로직 추가로 해결.
- **레이저가 유리창을 통과하는 것처럼 보이는 현상** — 원인을 모른 채 시청자에게 "레이저 전문가가 설명해달라"고 요청(미해결, 불확실 항목으로 남김).

## 수업 개념과 연결 (any link to KF / PF / PID / SLAM / localization / path planning / control loops / RL; write "없음" if none — do not invent links)
- **SLAM**: KISS-ICP는 point cloud 간 반복적 정합(iterative closest point, ICP)으로 프레임 간 상대 변위(odometry)를 추정하고 voxel hashmap으로 지도를 누적하는 방식 — 수업에서 다루는 SLAM의 "스캔 매칭 기반 odometry + map" 개념과 직접 연결됨. 단, loop closure(루프 클로저)는 구현되어 있지 않아 5~10분 정도 사용하면 드리프트(drift)가 누적된다고 스스로 인정 — 이는 수업에서 다루는 "SLAM의 누적 오차 문제, 왜 loop closure/보정이 필요한지"를 실전에서 보여주는 좋은 사례.
- **Localization**: 로봇 자세(orientation, 빨강/파랑/초록 축)를 SLAM 결과로 실시간 표시 — 순수 스캔매칭 기반 localization이며, 칼만필터/파티클필터 같은 확률적 필터링은 사용되지 않음(명시적 언급 없음).
- **Path planning**: occupancy grid 위에서 더블클릭 시 경로를 계산하는 기능을 시도했으나 "아직 똑똑하지 않다"고 스스로 평가 — 알고리즘의 구체적 종류(A*, Dijkstra 등)는 자막에 전혀 언급되지 않음. 수업의 "search/path smoothing"과 개념적으로만 연결되고, 실제 구현 디테일은 불명.
- **PID / KF / PF**: 명시적 언급 없음. 로봇 자체의 균형 제어(gait/balance)는 Unitree 내부 블랙박스 컨트롤러가 담당하는 것으로 보이며, sentdex 본인이 그 알고리즘을 구현한 게 아님("아마 독점적인 알고리즘일 것"이라고만 추정).

## Paul의 Hardware Challenge에 주는 교훈 (concrete, 2–5 bullets)
- **ROS 없이 SLAM 가능**: KISS-ICP + Open3D 조합처럼 ROS 생태계 없이도 가벼운 point-cloud 기반 SLAM을 구현할 수 있음 — Hardware Challenge에서 SLAM을 과제 알고리즘으로 고를 경우, ROS 빌드 트러블슈팅에 시간을 뺏기기보다 이런 경량 대안부터 검토할 가치가 있음(단, ROS 자체를 4시간 만에 포기했다는 건 ROS가 어렵다기보단 이 특정 환경/구성에서 안 됐을 가능성도 있으니, Paul의 플랫폼에서 별도로 확인 필요).
- **센서 장착 방향/기울기는 반드시 명시적으로 보정해야 함**: LiDAR가 거꾸로 달려 있어 뒤집기 처리가 필요했고, 이 반전 처리를 중복 적용하는 실수(더블 플립)까지 발생 — Paul이 직접 센서를 장착/배치할 때 좌표계 변환(mounting offset, rotation)을 코드에 명확히 문서화해두는 습관이 중요함.
- **occupancy grid의 "장애물 임계값"은 튜닝이 필요한 파라미터**임을 실전에서 확인 — Paul이 SLAM/occupancy grid를 과제에 쓴다면 이 임계값 캘리브레이션 과정을 미리 계획에 넣을 것.
- **드리프트(drift)는 단순 ICP 기반 SLAM의 실질적 한계** — loop closure가 없으면 몇 분 만에도 오차가 누적된다는 실증 사례. Paul의 과제에서 KF/PF를 SLAM/로컬라이제이션에 접목한다면, 이 영상에서 보여준 "필터 없는 순수 scan-matching"과 대비해 필터 적용의 이점을 설명하는 좋은 비교 포인트가 될 수 있음.
- **경로계획과 IK/모션은 별개 문제**라는 인식이 이 시리즈 전반에 반복해서 등장함(이 영상에서는 장애물 회피 실패 사례로, 다음 영상들에서 더 명확히 논의됨) — Paul의 Hardware Challenge에서 "search+smoothing"을 고를 경우, 장애물이 있는 환경에서 단순 최단거리 계산만으론 부족하다는 점을 미리 염두에 둘 것.

## 확인 필요 (anything ambiguous in the captions — mark as uncertain rather than guessing)
- LiDAR 상하 시야각 "15도"는 자막상 다소 불확실하게 언급됨(정확한 스펙인지 불명).
- Wi-Fi 환경에서 RGB 카메라만 안 되고 LiDAR/제어는 됐던 이유 — 영상 내에서 끝내 설명되지 않음(미해결).
- 시각화 라이브러리가 Open3D인지 PyQt 자체 렌더링인지 — 본인이 "지금은 Open3D가 아닐 수도 있다"고 스스로 불확실하다고 밝힘.
- "레이저가 창문을 통과하는 것처럼 보이는 현상"은 사실 확인이 아니라 sentdex 본인의 의문 제기이며, 정확한 물리적 설명은 이 영상에서 제공되지 않음.
- "Kiss ICP"와 "Kiss SLAM"이라는 용어가 자막에서 거의 같은 의미로 혼용되는데, 정확히 어떤 라이브러리/패키지명인지(둘이 같은 것인지 다른 것인지)는 자막만으로 확정하기 어려움.
