# Jetson Orin Nano Super (8GB) — 모바일 로봇 탑재 실전 조사

조사 대상: NVIDIA Jetson Orin Nano Super Developer Kit (8GB), GT OMSCS CS7638 (Robotics: KF/PF/PID/SLAM) 과제용 + 소형 VLM/LLM 실험 (Mac M5 Pro 64GB와 WiFi로 오프로드 예정). Mac이 유일한 개인 PC (Windows/Linux 없음).

**주의**: 검색 결과 상당수가 1차 문서가 아니라 애그리게이터 사이트(`nvidia-jetson.piveral.com` 등)나 포럼 스레드였습니다. 숫자가 나온 곳은 출처를 명시했고, 상충하거나 공식 문서로 재확인 못 한 값은 "⚠️ 미확인/상충"으로 표시했습니다.

---

## 오늘 사야 할 것 / 나중에 사도 되는 것

### Power 관점
- **오늘 살 필요 없음**: 박스 안에 19V 전원 어댑터가 기본 포함됩니다 (module + carrier board + 19V power supply + 지원 카드). [NVIDIA Quick Start Guide](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/quick_start.html)
- **로봇에 올릴 때(나중에)**: 배터리 구동을 하려면 buck/boost 컨버터나 배터리팩이 별도로 필요합니다 (아래 "전원과 브라운아웃" 참고). 오늘 당장 필요한 건 아니고, 로봇 섀시에 탑재하는 단계에서 준비하면 됩니다.

### WiFi 관점
- **오늘 사는 게 맞음**: Jetson Orin Nano (Super 포함) 개발자 키트는 **WiFi 모듈이 기본 포함되지 않습니다**. M.2 Key-E 슬롯은 있지만 카드는 별매입니다. [NVIDIA Developer Forums](https://forums.developer.nvidia.com/t/orin-nano-dev-kit-m-2-key-e-wifi-slot-dead-141e0000-phy-link-never-came-up-two-known-good-cards-requesting-rma/376637), [Yahboom 8822CE M.2 카드 (Orin Nano Super 호환 명시)](https://category.yahboom.net/products/jetson-nano-network-card)
  - Micro Center에 있다면 RTL8822CE 계열 M.2 Key-E 카드([Seeed Studio 판매](https://wiki.seeedstudio.com/rtl8822ce_wireless_module_for_jetson/))가 Jetson 커뮤니티에서 가장 많이 쓰이는 "plug & play" 옵션입니다. [NVIDIA Forums 스레드](https://forums.developer.nvidia.com/t/plug-play-wifi-module-for-jetpack-6-jetson-orin-nano/334346)도 이걸 확인해줍니다.
  - 대안(⚠️ 미확인 — 특정 모델명까지 검증 못함): USB WiFi 동글도 커널이 지원하는 칩셋이면 동작합니다. 다만 이건 오늘 급하게 살 필요는 없고, 초기 셋업은 유선 이더넷이나 부팅 시 모니터+키보드로 진행 가능하므로 M.2 카드가 없어도 당장 막히진 않습니다. Micro Center에 없으면 온라인으로 나중에 주문해도 됩니다.

### Storage 관점
- **오늘 사면 좋음, 필수는 아님**: microSD만으로도 부팅/개발 가능하지만, NVMe SSD(M.2 Key-M, **2280** 폼팩터, PCIe Gen3)를 꽂으면 부팅 속도·내구성이 훨씬 낫고 로봇에서 흔들림에도 SD카드보다 안정적입니다. [NVIDIA Hardware Layout 문서](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/hardware_layout.html)
  - 슬롯은 **1개**, M.2 Key-M, **2280 사이즈**가 기본 지원. 2242 등 짧은 폼팩터는 length adapter 없이는 물리적으로 헐겁게 고정될 수 있음(⚠️ 공식 문서로 2242 지원 명시 재확인은 못했고, "2280이 표준"이라는 점만 여러 소스에서 일치). [Cytron 제품 페이지 (JetPack용 2280 NVMe)](https://www.cytron.io/p-nvme-2280-m-key-makerdisk-ssd-512gb-jetpack-for-jetson-orin-nano)
  - PCIe **Gen3**라서 Gen4 SSD를 꽂아도 Gen3 속도로만 동작 (돈 낭비 방지 포인트).

---

## 전원과 브라운아웃 (Power & Brownout)

### 기본 스펙
- Carrier board 입력: **DC 7–20V** (barrel jack, 5.5mm OD / 2.5mm ID, center positive). ⚠️ 일부 문서/스레드는 9–20V로도 표기해서 정확한 하한값은 상충합니다 — 안전하게 **9V 이상**을 목표로 잡으세요. [NVIDIA Forums](https://forums.developer.nvidia.com/t/jetson-orin-nano-input-voltage/298625), [JetsonHacks 배터리 글](https://jetsonhacks.com/2021/07/16/nvidia-jetsons-on-battery-power/) ("Orin family operates at 9–19V input, unlike the Nano which requires 5V")
- 기본 동봉 어댑터: **19V** (정확한 A/W 수치는 NVIDIA 공식 Quick Start Guide에 명시되어 있지 않음 — ⚠️ 미확인). 서드파티 호환 어댑터는 19V/2.37A(~45W) 제품이 유통됨. [NVIDIA Quick Start Guide](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/quick_start.html), [Yahboom 19V/2.37A 어댑터](https://category.yahboom.net/products/jetson-power-supply)
- USB-C PD: Jetson Orin Nano/NX 계열은 USB-C를 통한 Power Delivery 입력을 지원합니다. 애그리게이터 기준 **20V/45W가 최소 요구치**로 언급되지만, 이건 Orin Nano Super 전용 공식 스펙 페이지에서 직접 재확인하지 못했습니다 (⚠️ 미확인, 다만 가능성 높음). USB-C로 전원을 줄 경우 PD 프로토콜을 정상적으로 협상하는 케이블/충전기가 필요합니다. [NVIDIA Forums: Powering Jetson Orin Nano/NX over USB-C](https://forums.developer.nvidia.com/t/powering-jetson-orin-nano-nx-over-usb-c/232404), [piveral.com 정리 글](https://nvidia-jetson.piveral.com/jetson-orin-nano/powering-the-nvidia-jetson-orin-nano-dev-board-io-port-and-usb-c-options/)
  - **결론**: 25W Super mode처럼 부하가 큰 상태에서 USB-C PD로 안정적으로 구동하려면 45W급 PD 충전기가 필요해 보이고, 그보다 낮은 PD 충전기(예: 흔한 20W 폰 충전기)는 성능 저하나 브라운아웃 위험이 있다고 추정됩니다. 로봇에 올릴 땐 barrel jack + DC-DC 컨버터 쪽이 커뮤니티에서 더 검증된 경로입니다.

### 브라운아웃 증상
- Undervoltage(전압 부족) 상태에서는 **LED가 어둡게 켜져 있어도 SoC가 reset 상태를 벗어나지 못합니다** — 즉 겉보기엔 켜진 것 같은데 실제로 부팅이 안 되는 게 전형적 증상입니다. [piveral.com: Jetson Orin Nano Power Supply Issues](https://nvidia-jetson.piveral.com/jetson-orin-nano/jetson-orin-nano-power-supply-issues/)
- Over-current 보호가 걸리면 **"System throttled due to Over-current"** 경고가 뜨고, 특히 **OC3 채널 (VDD_IN instant power)**에서 순간적인 전류 스파이크가 감지되면 시스템이 스로틀링되거나 리부팅됩니다. 25W Super mode에서 이 경고+리부팅을 겪었다는 사용자 리포트가 있습니다. [NVIDIA Forums: Overcurrent warning & reboot on 25W mode](https://forums.developer.nvidia.com/t/overcurrent-warning-reboot-on-25w-mode/341551), [piveral.com](https://nvidia-jetson.piveral.com/jetson-orin-nano/system-throttled-due-to-over-current-on-jetson-orin-nano/)
- **모터가 브라운아웃을 일으키는 메커니즘**: 모터(특히 기동 시 inrush current, PWM 스위칭)를 Jetson과 같은 전원 레일에서 직접 구동하면 모터 기동 순간 전압이 급격히 sag하면서 Jetson이 리셋됩니다. 이건 Jetson 계열 전반에서 반복적으로 보고되는 패턴입니다 — **모터 전원과 Jetson 전원을 반드시 분리**하거나, 공유할 경우 넉넉한 버퍼 커패시터/배터리를 두라는 게 커뮤니티 컨센서스입니다. [NVIDIA Forums 관련 논의](https://forums.developer.nvidia.com/t/choosing-power-source-for-jetson-nano-when-using-on-mobile-robot/122720/1)

### 25W Super mode 전류 관련 수치
- 25W(MAXN) 모드에서의 **정확한 A(암페어) 소비 실측치는 이번 조사에서 1차 문서/신뢰 가능한 실측 블로그로 확인하지 못했습니다** (⚠️ 미확인). 다만 19V 어댑터 기준 25W ≈ 1.3A 수준의 평균 소비이고, 스파이크성 부하(카메라+모델 추론 동시)는 이보다 순간적으로 높을 수 있다는 게 over-current 보고들의 시사점입니다.
- NVIDIA 공식 권장(애그리게이터 경유, ⚠️ 완전 1차 확인은 못함): barrel jack 기준 **19V, 최소 2.0A**, 지속 부하엔 **3.42A/65W 권장**. [piveral.com: Jetson Orin Nano Developer Kit Power Supply Specifications](https://nvidia-jetson.piveral.com/jetson-orin-nano/jetson-orin-nano-developer-kit-power-supply-specifications/)

### 로봇 배터리 구동 — 구체적 권장
- JetsonHacks 실측 사례: **NP-F 스타일 카메라 배터리(18650 페어, 공칭 7.4V, 풀충전 8.4V, 방전 하한 6.6V — 6V 밑으로 절대 내려가면 안 됨)**를 "boost converter"로 **7.4V → 12V** 승압해서 barrel jack에 공급하는 방식이 흔히 쓰입니다. 컨버터의 입출력 전압차는 최소 1.5V는 있어야 한다는 실전 팁도 있습니다. 이 조합으로 Xavier NX + 3D lidar + 카메라를 **1.3시간** 구동한 실측 사례가 있습니다(참고용, Orin Nano Super와 소비전력은 다를 수 있음). [JetsonHacks: NVIDIA Jetsons on Battery Power](https://jetsonhacks.com/2021/07/16/nvidia-jetsons-on-battery-power/)
- 포럼 기준 모바일 로보틱스에서는 **4S LiPo (완충 16.8V ~ 방전 12.8V)**가 자주 쓰이며, 7–20V(또는 9–20V) 입력 범위에 안전하게 들어갑니다. [Chief Delphi: Powering Jetson Orin Nano](https://www.chiefdelphi.com/t/powering-jetson-orin-nano/459092) (⚠️ 이건 로보틱스 커뮤니티 포럼 컨센서스이지 NVIDIA 공식 권장은 아님)
- **실전 권장**: barrel jack으로 갈 거면 (1) 모터 전원 분리, (2) DC-DC 벅/부스트 컨버터로 12~19V 안정 출력, (3) 컨버터 정격 전류는 피크 소비(카메라+모델+모터 컨트롤러 동시 기동)보다 확실히 여유 있게, (4) 가능하면 전해 커패시터로 버퍼링. 정확한 피크 A 스펙은 미확인이므로 실측(멀티미터/USB 전력계)으로 직접 확인하는 걸 권합니다.

---

## Mac만으로 셋업 가능한가

**결론: 네, 가능합니다 — 그리고 최근(JetPack 7.2 이후) NVIDIA가 이 경로를 공식적으로 더 쉽게 만들었습니다.** SDK Manager(Ubuntu 필수)를 안 써도 되는 흐름이 이제 기본값입니다.

### 현재 상황 (2026년 9월 기준)
- 현재 공식 문서상 최신 JetPack은 **JetPack 7.2.1** (Jetson Linux/L4T r39.2.1)이며, Quick Start Guide가 이를 기준으로 작성되어 있습니다. [NVIDIA Quick Start Guide](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/quick_start.html)
- **큰 변화**: JetPack 7.2부터 **Jetson Orin Nano용 SD 카드 이미지가 더 이상 제공되지 않습니다.** 대신 통합 **USB ISO installer** 방식으로 바뀌었습니다 — ISO를 USB 플래시 드라이브(16GB+)에 써서, 그 USB로 Jetson을 부팅한 뒤 microSD나 NVMe SSD에 설치하는 방식입니다. [JetsonHacks: JetPack 7.2.1 Released!](https://jetsonhacks.com/2026/08/12/jetpack-7-2-1-released/)
- 이 USB ISO installer는 **Ubuntu 우분투 호스트 PC 없이도 동작**합니다 — Jetson 자체가 USB 스틱으로 부팅해서 독립적으로 설치를 진행하는(Ubuntu 설치 USB와 비슷한) 방식입니다. USB에 ISO를 굽는 데는 **Balena Etcher**를 쓰는데, 이건 macOS를 포함한 크로스플랫폼 툴입니다. [NVIDIA Forums 스레드 (ISO 설치 과정 확인)](https://forums.developer.nvidia.com/t/jetpack-7-2-iso-installer-consistently-fails-when-installing-to-usb-ssd-on-jetson-orin-nano-developer-kit-curtininstallerror-nonetype-bcache/375658)
  - ⚠️ 주의: 같은 스레드에서 USB SSD로의 설치는 NVIDIA가 "공식 지원 안 함(We don't support the usb ssd)"이라고 밝혔고, 설치 UI엔 옵션이 뜨지만 실패 사례(`CurtinInstallError`, `bcache` 모듈 없음 등)가 보고됩니다. **NVMe SSD 또는 microSD로 설치하는 게 안전**합니다.

### 구형 유닛(사전 36.0 펌웨어)이면 한 단계 더 필요
- Micro Center 재고가 이전 JetPack 5/6 시절 펌웨어로 나갔다면, **QSPI 펌웨어가 36.0 미만**일 수 있고, 이 경우 JetPack 7.2.1 ISO를 바로 부팅하기 전에 **JetPack 6.x 세대 펌웨어로 먼저 업데이트**해야 합니다. [NVIDIA: JetPack 6.x Update Path](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/update_firmware.html)
- 이 펌웨어 업데이트 경로는 문서에 명시적으로 **"Use this method when you do not have an Ubuntu host PC available"**라고 적혀 있어, **호스트 PC 없이 microSD만으로 가능**합니다:
  1. **JetPack 5.1.3** SD 카드 이미지(`JP513-orin-nano-sd-card-image_b29.zip`, 최근 업데이트된 빌드 — 반드시 이 버전 사용)를 Balena Etcher로 microSD에 씀
  2. 그 SD카드로 부팅, Ubuntu 초기 설정 완료, 인터넷 연결 → 펌웨어 업데이트가 자동으로 예약됨
  3. 재부팅 → 화면/시리얼로 펌웨어 업데이트 진행 확인
  4. `sudo apt install nvidia-l4t-jetson-orin-nano-qspi-updater` 실행
  5. 재부팅 → QSPI 업데이트 완료
  6. 전원 끄고 SD카드를 최종 목표 JetPack(7.2.1) USB로 교체 → 부팅 및 설치
  7. 전원 관리 중 **업데이트 도중 전원을 뽑지 말 것** (문서 강조)
  - [NVIDIA: JetPack 6.x Update Path](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/update_firmware.html)

### Mac 셋업 단계별 결론
1. 펌웨어가 구형(pre-36.0)이면: Mac에서 Balena Etcher로 JetPack 5.1.3 SD 이미지를 구움 → Jetson에 모니터+키보드(또는 USB-시리얼 케이블)로 연결해 초기 설정 → 자동 QSPI 업데이트 완료. **Mac만으로 가능.**
2. 최종 OS 설치: Mac에서 Balena Etcher로 JetPack 7.2.1 ISO를 USB 스틱(16GB+)에 구움 → Jetson이 그 USB로 부팅 → 설치 대상은 **NVMe SSD 또는 microSD** (USB SSD는 피할 것) → 설치 완료 후 재부팅. **Mac만으로 가능.**
3. NVIDIA SDK Manager는 필요 없습니다 (SDK Manager는 Ubuntu 22.04/20.04 x64 호스트가 필수인 별개의 옛 경로입니다 — 이번 흐름에서는 안 써도 됨). [NVIDIA JetPack Install/Setup 문서](https://docs.nvidia.com/jetson/jetpack/install-setup/index.html)

**요약**: Windows/Linux PC 없이 Mac만으로 처음부터 끝까지 셋업 가능합니다. 단, 모니터+키보드(또는 시리얼 케이블)는 최초 1~2회 필요하고, 완전 headless(SSH만으로) 초기 설정은 공식적으로 보장되지 않습니다 (아래 "초보자 실수" 참고).

---

## 성능 현실 (Performance Reality)

모든 수치는 **Jetson Orin Nano Super, 25W(MAXN) 모드** 기준입니다.

| 항목 | 수치 | 출처 |
|---|---|---|
| GPU 클럭 (MAXN) | 1,020 MHz (기존 635 MHz 대비) | [NVIDIA Blog: Super Boost](https://developer.nvidia.com/blog/nvidia-jetson-orin-nano-developer-kit-gets-a-super-boost/) |
| AI 성능 (MAXN) | 67 TOPS (Sparse) / 33 TOPS (Dense) / 17 FP16 TFLOPs | [NVIDIA Blog: Super Boost](https://developer.nvidia.com/blog/nvidia-jetson-orin-nano-developer-kit-gets-a-super-boost/) |
| 메모리 대역폭 (MAXN) | 102 GB/s (기존 65 GB/s 대비) | [NVIDIA Blog: Super Boost](https://developer.nvidia.com/blog/nvidia-jetson-orin-nano-developer-kit-gets-a-super-boost/) |
| Super mode 요구사항 | JetPack 6.1 이상 (`sudo nvpmodel -m 2`로 활성화) | [NVIDIA Blog: Super Boost](https://developer.nvidia.com/blog/nvidia-jetson-orin-nano-developer-kit-gets-a-super-boost/) |
| Llama 3.2 3B | 43.07 tok/s (일반 모드 27.7 tok/s 대비 1.55x) | [Jetson AI Lab Benchmarks](https://www.jetson-ai-lab.com/archive/benchmarks.html) |
| Gemma 2 2B | 34.97 tok/s (1.63x) | [Jetson AI Lab Benchmarks](https://www.jetson-ai-lab.com/archive/benchmarks.html) |
| Phi 3.5 3B | 38.1 tok/s (1.54x) | [Jetson AI Lab Benchmarks](https://www.jetson-ai-lab.com/archive/benchmarks.html) |
| SmolLM2 | 64.5 tok/s (1.57x) | [Jetson AI Lab Benchmarks](https://www.jetson-ai-lab.com/archive/benchmarks.html) |
| VILA 1.5 3B (VLM) | 1.06 fps (1.51x) | [Jetson AI Lab Benchmarks](https://www.jetson-ai-lab.com/archive/benchmarks.html) |
| PaliGemma2 3B (VLM) | 21.6 fps (1.58x) | [Jetson AI Lab Benchmarks](https://www.jetson-ai-lab.com/archive/benchmarks.html) |
| SmolVLM 2B (VLM) | 12.9 fps (1.59x) | [Jetson AI Lab Benchmarks](https://www.jetson-ai-lab.com/archive/benchmarks.html) |
| Qwen3 0.6B (Ollama, 실측) | 38.84 tok/s | [Eric X. Liu 블로그](https://ericxliu.me/posts/benchmarking-llms-on-jetson-orin-nano/) |
| Qwen2.5 0.5B (Ollama, 실측) | 35.24 tok/s | [Eric X. Liu 블로그](https://ericxliu.me/posts/benchmarking-llms-on-jetson-orin-nano/) |
| Gemma3 1B (Ollama, 실측) | 26.33 tok/s | [Eric X. Liu 블로그](https://ericxliu.me/posts/benchmarking-llms-on-jetson-orin-nano/) |

### 8GB 공유 메모리에서 실제로 쓸 수 있는 양
- OS + 백그라운드 프로세스 오버헤드 제외하면 **실사용 가능 메모리는 약 5.2GB** (전체 8GB 중 약 2.8GB는 OS가 먼저 씀). [Eric X. Liu 블로그: Why Your Jetson Orin Nano's 40 TOPS Goes Unused](https://ericxliu.me/posts/benchmarking-llms-on-jetson-orin-nano/)
- 같은 저자는 **0.5B~1B 파라미터급(3GB 미만)** 모델에 집중해야 KV cache 여유가 남는다고 권장하며, 84개 테스트 중 66개(78.6%)만 성공, 실패 대부분이 **큰 모델에서의 OOM(메모리 부족) 크래시**였다고 보고합니다. [Eric X. Liu 블로그](https://ericxliu.me/posts/benchmarking-llms-on-jetson-orin-nano/)
- **당신의 유스케이스(OpenCV + KF + PID + 소형 VLM 실험, 무거운 건 Mac으로 오프로드)에는 이 메모리 제약이 오히려 잘 맞습니다** — 온보드에서는 가볍게 굴리고, 무거운 추론은 WiFi로 Mac(64GB)에 던지는 설계가 8GB 제약을 우회하는 정석적인 방법입니다.

---

## 초보자가 날리는 시간 Top 5와 회피법

1. **Super mode를 안 켜고 "왜 느리지" 헤맴**: JetPack 6.1+ 에서도 기본값이 아닐 수 있음 — `sudo nvpmodel -m 2` (또는 Ubuntu 데스크톱 상단바 Power Mode Selector)로 MAXN(25W) 모드를 직접 켜야 함. [NVIDIA Blog: Super Boost](https://developer.nvidia.com/blog/nvidia-jetson-orin-nano-developer-kit-gets-a-super-boost/)
   → 회피: 설치 직후 `nvpmodel -q` 로 현재 모드 확인, `jetson_clocks`까지 같이 실행해 클럭을 고정.
2. **JetPack/QSPI 펌웨어 버전 불일치로 설치가 반복 실패**: `nv_tegra_release` 파일이 실제 JetPack 버전과 다르게 나오는 등 혼란이 보고됨. 특히 JetPack 7.2.1은 **JetPack 6.x 세대 QSPI 펌웨어가 선행 조건**이라 구형 유닛에서 바로 ISO를 부팅하면 실패함. [NVIDIA Forums: nv_tegra_release 불일치 사례](https://nvidia-jetson.piveral.com/jetson-orin-nano/jetson-orin-nano-nv_tegra_release-differs-from-jetpack-version/), [NVIDIA: JetPack 6.x Update Path](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/update_firmware.html)
   → 회피: 부팅 시 Esc로 UEFI 메뉴 들어가 현재 펌웨어 버전부터 확인. 36.0 미만이면 위 "Mac 셋업" 섹션의 QSPI 업데이트부터.
3. **Docker 이미지가 JetPack 버전과 안 맞음**: JetPack 버전별로 L4T/CUDA 조합이 다르기 때문에, 다른 버전용 컨테이너 이미지를 그대로 쓰면 실행이 안 되거나 이상 동작함. [Plate Recognizer Jetson FAQ](https://guides.platerecognizer.com/docs/jetson/)
   → 회피: 컨테이너를 받을 때 반드시 설치된 정확한 JetPack/L4T 버전에 맞는 태그(NVIDIA NGC 등)를 확인.
4. **카메라 드라이버가 JetPack 버전 업 후 깨짐**: JetPack 6.0에서 `v4l2src`로 이미지가 불완전하게 잡히는 문제, 비디오 디바이스 순서가 버전마다 바뀌는 문제가 보고됨 (`nvv4l2camerasrc`가 더 안정적이었다는 사례). [piveral.com: Camera Capture Issues with JetPack 6.0](https://nvidia-jetson.piveral.com/jetson-orin-nano/camera-capture-issues-with-jetpack-6-0-on-jetson-orin-nano/)
   → 회피: OpenCV로 카메라를 열 때 GStreamer 파이프라인(`nvv4l2camerasrc` 등)을 우선 시도하고, `/dev/video*` 번호를 하드코딩하지 말고 매번 확인.
5. **완전 headless(모니터/키보드 없이 SSH만)로 첫 설정을 시도하다가 막힘**: 최근 JetPack은 보안상 기본 계정/비밀번호를 안 주기 때문에 최초 1회는 화면+키보드(또는 시리얼 콘솔)로 직접 계정을 만들어야 함. SSH는 그 이후에나 씀. [NVIDIA Forums: Headless Setup 관련 논의](https://forums.developer.nvidia.com/t/jetson-orin-nano-headless-setup-ready-to-ssh/277765)
   → 회피: 처음 한두 번은 모니터+키보드(또는 USB-TTL 시리얼 케이블, 115200 baud)로 계정 생성까지만 하고, 이후엔 SSH로 전환. "Mac만 있으니 완전 무모니터로 되겠지"라는 가정은 첫 부팅 단계에서 깨질 가능성이 높음.

번외(시간 날리기 6위, 참고): **열/전원 관리 자체는 이번 조사에서 Orin Nano Super 관련 thermal throttling 실측 리포트를 찾지 못했습니다** (⚠️ 미확인 — 위 Eric X. Liu 블로그도 "thermal throttling 이슈 없었다"고만 언급). 다만 로봇처럼 밀폐된 인클로저에 넣을 계획이면 방열판/팬 공기 흐름은 별도로 확인 권장 (이번 조사 범위 밖).

---

## 출처 (전체)

- [NVIDIA Jetson Orin Nano Developer Kit — Quick Start Guide](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/quick_start.html)
- [NVIDIA Jetson Orin Nano Developer Kit — JetPack 6.x Update Path (firmware)](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/update_firmware.html)
- [NVIDIA Jetson Orin Nano Developer Kit — Hardware Layout](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/hardware_layout.html)
- [NVIDIA JetPack — Install/Setup 문서](https://docs.nvidia.com/jetson/jetpack/install-setup/index.html)
- [NVIDIA Technical Blog — Jetson Orin Nano Developer Kit Gets a "Super" Boost](https://developer.nvidia.com/blog/nvidia-jetson-orin-nano-developer-kit-gets-a-super-boost/)
- [NVIDIA Jetson AI Lab — Benchmarks](https://www.jetson-ai-lab.com/archive/benchmarks.html)
- [JetsonHacks — JetPack 7.2.1 Released!](https://jetsonhacks.com/2026/08/12/jetpack-7-2-1-released/)
- [JetsonHacks — NVIDIA Jetsons on Battery Power](https://jetsonhacks.com/2021/07/16/nvidia-jetsons-on-battery-power/)
- [Eric X. Liu — Why Your Jetson Orin Nano's 40 TOPS Goes Unused](https://ericxliu.me/posts/benchmarking-llms-on-jetson-orin-nano/)
- [NVIDIA Developer Forums — JetPack 7.2 ISO installer 이슈 (USB SSD 미지원 확인)](https://forums.developer.nvidia.com/t/jetpack-7-2-iso-installer-consistently-fails-when-installing-to-usb-ssd-on-jetson-orin-nano-developer-kit-curtininstallerror-nonetype-bcache/375658)
- [NVIDIA Developer Forums — Powering Jetson Orin Nano/NX over USB-C](https://forums.developer.nvidia.com/t/powering-jetson-orin-nano-nx-over-usb-c/232404)
- [NVIDIA Developer Forums — Jetson Orin Nano Input Voltage](https://forums.developer.nvidia.com/t/jetson-orin-nano-input-voltage/298625)
- [NVIDIA Developer Forums — Overcurrent warning & reboot on 25W mode](https://forums.developer.nvidia.com/t/overcurrent-warning-reboot-on-25w-mode/341551)
- [NVIDIA Developer Forums — M.2 Key-E WiFi slot 관련](https://forums.developer.nvidia.com/t/orin-nano-dev-kit-m-2-key-e-wifi-slot-dead-141e0000-phy-link-never-came-up-two-known-good-cards-requesting-rma/376637)
- [NVIDIA Developer Forums — Plug & play wifi module for JetPack 6](https://forums.developer.nvidia.com/t/plug-play-wifi-module-for-jetpack-6-jetson-orin-nano/334346)
- [NVIDIA Developer Forums — Choosing power source for mobile robot](https://forums.developer.nvidia.com/t/choosing-power-source-for-jetson-nano-when-using-on-mobile-robot/122720/1)
- [NVIDIA Developer Forums — Headless setup ready to SSH](https://forums.developer.nvidia.com/t/jetson-orin-nano-headless-setup-ready-to-ssh/277765)
- [Seeed Studio Wiki — RTL8822CE Wireless Module for Jetson](https://wiki.seeedstudio.com/rtl8822ce_wireless_module_for_jetson/)
- [Yahboom — 8822CE NGW M.2 카드 (Orin Nano/NX Super 호환)](https://category.yahboom.net/products/jetson-nano-network-card)
- [Yahboom — 19V/2.37A DC Power Supply](https://category.yahboom.net/products/jetson-power-supply)
- [Cytron — NVMe 2280 M-Key MakerDisk SSD (JetPack for Orin Nano Super)](https://www.cytron.io/p-nvme-2280-m-key-makerdisk-ssd-512gb-jetpack-for-jetson-orin-nano)
- [Chief Delphi — Powering Jetson Orin Nano (4S LiPo 논의)](https://www.chiefdelphi.com/t/powering-jetson-orin-nano/459092)
- [Plate Recognizer — Nvidia Jetson FAQ (Docker/JetPack 버전 이슈)](https://guides.platerecognizer.com/docs/jetson/)
- [piveral.com — Jetson Orin Nano Developer Kit Power Supply Specifications](https://nvidia-jetson.piveral.com/jetson-orin-nano/jetson-orin-nano-developer-kit-power-supply-specifications/) (⚠️ 애그리게이터, 1차 문서 아님)
- [piveral.com — Jetson Orin Nano Power Supply Issues (undervoltage 증상)](https://nvidia-jetson.piveral.com/jetson-orin-nano/jetson-orin-nano-power-supply-issues/) (⚠️ 애그리게이터)
- [piveral.com — System throttled due to Over-current](https://nvidia-jetson.piveral.com/jetson-orin-nano/system-throttled-due-to-over-current-on-jetson-orin-nano/) (⚠️ 애그리게이터)
- [piveral.com — Camera Capture Issues with JetPack 6.0](https://nvidia-jetson.piveral.com/jetson-orin-nano/camera-capture-issues-with-jetpack-6-0-on-jetson-orin-nano/) (⚠️ 애그리게이터)
- [piveral.com — nv_tegra_release differs from JetPack version](https://nvidia-jetson.piveral.com/jetson-orin-nano/jetson-orin-nano-nv_tegra_release-differs-from-jetpack-version/) (⚠️ 애그리게이터)
