# rover-mind

Stage 1 of Kalman's mind (`docs/decisions.md`, plan in `docs/voice-orchestration.md`): listen on the
rover microphone, wake, record until the speaker stops, transcribe with Whisper (`rover-stt`, name
prompt), ask the LLM on the Mac mini (`rover-brainlink`), speak the reply sentence by sentence with
Supertonic (`rover-tts-st`) on the rover speaker, and journal every step.

Wake (Paul's choice 2026-11-07): Silero VAD cuts each spoken phrase out of the stream, Whisper
transcribes it with the name as a prompt, and a phrase that starts with "Kalman" (optionally after
hey / hi / ok) wakes it. "Hey Kalman, what time is it?" is answered at once; "Hey Kalman" alone gets a
beep and then the question. After each reply Kalman keeps listening for 8 s (`--follow-s`)
without the name, as Google Assistant's continued conversation does; "thanks", "stop", "bye", "that's all"
or 8 s of quiet end the conversation with a low tone. Phrases without the name are dropped without being stored; `/state` only
counts them (`phrases`, `whisper_ms`, `wakes`). Known cost: names that sound alike ("Calvin",
"Carmen") also wake it, and Whisper runs on every phrase anyone in the room says (`docs/verify.md`).

```
curl -X POST http://127.0.0.1:8096/listen     # on the Jetson: wake without the name
curl http://127.0.0.1:8096/state
```

Run on the Jetson (host networking, so every service is on loopback; nothing listens on the LAN):

```
docker build -t rover/mind:1 jetson/mind
docker run -d --name rover-mind --network host --device /dev/snd --group-add audio \
  -v /home/paulcho/kalman/journal:/journal -v /home/paulcho/voice:/voice:ro rover/mind:1
```

Needs Whisper's HTTP port on the host: `rover-stt` runs `whisper-server` on `0.0.0.0:8080` inside the
container, published as `127.0.0.1:8095`.

Journal: `/home/paulcho/kalman/journal/YYYY-MM-DD.jsonl`, one event per line (`start`, `wake`,
`heard`, `reply`, `error`), outside the repository. Audio is not kept. The persona is
`persona.txt` (also read by `jetson/voice/talk.py`).
