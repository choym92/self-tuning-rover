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
or 8 s of quiet end the conversation with a low tone.

Barge-in (first version, no echo canceller): while Kalman speaks the microphone keeps listening; each
phrase is transcribed and, if it starts with "Kalman", "stop", "wait"... and is not mostly the words
Kalman is saying (his own voice coming back), playback stops and the rest of the reply is dropped.
"Kalman, <question>" is answered next; "stop" just stops. A proper echo canceller needs the microphone
and speaker on one clock (the audio board's own microphones or a mic array with AEC). Phrases without the name are dropped without being stored; `/state` only
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

Journal: `/home/paulcho/kalman/journal/YYYY-MM-DD.jsonl`, one event per line, outside the repository.
Audio is not kept.

Prompt (assembled for every reply, shown in the console's Mind view under "What Gemma receives"):
identity + style + rules (editable, `/home/paulcho/kalman/config/*.md`, seeded from `prompt/*.md` here,
which `jetson/voice/talk.py` also reads) + a "Right now" line filled in each time (time, real battery
voltage from rover-control, e-stop, whether a conversation is going on) + the language rule (+ the
"you were cut off" rule after an interruption) + recent history + the new words. Settings
(`settings.json`: follow-up seconds, reply length, temperature, history, voice speed and steps,
barge-in ratio and hold) are edited in the same view and apply from the next reply. The console reaches
this control port through the `rover` network gateway (`--hosts 127.0.0.1 172.18.0.1`); it changes
words and voice settings only, never motion.

Run command now also mounts `-v /home/paulcho/kalman/config:/config`.

Sessions (`memory.py`): a session (`s20261107-185501`) opens when Kalman is called with none open and
closes after `session_gap_min` (30) quiet minutes, so several conversations can share one. Every journal
event in it carries the id; the prompt carries only the current session's turns. When a session closes,
a background worker asks the model for a short `session_summary` (prompt `prompt/summary.md`); today's
earlier summaries go into the prompt as "Earlier today". When a day is over, its summaries become one
`day_summary` (`prompt/day.md`). Summaries missed while the Mac mini was off are made later; a session
left open by a restart is closed and summarised. Nothing is deleted. To change the summary instructions,
copy `summary.md` or `day.md` into `/home/paulcho/kalman/config/` and edit the copy.

Language: Whisper detects the language (`--language auto`); Korean questions get Korean answers and the
Korean voice. "칼만" written in Hangul wakes Kalman; 고마워, 그만, 잘 자 and similar end a conversation.
Single short Korean words are often misheard (`docs/verify.md`).

