# Hugging Face model shortlist for the 8 GB Jetson robot (2026-10-03)

Dated research snapshot, not a decision. Board budget: ~4.5–5 GB usable GPU memory with the desktop on; one 2–4B LLM already takes ~2.5–3 GB (see `docs/verify.md`). No Orin Nano fps or memory figures were collected for any model below; each needs measuring before adoption.

Evidence labels: VERIFIED = read on the model card or HF API on 2026-10-03; INFERENCE = not checked.

| Task | First pick | Alternative | License | Evidence / caveat |
|---|---|---|---|---|
| Person / object detection | `Roboflow/rf-detr-nano` (30.5M params) | `Ultralytics/YOLO26` n/s | RF-DETR Apache-2.0 (VERIFIED); **YOLO26 AGPL-3.0** (VERIFIED) | Model card has no latency or export notes; paper arXiv 2511.09554. TensorRT export and Jetson fps unverified |
| Tracking (keep the same ID) | ByteTrack algorithm, no model | BoT-SORT + OSNet re-ID (~2M) | depends on the packaging library | INFERENCE |
| "Find the red cup" (open vocabulary) | YOLOE | OWLv2 base, Grounding DINO tiny | YOLOE AGPL (INFERENCE); others Apache-2.0 (INFERENCE) | OWLv2 / Grounding DINO likely only a few fps; on-demand use |
| Segmentation | `facebook/sam2.1-hiera-tiny` (~39M) | MobileSAM, EfficientSAM | Apache-2.0 (INFERENCE) | later phase |
| Pose / gestures | RTMPose (rtmlib, ONNX) | YOLO26-pose | RTMPose Apache-2.0 (INFERENCE); YOLO26-pose AGPL (VERIFIED) | later phase |
| "What do you see" | Gemma 4 E2B image input (already loaded LLM) | `Qwen/Qwen3-VL-2B-Instruct-GGUF` | Gemma terms; Qwen3-VL Apache-2.0 (VERIFIED) | needs the mmproj file; two resident models will not fit |
| Speech to text | `Qwen/Qwen3-ASR-0.6B` | Whisper small / large-v3-turbo | Apache-2.0 (VERIFIED); Whisper MIT | Qwen3-ASR: 30 languages incl. Korean, streaming + offline (VERIFIED); GGUF build `handy-computer/Qwen3-ASR-0.6B-gguf` exists (VERIFIED) |
| Text to speech | `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` (0.9B in BF16) | MeloTTS-Korean (~40M) | Apache-2.0 (VERIFIED); MeloTTS MIT (INFERENCE) | 10 languages incl. Korean, 9 voices incl. "Sohee", streaming, "as low as 97 ms" end-to-end on the vendor's hardware (VERIFIED); GGUF `Serveurperso/Qwen3-TTS-GGUF` exists (VERIFIED) |
| Depth | none | — | — | the D436 gives metric depth; use RealSense post-processing for holes |
| Arm policy (later) | LeRobot ACT (~80M) | `lerobot/smolvla_base` (~450M) | Apache-2.0 | needs an arm and demonstrations |

Suggested order: (1) RF-DETR nano + ByteTrack + D436 depth for person detection with distance (feeds pan-tilt tracking); (2) Qwen3-ASR-0.6B for Korean/English voice in, Qwen3-TTS-0.6B or MeloTTS-Korean for voice out, run when the LLM is idle; (3) Gemma 4 E2B image input for "what do you see" before adding a second VLM.

Licensing trap: Ultralytics YOLO11/YOLO26/YOLOE and their pose variants are AGPL-3.0. Fine for this public personal repository; a closed or commercial robot would need a paid licence.
