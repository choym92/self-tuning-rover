#!/usr/bin/env python3
"""rover-mind, stage 1: Kalman listens when called and answers on the rover, no MacBook involved.

  microphone (arecord) -> wake -> record until silence -> Whisper (rover-stt) -> LLM on the Mac mini
  (rover-brainlink) -> Supertonic sentence by sentence (rover-tts-st) -> speaker (aplay), half-duplex

Wake (Paul's choice, 2026-11-07): Silero VAD cuts every spoken phrase out of the microphone stream and
Whisper, given the name as a prompt, transcribes it; a phrase that starts with "Kalman" wakes Kalman, and
any words after the name are taken as the question at once. Phrases without the name are dropped
unrecorded (only counted). POST /listen on the local control port also wakes it. Every turn is written
to a day-file JSONL journal. Runs with host networking so all services are on the Jetson's loopback
(jetson/mind/README.md).
"""
import argparse
import array
import io
import json
import math
import os
import queue
import re
import select
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
import wave
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RATE = 16000
FRAME = 480                      # 30 ms of 16-bit mono
HANGUL = re.compile(r"[가-힣]")
SENTENCE_END = re.compile(r"(?<=[.!?。！？])\s+")
WHISPER_PROMPT = "Kalman is a small robot. Hey Kalman."   # name-only hint measured 6/6 (docs/verify.md)
# Lines Whisper is known to invent from short noise (YouTube-caption endings); seen on the rover 2026-11-07.
INVENTED = re.compile(r"^\W*(thank(s| you)( so much| very much)?( for (watching|listening)\b.*)?|please subscribe.*|"
                      r"subscribe.*|you|bye|\.+)\W*$", re.I)


NAME = re.compile(r"^\W*(?:(?:hey|hi|hello|ok|okay|yo)\W+)?kalman\b\W*", re.I)


# Whisper sometimes repeats its own prompt ("Kalman's a huge robot. Kalman.", 2026-11-07).
ECHO = re.compile(r"\bkalman(?:'s| is)\s+(?:a\s+)?\w*\s*robot\b", re.I)


def split_wake(text):
    """(True, rest) when the phrase starts with the name, optionally after a greeting; rest is what
    followed the name ('' if nothing). The general detector heard Paul's "Kalman" as "common"
    (docs/verify.md); Whisper with the name prompt wrote it right on every real call."""
    if ECHO.search(text or ""):
        return False, ""
    m = NAME.match(text or "")
    return (True, text[m.end():].strip()) if m else (False, "")


# Ends a conversation early, as on Google Assistant and Alexa ("thank you", "stop", "go to sleep").
END = re.compile(r"^\W*(?:(?:ok|okay|alright|all right)\W+)?(?:thank you|thanks|stop|cancel|bye|goodbye|good bye|"
                 r"go to sleep|that'?s all|that is all|never mind|nevermind)\b[\w\s,'.!]*$", re.I)


def is_end(text):
    return bool(END.match(text or "")) and len((text or "").split()) <= 6


def is_speech(text):
    """False for empty text, sound tags only ([BEEP], (noise)) and lines Whisper invents from noise."""
    words = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", text).strip(" .,!?")
    return bool(words) and not INVENTED.match(words)


def rms(frame):
    a = array.array("h", frame)
    return math.sqrt(sum(x * x for x in a) / max(len(a), 1))


def floats(frame):
    return [x / 32768.0 for x in array.array("h", frame)]


class Endpointer:
    """End of the spoken request after a wake. A VAD (Silero through sherpa-onnx; anything with
    accept_waveform / is_speech_detected / empty / pop / reset) decides speech; the request ends when
    the VAD closes a speech segment (its own silence timer), at `max_s`, or with nothing if nobody
    spoke within `start_s`. The audio sent on is everything since the wake, so nothing is clipped."""

    def __init__(self, vad, start_s=4.0, max_s=10.0):
        self.vad = vad
        self.vad.reset()
        self.start_frames = int(start_s * RATE / FRAME)
        self.max_frames = int(max_s * RATE / FRAME)
        self.frames, self.started, self.n = [], False, 0

    def feed(self, frame):
        """Returns (done, pcm or None)."""
        self.n += 1
        self.frames.append(frame)
        self.vad.accept_waveform(floats(frame))
        if self.vad.is_speech_detected():
            self.started = True
        closed = False
        while not self.vad.empty():
            self.vad.pop()
            closed = True
        if not self.started and not closed and self.n >= self.start_frames:
            return True, None
        if closed or (self.started and self.n >= self.max_frames):
            return True, b"".join(self.frames)
        return False, None


def make_vad(model, silence_s=0.6):
    import sherpa_onnx
    cfg = sherpa_onnx.VadModelConfig()
    cfg.silero_vad.model = model
    cfg.silero_vad.threshold = 0.5
    cfg.silero_vad.min_silence_duration = silence_s
    cfg.silero_vad.min_speech_duration = 0.15
    cfg.sample_rate = RATE
    return sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=30)


class SpeechGate:
    """Cuts phrases out of the continuous stream: from a little before the VAD hears speech until it
    closes the segment. Returns the phrase's PCM when it ends, else None. Phrases shorter than
    `min_s` (clicks, coughs) and longer than `max_s` (TV monologue) are dropped."""

    def __init__(self, vad, pre_s=0.4, min_s=0.4, max_s=10.0):
        self.vad = vad
        self.vad.reset()
        self.pre = deque(maxlen=int(pre_s * RATE / FRAME))
        self.min_frames, self.max_frames = int(min_s * RATE / FRAME), int(max_s * RATE / FRAME)
        self.frames = None

    def feed(self, frame):
        self.vad.accept_waveform(floats(frame))
        if self.frames is None:
            self.pre.append(frame)
            if self.vad.is_speech_detected():
                self.frames = list(self.pre)
            return None
        self.frames.append(frame)
        closed = False
        while not self.vad.empty():
            self.vad.pop()
            closed = True
        if closed or len(self.frames) >= self.max_frames:
            pcm, n = b"".join(self.frames), len(self.frames)
            self.frames = None
            self.pre.clear()
            if not closed:
                self.vad.reset()
                return None
            return pcm if n >= self.min_frames else None
        return None


def wav_bytes(pcm, rate=RATE):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def multipart(fields, file_bytes, filename="utterance.wav"):
    boundary = uuid.uuid4().hex
    parts = [(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
             for k, v in fields.items()]
    parts.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
                  "Content-Type: audio/wav\r\n\r\n").encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def sentences(stream, first_clause_words=4):
    """Turn a stream of text pieces into whole sentences as soon as each one ends. The very first
    piece may end at a comma once it has `first_clause_words` words, so the first sound comes sooner."""
    buf, first = "", True
    for piece in stream:
        buf += piece
        if first and "," in buf and len(buf.split(",")[0].split()) >= first_clause_words:
            head, buf = buf.split(",", 1)
            first = False
            yield head.strip() + ","
        parts = SENTENCE_END.split(buf)
        for done in parts[:-1]:
            if done.strip():
                first = False
                yield done.strip()
        buf = parts[-1]
    if buf.strip():
        yield buf.strip()


def sse_text(lines):
    """Content pieces from an OpenAI-style streaming response (one `data: {...}` per line)."""
    for raw in lines:
        line = raw.decode("utf-8", "replace").strip() if isinstance(raw, bytes) else raw.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            return
        try:
            delta = json.loads(data)["choices"][0].get("delta", {})
        except (ValueError, KeyError, IndexError):
            continue
        if delta.get("content"):
            yield delta["content"]


def tone(freq=880.0, seconds=0.12, rate=RATE, volume=0.3):
    n = int(seconds * rate)
    a = array.array("h", (int(volume * 32767 * math.sin(2 * math.pi * freq * i / rate) * min(1, i / 160, (n - i) / 160))
                          for i in range(n)))
    return wav_bytes(a.tobytes(), rate)


class Journal:
    def __init__(self, folder):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)
        self.lock = threading.Lock()

    def write(self, kind, **fields):
        now = datetime.now().astimezone()
        rec = {"ts": now.isoformat(timespec="milliseconds"), "kind": kind, **fields}
        with self.lock, open(os.path.join(self.folder, now.strftime("%Y-%m-%d") + ".jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(json.dumps(rec, ensure_ascii=False), flush=True)


class Mind:
    def __init__(self, args):
        self.a = args
        self.persona = open(args.persona, encoding="utf-8").read().strip()
        self.journal = Journal(args.journal)
        self.wake = threading.Event()
        self.vad = make_vad(args.vad_model)
        self.gate_vad = make_vad(args.vad_model, silence_s=0.4)
        self.counts = {"phrases": 0, "whisper_ms": 0, "wakes": 0, "follow_ups": 0}   # for the TV test
        self.convo_until = 0.0         # while now < this, a phrase needs no name (conversation mode)
        self.state = "starting"
        self.speaking = False
        self.recent = deque(maxlen=int(1.0 * RATE / FRAME))     # pre-roll and noise level
        self.history = deque(maxlen=6)                           # last turns for context

    # --- services -------------------------------------------------------------------------
    def transcribe(self, pcm):
        body, ctype = multipart({"temperature": "0", "language": self.a.language, "response_format": "json",
                                 "prompt": WHISPER_PROMPT}, wav_bytes(pcm))
        req = urllib.request.Request(self.a.stt + "/inference", data=body, headers={"Content-Type": ctype})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read()).get("text", "").strip()

    def reply_stream(self, heard):
        rule = "이번 답은 반드시 한국어로, 반말로 짧게." if HANGUL.search(heard) else "Answer in English."
        messages = [{"role": "system", "content": self.persona + " " + rule}, *self.history, {"role": "user", "content": heard}]
        body = json.dumps({"messages": messages, "max_tokens": 110, "temperature": 0.9, "stream": True,
                           "chat_template_kwargs": {"enable_thinking": False}}).encode()
        req = urllib.request.Request(self.a.llm + "/v1/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=30)
        return resp, sse_text(resp)

    def synthesize(self, text):
        lang = "ko" if HANGUL.search(text) else "en"
        body = json.dumps({"text": text, "lang": lang, "voice": self.a.voice, "steps": self.a.tts_steps,
                           "speed": self.a.tts_speed}).encode()
        req = urllib.request.Request(self.a.tts + "/say", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()

    def play(self, wav=None, path=None):
        cmd = ["aplay", "-q", "-D", self.a.speaker] + ([path] if path else ["-"])
        for _ in range(20):            # the speaker can be busy for a moment (docs/setup-log.md 2026-11-07)
            p = subprocess.run(cmd, input=wav, capture_output=True)
            if p.returncode == 0 or b"busy" not in p.stderr:
                return p.returncode == 0
            time.sleep(0.5)
        return False

    # --- one turn -------------------------------------------------------------------------
    def turn(self, source, frames, called="", question=""):
        """One exchange. With `question` (said in the same breath as the name) Kalman answers at once;
        otherwise it beeps and records the question."""
        self.journal.write("wake", source=source, heard=called)
        if question:
            heard = question
        else:
            # The microphone keeps recording while the beep plays, so the frames queued during the beep
            # (plus a margin for the speaker's own latency) are dropped; otherwise the beep reads as speech.
            # Everything queued so far (the wake phrase's transcription time, then the beep itself) is old.
            self.play(tone())
            time.sleep(0.15)
            self.drain()
            t0 = time.monotonic()
            seg = Endpointer(self.vad)
            pcm = None
            for frame in frames:
                done, pcm = seg.feed(frame)
                if done:
                    break
            if not pcm:
                self.journal.write("heard", text="", ms=round((time.monotonic() - t0) * 1000), note="no speech")
                return
            t1 = time.monotonic()
            try:
                heard = self.transcribe(pcm)
            except Exception as e:
                self.journal.write("error", where="stt", error=str(e))
                return
            self.journal.write("heard", text=heard, lang=self.a.language, seconds=round(len(pcm) / 2 / RATE, 2),
                               ms=round((time.monotonic() - t1) * 1000))
        if not is_speech(heard):
            self.journal.write("ignored", text=heard)
            return
        self.speaking = True
        try:
            t2 = time.monotonic()
            lang = "ko" if HANGUL.search(heard) else "en"
            try:
                resp, stream = self.reply_stream(heard)
            except Exception as e:
                self.journal.write("error", where="llm", error=str(e))
                self.play(path=os.path.join(self.a.voice_dir, f"brain_offline_{lang}.wav"))
                return
            said, first = [], None
            # Synthesis runs one sentence ahead of playback, so sentences follow without a gap.
            ready = queue.Queue(maxsize=2)

            def produce():
                try:
                    for sentence in sentences(stream):
                        ready.put((sentence, self.synthesize(sentence)))
                except Exception as e:
                    ready.put((None, e))
                ready.put(None)

            with resp:
                threading.Thread(target=produce, daemon=True).start()
                while True:
                    item = ready.get()
                    if item is None:
                        break
                    sentence, wav = item
                    if sentence is None:
                        self.journal.write("error", where="tts", error=str(wav))
                        break
                    if first is None:
                        first = round((time.monotonic() - t2) * 1000)
                    self.play(wav)
                    said.append(sentence)
            reply = " ".join(said)
            self.journal.write("reply", text=reply, model=self.a.model_name, first_sound_ms=first,
                               ms=round((time.monotonic() - t2) * 1000))
            self.history.extend([{"role": "user", "content": heard}, {"role": "assistant", "content": reply}])
            self.convo_until = time.monotonic() + 0.3 + self.a.follow_s
        finally:
            time.sleep(0.3)
            self.speaking = False

    # --- audio loop -----------------------------------------------------------------------
    def frames(self):
        p = subprocess.Popen(["arecord", "-q", "-D", self.a.mic, "-f", "S16_LE", "-r", str(RATE), "-c", "1", "-t", "raw"],
                             stdout=subprocess.PIPE, bufsize=0)
        self.mic_fd = p.stdout.fileno()
        need, buf = FRAME * 2, b""
        while True:
            while len(buf) < need:
                chunk = os.read(self.mic_fd, 65536)
                if not chunk:
                    raise RuntimeError("microphone stream ended")
                buf += chunk
            frame, buf = buf[:need], buf[need:]
            yield frame

    def drain(self):
        """Throw away every microphone byte already waiting in the pipe."""
        while select.select([self.mic_fd], [], [], 0)[0]:
            if not os.read(self.mic_fd, 65536):
                return

    def end_conversation(self, reason):
        self.convo_until = 0.0
        self.journal.write("conversation_end", reason=reason)
        self.speaking = True
        self.play(tone(freq=440.0, seconds=0.25, volume=0.2))
        self.speaking = False

    def run(self):
        self.journal.write("start", mic=self.a.mic, speaker=self.a.speaker, llm=self.a.llm, model=self.a.model_name)
        src = self.frames()
        gate = SpeechGate(self.gate_vad)
        self.state = "listening"
        for frame in src:
            if self.speaking:
                continue                       # half-duplex: ignore our own voice
            self.recent.append(frame)
            woke, called, question, source = False, "", "", "button"
            in_convo = time.monotonic() < self.convo_until
            if self.convo_until and not in_convo and gate.frames is None:
                self.end_conversation("quiet")
            phrase = gate.feed(frame)
            if phrase:
                t = time.monotonic()
                try:
                    called = self.transcribe(phrase)
                except Exception as e:
                    self.journal.write("error", where="stt", error=str(e))
                    called = ""
                self.counts["phrases"] += 1
                self.counts["whisper_ms"] += round((time.monotonic() - t) * 1000)
                woke, question = split_wake(called)
                if woke:
                    source = "name"
                    question = question if is_speech(question) else ""
                elif in_convo and is_end(called):
                    self.end_conversation("said: " + called.strip())
                elif in_convo and is_speech(called):
                    woke, source, question = True, "follow-up", called.strip()
                    self.counts["follow_ups"] += 1
            if woke or self.wake.is_set():
                self.wake.clear()
                self.counts["wakes"] += 1
                self.state = "turn"
                try:
                    self.turn(source, src, called if woke else "", question)
                except Exception as e:
                    self.journal.write("error", where="turn", error=str(e))
                self.recent.clear()
                gate = SpeechGate(self.gate_vad)
                self.state = "listening"


def control_server(mind, port):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._json(200, {"state": mind.state, **mind.counts}) if self.path == "/state" else self._json(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/listen":
                return self._json(404, {"error": "not found"})
            if mind.state != "listening":
                return self._json(409, {"result": "busy", "state": mind.state})
            mind.wake.set()
            self._json(200, {"result": "ok"})

    httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mic", default="plughw:0,0")
    ap.add_argument("--speaker", default="plughw:1,0")
    ap.add_argument("--stt", default="http://127.0.0.1:8095")
    ap.add_argument("--llm", default="http://127.0.0.1:8080")
    ap.add_argument("--tts", default="http://127.0.0.1:8093")
    ap.add_argument("--voice", default="M1")
    ap.add_argument("--language", default="en", help="Whisper language for now (English-only model setting)")
    ap.add_argument("--model-name", default="gemma-4-E2B-it-Q4_K_M", help="recorded in the journal")
    ap.add_argument("--persona", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "persona.txt"))
    ap.add_argument("--journal", default="/journal")
    ap.add_argument("--voice-dir", default="/voice")
    ap.add_argument("--follow-s", type=float, default=8.0, help="after a reply, seconds in which no name is needed")
    ap.add_argument("--tts-steps", type=int, default=6, help="Supertonic steps: 10 took 1.3-1.7 s per audio second on the Jetson, 6 about 0.6-0.8")
    ap.add_argument("--tts-speed", type=float, default=1.1)
    ap.add_argument("--port", type=int, default=8096)
    ap.add_argument("--vad-model", default="/models/sherpa/silero_vad.onnx")
    args = ap.parse_args()
    mind = Mind(args)
    control_server(mind, args.port)
    mind.run()


if __name__ == "__main__":
    sys.exit(main())
