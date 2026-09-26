# OpenClaw and NemoClaw for the rover (2026-09-25)

Research and recommendation, not an installation decision. Paul asked whether
an existing agent runtime would be useful before proceeding with STT preparation.

## Existing repository notes

`2026-09-25-llm-on-orin-nano-sources.md` mentions the Jetson AI Lab OpenClaw
Nano tutorial and a video walkthrough. No NemoClaw note was found in the
repository text search. Neither runtime has been installed by this task.

## Verified from current first-party documentation

- [OpenClaw architecture](https://docs.openclaw.ai/concepts/architecture): a
  persistent gateway connects clients/channels and agent sessions. Reusing its
  session/tool infrastructure is a plausible way to avoid rebuilding a general
  assistant around our speech pipeline.
- [Jetson AI Lab tutorial](https://www.jetson-ai-lab.com/tutorials/openclaw/): an
  8GB Orin Nano path exists, using Ollama, Qwen3.5 2B, a 16k context and reduced
  tool/workspace overhead. The example changes host packages/services and
  recommends a 16GB swapfile. Those installation steps conflict with our current
  container-only experiment rule. This is evidence of feasibility, not evidence
  that our 4B llama.cpp + Whisper + camera combination fits.
- [NemoClaw overview](https://docs.nvidia.com/nemoclaw/user-guide/openclaw/home):
  an agent deployment stack using OpenShell sandboxing, inference management,
  network policies and lifecycle controls. It is not the Nemotron language model.
- [NemoClaw prerequisites](https://docs.nvidia.com/nemoclaw/latest/user-guide/openclaw/get-started/prerequisites):
  minimum RAM 8GB, recommended 16GB; Node 22.19+, container runtime and free disk
  requirements. The image pipeline can create substantial temporary memory
  pressure. Our exact JetPack 6.2.3 integration is not verified by this review.

## Recommendation (inference; Paul has not decided)

OpenClaw is worth a later bounded container trial once STT is measured. Expose
the transcript and a small set of typed tools (weather, status, navigation) to
the assistant. Navigation and the deterministic motor/safety layer still need
robot-specific implementation; installing an agent does not supply those.

Keep STT independent of the agent runtime: microphone → STT → transcript →
agent → validated robot/service API. This lets us compare our thin assistant
with OpenClaw without replacing the microphone or Whisper implementation.

Defer NemoClaw on this 8GB board until we measure spare memory and need its
policy/isolation features. Its stated minimum leaves little headroom for our
local LLM, STT and future camera workloads; that is a resource concern, not a
claim that Jetson is categorically unsupported. A larger separate host could
be evaluated later if desired.

Before an OpenClaw trial: verify the chosen release's llama.cpp API/tool-call
compatibility and context requirements, container-only installation, memory
with base STT running, and actual task quality. Reuse an existing model server
only after checking compatibility; do not launch duplicate LLM runtimes by default.
