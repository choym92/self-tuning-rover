# Voice orchestration design

Status: working proposal. Paul chose English-only speech recognition on
2026-09-25. The interaction style and implementation details listed under
"Open decisions" are not decided yet.

## Verified baseline

The current experiment is a transport and STT baseline, not the final robot
voice loop:

```text
Mac microphone -> SSH tunnel -> Jetson PCM bridge -> whisper.cpp base/en
```

On 2026-09-25, Whisper transcribed `Hey Jetson, how's the weather today?`
correctly. The Orin CUDA inference took 0.50 s, and the result arrived 0.55 s
after the final audio upload. The current client captures a fixed eight-second
window. It has no wake-word detector, VAD, router, LLM or robot action.

## Recommended architecture

Start with a thin Python orchestrator and an independent motion-safety layer.
Do not make an agent framework the owner of the robot.

```text
Microphone
  -> audio ring buffer
  -> wake-word detector
  -> VAD / utterance capture
  -> Whisper STT
  -> orchestrator
       |-> stop / cancel
       |-> deterministic robot commands
       |     -> validator
       |     -> safety supervisor
       |     -> navigation goal
       |     -> motor bridge -> ESP32
       `-> general question / LLM / allow-listed tools
```

Keep the audio frontend, Whisper, LLM and robot control replaceable. They may
run as separate processes or containers. Combining images does not remove the
memory consumed by loaded models. On the 8 GB Jetson, serialize heavy GPU work
and give navigation/perception priority over chat.

## What happens after `Hey Jetson`

1. The microphone runs continuously. Only a short, bounded pre-roll remains in
   a RAM ring buffer; raw audio is not stored by default.
2. A lightweight CPU wake-word detector recognizes `Hey Jetson`.
3. The robot acknowledges that it is listening with a short sound or LED.
4. The orchestrator creates an utterance ID and timestamp.
5. VAD captures speech, including pre-roll so the first command word is not
   clipped.
6. Silence ends the utterance. A hard duration limit handles continuous noise
   or a stuck microphone.
7. Whisper `base/en` transcribes the bounded utterance.
8. The orchestrator rejects empty, stale or invalid input and routes the text.
9. `stop` and `cancel` take the deterministic priority path and never wait for
   the LLM.
10. Clear commands such as `go to the kitchen` use a deterministic intent and
    known-destination lookup.
11. General questions and ambiguous language may go to the LLM or an
    allow-listed tool such as weather or robot status.
12. A proposed robot action passes schema, semantic and current-state safety
    validation before navigation sees it.
13. The robot acknowledges an accepted goal, for example `Going to the
    kitchen`.
14. Voice returns to listening while navigation continues, so a new stop or
    cancel request can preempt the mission.
15. Arrival, rejection and failure produce a user-visible response and a
    structured event log.

## Separate state machines

Voice and motion need separate state because the robot must keep listening
while it moves.

```text
Voice:
LISTENING -> WAKE_DETECTED -> CAPTURING -> TRANSCRIBING -> ROUTING
          -> CLARIFYING | DISPATCHING | ANSWERING -> RESPONDING -> LISTENING

Motion:
DISARMED -> READY -> NAVIGATING -> ARRIVED | STOPPED | FAULT
```

Timeouts and component failures return the voice loop to a known state. Motion
faults enter a safe stop and require a fresh command before motion resumes.

## Non-negotiable safety boundary

The LLM may propose a typed high-level action:

```json
{
  "tool": "navigate_to",
  "args": {
    "destination": "kitchen"
  }
}
```

The LLM must not receive direct access to UART, wheel velocities, motor PWM,
PID settings, arbitrary shell commands or safety overrides. A validator and
safety supervisor own motion permission. The motor bridge alone talks to the
ESP32 motor controller.

Before accepting motion, validate at least:

- the destination is a registered waypoint;
- localization and obstacle data are healthy and fresh;
- battery and controller state permit motion;
- the request is not negated, ambiguous, expired or duplicated;
- another active mission has been cancelled or deliberately replaced;
- any required confirmation has been received.

A physical emergency stop and an ESP32-side command watchdog remain independent
of voice, Whisper, the LLM and the Jetson process. Loss of valid control input
must command zero motion. Voice stop is an additional interface, not the only
safety mechanism. A new stop invalidates all older in-flight STT, LLM and
navigation results; an old result must never restart motion.

## Failure cases to design and test

- The first word after the wake phrase is clipped.
- A TV, another person or the robot's own speaker triggers the wake word.
- VAD cuts off a pause or waits forever in continuous noise.
- Whisper hallucinates a command from noise.
- A delayed LLM result arrives after stop or cancel.
- A retry executes the same motion twice.
- The orchestrator, Jetson or network tool fails while moving.
- Weather is unavailable or cannot know the user's location.
- Whisper, LLM and vision exceed shared GPU memory.
- TTS audio feeds back into the microphone.
- Spoken stop is unavailable because the microphone or voice stack failed.

Use request IDs, command expiry, idempotency, bounded queues and structured
event logs. Start TTS in half-duplex mode; AEC can be enabled and tested with
the final microphone and speaker later.

## Implementation order

1. Record a compact English STT baseline with 5-10 phrases covering wake,
   navigation, negation, stop, status and a general question.
2. Define the voice/motion states, typed command schemas and safety invariants.
3. Test routing, rejection, expiry, duplication and cancellation against a fake
   robot API; no motors move.
4. Replace fixed eight-second capture with VAD and end-of-speech detection.
5. Add the `Hey Jetson` detector and pre-roll buffer.
6. Repeat acoustic tests with the final rover microphone, fan, motors, speaker
   and realistic distances. Mac noise tests are not hardware acceptance tests.
7. Connect read-only tools such as weather and robot status.
8. Add the physical stop, ESP32 watchdog, safety supervisor and validated
   navigation goal interface before voice-controlled powered motion.
9. Connect the LLM for general questions and constrained interpretation only
   after the typed tool boundary is tested.
10. Add TTS, first with half-duplex behavior, then test AEC if needed.

## Open decisions

Discuss and decide these one at a time before implementation:

1. Interaction: `Hey Jetson` -> acknowledgement -> command, or allow one-breath
   `Hey Jetson, go to the kitchen` from the first version? The recommendation
   for version 1 is the explicit acknowledgement flow.
2. Acknowledgement: sound, LED, spoken phrase, or a combination?
3. Which commands require confirmation before execution?
4. While navigating, is bare `stop` accepted without the wake phrase?
5. What should happen when a command is ambiguous or the destination is
   unknown?
6. Which English accent, distance and noise conditions define acceptance?
7. What transcript and event data may be retained, and for how long?
8. What measurable stopping deadline and distance must the motor watchdog meet?
