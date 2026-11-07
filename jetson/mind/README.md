# rover-mind

Stage 1 of Kalman's mind (`docs/decisions.md`, plan in `docs/voice-orchestration.md`): listen on the
rover microphone, wake, record until the speaker stops, transcribe with Whisper (`rover-stt`, name
prompt), ask the LLM on the Mac mini (`rover-brainlink`), speak the reply sentence by sentence with
Supertonic (`rover-tts-st`) on the rover speaker, and journal every step.

Wake: until the `Hey Kalman` detector exists, a POST to the local control port wakes it:

```
curl -X POST http://127.0.0.1:8096/listen     # on the Jetson; a short beep means "speak now"
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
