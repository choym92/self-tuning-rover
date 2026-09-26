# Agent instructions — self-tuning-rover

This file is the single source of repository instructions for coding agents.
`CLAUDE.md` imports it; do not duplicate these rules there.

## Project and communication

This is Paul Cho's self-tuning rover on a Jetson Orin Nano Super 8 GB. Sensor
streams are timestamped and logged, replayed on the Mac, scored against ground
truth, and used to tune filter/controller parameters.

Paul is a Data Science Lead, not a software engineer. Explain commands and keep
steps small. Chat with him in Korean. Write repository files in English.

## Start here, then read only what the task needs

Always read `docs/STATUS.md`. It is the short, current handoff. Do not infer
live device state from it: run its read-only checks when live state matters.

| Task | Read |
|---|---|
| Project orientation | `README.md` |
| Architecture or a durable choice | `docs/decisions.md`; relevant design doc |
| Claim about measured behavior | `docs/verify.md` |
| Command that changes the Jetson/system | relevant entry in `docs/preflight.md` |
| Investigating an earlier setup failure | relevant dated section in `docs/setup-log.md` |
| Voice work | `jetson/voice/README.md`, `docs/voice-orchestration.md` |
| LLM work | `jetson/llm/README.md`; results in `docs/verify.md` |
| Parts or purchase status | `docs/build-spec.md` |
| Historical research only | a specifically relevant file under `docs/reference/` |

Do not read every document by default. `docs/reference/` is dated evidence, not
current truth. Search headings first and open only the relevant section.

## Device access

| Item | Value |
|---|---|
| Jetson | Orin Nano Super Developer Kit 8 GB; hostname `paul-cho-jetson` |
| SSH | `ssh paulcho@192.168.1.234` from the home LAN; key login is configured |
| Current OS/software state | `docs/STATUS.md`; verify live before acting |
| sudo | Paul enters it himself. Never type or ask for his password |
| Docker | NVIDIA runtime; group membership may be temporary—check `docs/STATUS.md` |
| Python | `~/venvs/robot` (3.10); RealSense RSUSB build documented in the setup log |

Mac prompt: `Pauls-MacBook-Pro`. Jetson prompt: `paulcho@paul-cho-jetson`.
Check the host before every device command. Never insert the fallback microSD
while the NVMe system is running; their filesystem UUIDs are identical.

## Rules that are not negotiable

1. **One device-changing step at a time.** Before a device/system mutation or
   costly/irreversible action, propose the exact step, get Paul's explicit go,
   run it, report what happened, then propose the next. Within an already
   authorized repository task, batch reversible edits, read-only checks, tests
   and documentation as needed. Never record a decision Paul has not made.
2. **Preflight before a device/system change.** For host installs, boot config,
   firmware, kernel, services or similar changes, follow `docs/preflight.md`:
   exact-version source, known issues, read-only facts, VERIFIED vs INFERENCE,
   fallback, guarded command. Research and read-only checks need no preflight.
3. **No experiment dependencies on the Jetson host.** Use containers,
   `/home/paulcho/models` and `/home/paulcho/llm`. Do not edit `daemon.json`,
   add systemd units/swapfiles, or install global npm/pip packages.
4. **Report faithfully.** Include failures and unverified assumptions. Never
   turn a plan, recommendation, order or inference into a completed fact.
5. **Commits:** English, plain messages, no AI signature or co-author line.
   Push completed work to `origin main` only after verification. When multiple
   agents share the checkout, only the coordinating agent commits or pushes;
   all agents preserve the edits made by others.
6. Never edit a running script. Reddit is blocked; do not try workarounds.
7. Files in the separate CS7638 course repository are off limits.

## Decision review

For a hard-to-reverse architecture, device, safety, security, privacy or
high-cost choice with multiple credible options, use at least two agents when
capacity permits: one proposer and one adversarial reviewer. The proposer
compares viable options and evidence. The reviewer independently inspects the
evidence and challenges assumptions, failure modes and cheaper alternatives.
The coordinating agent synthesizes the result, preserves material disagreement
and leaves genuinely user-owned choices to Paul. Agreement is not proof.

Do not use multi-agent review for routine implementation, documentation,
verification, status maintenance or execution of an already-decided plan.
Store only the final decision and rationale in `docs/decisions.md`; do not store
agent transcripts. Follow an explicit request from Paul for broader debate.

## Documentation discipline

Each fact has one canonical home:

- current handoff and next steps → `docs/STATUS.md`
- accepted/proposed/superseded choices and reasons → `docs/decisions.md`
- measurements and test evidence → `docs/verify.md`
- risk review before a device change → `docs/preflight.md`
- chronological setup incidents → `docs/setup-log.md`
- subsystem architecture → its design document
- dated external research → `docs/reference/`

`docs/STATUS.md` is a short derived dashboard, not an evidence source. Update
the canonical decision, measurement or incident record first and update
`STATUS.md` last, only when the active objective, verified capability, blocker
or next step materially changes. If it conflicts with canonical evidence or a
live read-only check, the canonical evidence or live check wins.

Link to the canonical fact instead of copying detailed values into multiple
files. Use decision-lifecycle labels (`PROPOSED`, `DECIDED`, `SUPERSEDED`)
separately from evidence labels (`VERIFIED`, `INFERENCE`, `UNVERIFIED`) when the
distinction matters. `STALE` is a freshness warning. A decision is not
automatically verified, and verified runtime state is not assumed current.

Update `verify.md` only for new measurements, `decisions.md` only for a real
decision, and the setup log only when execution history will help later
debugging. Keep raw or private experiment output gitignored and summarize
durable results in `verify.md`.
