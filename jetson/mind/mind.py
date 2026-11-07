#!/usr/bin/env python3
"""rover-mind, stage 1: Kalman listens when called and answers on the rover, no MacBook involved.

  microphone (arecord) -> wake -> record until silence -> Whisper (rover-stt) -> LLM on the Mac mini
  (rover-brainlink) -> Supertonic sentence by sentence (rover-tts-st) -> speaker (aplay), half-duplex

Every step is written to a day-file JSONL journal. The wake detector is pluggable; until the
"Hey Kalman" model exists, POST /listen on the local control port wakes Kalman (push to talk).
Runs with host networking so all services are on the Jetson's loopback (jetson/mind/README.md).
"""
import argparse
import array
import io
import json
import math
import os
import re
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


def rms(frame):
    a = array.array("h", frame)
    return math.sqrt(sum(x * x for x in a) / max(len(a), 1))


class Segmenter:
    """Energy end-of-speech detector. Feed 30 ms frames after the wake; it returns the utterance once
    speech has started and then stayed quiet for `silence_s`, or at `max_s`, or None if nobody spoke
    within `start_s`. The threshold follows the room: `factor` times the quiet level before the wake."""

    def __init__(self, noise_rms, factor=2.0, floor=300.0, silence_s=0.7, start_s=4.0, max_s=8.0):
        self.threshold = max(floor, noise_rms * factor)
        self.silence_frames = int(silence_s * RATE / FRAME)
        self.start_frames = int(start_s * RATE / FRAME)
        self.max_frames = int(max_s * RATE / FRAME)
        self.frames, self.quiet, self.started, self.n = [], 0, False, 0

    def feed(self, frame):
        """Returns (done, pcm or None)."""
        self.n += 1
        loud = rms(frame) >= self.threshold
        self.frames.append(frame)
        if loud:
            self.started, self.quiet = True, 0
        elif self.started:
            self.quiet += 1
        if not self.started and self.n >= self.start_frames:
            return True, None
        if self.started and (self.quiet >= self.silence_frames or self.n >= self.max_frames):
            return True, b"".join(self.frames)
        return False, None


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


def sentences(stream):
    """Turn a stream of text pieces into whole sentences as soon as each one ends."""
    buf = ""
    for piece in stream:
        buf += piece
        parts = SENTENCE_END.split(buf)
        for done in parts[:-1]:
            if done.strip():
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
        body = json.dumps({"text": text, "lang": lang, "voice": self.a.voice, "steps": 10, "speed": 1.0}).encode()
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
    def turn(self, source, frames):
        self.speaking = True
        self.play(tone())
        self.speaking = False
        t0 = time.monotonic()
        self.journal.write("wake", source=source)
        noise = sorted(rms(f) for f in self.recent)[len(self.recent) // 2] if self.recent else 500.0
        seg = Segmenter(noise)
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
        if not heard or heard.strip("[]() .").lower() in ("", "blank_audio") or heard.startswith("[BLANK"):
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
            with resp:
                for sentence in sentences(stream):
                    wav = self.synthesize(sentence)
                    if first is None:
                        first = round((time.monotonic() - t2) * 1000)
                    self.play(wav)
                    said.append(sentence)
            reply = " ".join(said)
            self.journal.write("reply", text=reply, model=self.a.model_name, first_sound_ms=first,
                               ms=round((time.monotonic() - t2) * 1000))
            self.history.extend([{"role": "user", "content": heard}, {"role": "assistant", "content": reply}])
        finally:
            time.sleep(0.3)
            self.speaking = False

    # --- audio loop -----------------------------------------------------------------------
    def frames(self):
        p = subprocess.Popen(["arecord", "-q", "-D", self.a.mic, "-f", "S16_LE", "-r", str(RATE), "-c", "1", "-t", "raw"],
                             stdout=subprocess.PIPE)
        need = FRAME * 2
        while True:
            chunk = p.stdout.read(need)
            if len(chunk) < need:
                raise RuntimeError("microphone stream ended")
            yield chunk

    def run(self):
        self.journal.write("start", mic=self.a.mic, speaker=self.a.speaker, llm=self.a.llm, model=self.a.model_name)
        src = self.frames()
        self.state = "listening"
        for frame in src:
            if self.speaking:
                continue                       # half-duplex: ignore our own voice
            self.recent.append(frame)
            if self.wake.is_set():
                self.wake.clear()
                self.state = "turn"
                try:
                    self.turn("button", src)
                except Exception as e:
                    self.journal.write("error", where="turn", error=str(e))
                self.recent.clear()
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
            self._json(200, {"state": mind.state}) if self.path == "/state" else self._json(404, {"error": "not found"})

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
    ap.add_argument("--port", type=int, default=8096)
    args = ap.parse_args()
    mind = Mind(args)
    control_server(mind, args.port)
    mind.run()


if __name__ == "__main__":
    sys.exit(main())
