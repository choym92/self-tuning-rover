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


# Barge-in (stage 1, no echo canceller): while Kalman speaks the microphone keeps listening, every phrase
# is transcribed, and a phrase that starts like this AND is not just Kalman's own voice coming back stops
# him. The echo test compares words with what he is saying (the transcript-matching fallback voice
# platforms use; a real canceller needs the microphone and speaker on one clock, which ours are not).
INTERRUPT = re.compile(r"^\W*(?:(?:hey|ok|okay)\W+)?(?:kalman|stop|wait|hold on|enough|be quiet|quiet|shut up)\b", re.I)


def words(text):
    return re.findall(r"[a-z\uac00-\ud7a3']+", (text or "").lower())


def is_echo(heard, spoken, share=0.6):
    """True when most of the heard words are words Kalman is saying right now."""
    h, s = words(heard), set(words(spoken))
    return not h or sum(w in s for w in h) / len(h) >= share


def barge_in(heard, spoken, min_words=3):
    """(True, rest) when `heard` is Paul cutting in: it is not mostly Kalman's own words, and it either
    starts with the name or a stop word, or is a real sentence of `min_words`+ words (Paul just talking
    over him, as voice agents allow). rest is the new request ('' for "stop", "Kalman" alone...)."""
    if not is_speech(heard) or is_echo(heard, spoken):
        return False, ""
    if INTERRUPT.match(heard or ""):
        woke, rest = split_wake(heard)
        keep = woke and is_speech(rest) and not INTERRUPT.match(rest) and not is_end(rest)   # "Kalman, stop." only stops
        return True, (rest if keep else "")
    if len(words(heard)) >= min_words:
        return True, heard.strip()
    return False, ""


class DoubleTalk:
    """Paul talking over Kalman, by sound alone (a Geigel-style double-talk test, no echo canceller):
    the microphone level is compared with the loudest playback level of the last `lag_s` (so speaker and
    pipe latency do not matter) times the speaker-to-mic gain, which is learned while Kalman speaks alone.
    Louder than `ratio` x that for `hold_s` means someone else is making sound."""

    def __init__(self, ratio=2.0, hold_s=0.2, lag_s=0.5, min_level=900.0, gain=None, warm_s=0.3):
        self.ratio, self.min_level = ratio, min_level
        self.warm = int(warm_s * RATE / FRAME)   # playback start: the echo has not reached the mic yet
        self.hold = int(hold_s * RATE / FRAME)
        self.lag = int(lag_s * RATE / FRAME)
        self.gain = gain                       # echo level per unit of playback level; None until learned
        self.reset([])

    def reset(self, play_env):
        self.env, self.i, self.run = play_env, 0, 0

    def feed(self, mic_level):
        """One microphone frame level; returns True when Paul is judged to be making sound."""
        window = self.env[max(0, self.i - self.lag):self.i + 1]
        self.i += 1
        if self.i <= self.warm:
            return False
        ref = max(window) if window else 0.0
        expected = (self.gain or 0.0) * ref
        loud = self.gain is not None and mic_level > max(self.ratio * expected, self.min_level)
        self.run = self.run + 1 if loud else 0
        if not loud and ref > 500 and mic_level > 0:      # learn the echo gain while Kalman talks alone
            g = mic_level / ref
            self.gain = g if self.gain is None else 0.95 * self.gain + 0.05 * min(g, 4 * self.gain)
        return self.run >= self.hold


def play_envelope(wav):
    """RMS of the playback per 30 ms, at the microphone's frame rate."""
    with wave.open(io.BytesIO(wav)) as w:
        rate, ch = w.getframerate(), w.getnchannels()
        a = array.array("h", w.readframes(w.getnframes()))
    if ch > 1:
        a = a[::ch]
    step = max(1, int(rate * FRAME / RATE))
    return [math.sqrt(sum(x * x for x in a[i:i + step]) / step) for i in range(0, len(a) - step + 1, step)]


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
        self.barge_vad = make_vad(args.vad_model, silence_s=0.3)
        self.counts = {"phrases": 0, "whisper_ms": 0, "wakes": 0, "follow_ups": 0, "interrupts": 0, "echoes": 0}
        self.dtd = DoubleTalk()                # keeps the learned speaker-to-mic gain across replies
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

    def reply_stream(self, heard, interrupted=False):
        rule = "이번 답은 반드시 한국어로, 반말로 짧게." if HANGUL.search(heard) else "Answer in English."
        if interrupted:
            rule += (" Paul just cut you off mid-answer. Drop what you were saying: do not finish it, repeat it or"
                     " go back to it. Reply only to his new words, briefly.")
        messages = [{"role": "system", "content": self.persona + " " + rule}, *self.history, {"role": "user", "content": heard}]
        body = json.dumps({"messages": messages, "max_tokens": 110, "temperature": 0.9, "stream": True,
                           "chat_template_kwargs": {"enable_thinking": False}}).encode()
        req = urllib.request.Request(self.a.llm + "/v1/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=30)
        return resp, sse_text(resp)

    def synthesize(self, text):
        """Kalman's voice from the Mac mini (about 5x faster, docs/verify.md); the Jetson's own Supertonic
        at fewer steps if the Mac mini does not answer."""
        lang = "ko" if HANGUL.search(text) else "en"
        last = None
        for url, steps, timeout in ((self.a.tts, self.a.tts_steps, 10), (self.a.tts_fallback, self.a.fallback_steps, 60)):
            if not url:
                continue
            body = json.dumps({"text": text, "lang": lang, "voice": self.a.voice, "steps": steps, "speed": self.a.tts_speed}).encode()
            try:
                with urllib.request.urlopen(urllib.request.Request(url + "/say", data=body, headers={"Content-Type": "application/json"}),
                                            timeout=timeout) as r:
                    return r.read()
            except Exception as e:
                last = e
                self.journal.write("error", where="tts", url=url, error=str(e))
        raise RuntimeError("no voice: %s" % last)

    def play(self, wav=None, path=None):
        cmd = ["aplay", "-q", "-D", self.a.speaker] + ([path] if path else ["-"])
        for _ in range(20):            # the speaker can be busy for a moment (docs/setup-log.md 2026-11-07)
            p = subprocess.run(cmd, input=wav, capture_output=True)
            if p.returncode == 0 or b"busy" not in p.stderr:
                return p.returncode == 0
            time.sleep(0.5)
        return False

    def play_listening(self, wav, frames, gate, spoken):
        """Play `wav` while still listening. Returns the interrupting phrase if Paul's words cut in,
        ("sound", pre-roll frames) if a sound louder than Kalman's own echo did, else None."""
        env = play_envelope(wav)
        pre = deque(maxlen=int(0.6 * RATE / FRAME))
        for _ in range(20):
            self.drain()                      # line the microphone up with the start of playback
            self.dtd.reset(env)
            p = subprocess.Popen(["aplay", "-q", "-D", self.a.speaker, "-"], stdin=subprocess.PIPE, stderr=subprocess.PIPE)

            def feed():
                try:
                    p.stdin.write(wav)
                    p.stdin.close()
                except (BrokenPipeError, ValueError):
                    pass
            threading.Thread(target=feed, daemon=True).start()
            while p.poll() is None:
                frame = next(frames)
                pre.append(frame)
                if self.dtd.feed(rms(frame)):
                    p.kill()
                    p.wait()
                    self.journal.write("while_speaking", sound=True, gain=round(self.dtd.gain or 0, 3))
                    return ("sound", list(pre))
                phrase = gate.feed(frame)
                if not phrase:
                    continue
                try:
                    heard = self.transcribe(phrase)
                except Exception:
                    continue
                cut, _ = barge_in(heard, spoken)
                self.journal.write("while_speaking", text=heard, echo=is_echo(heard, spoken), cut=cut,
                                   seconds=round(len(phrase) / 2 / RATE, 2))
                if cut:
                    p.kill()
                    p.wait()
                    return heard
                if INTERRUPT.match(heard or ""):
                    self.counts["echoes"] += 1
            if p.returncode == 0 or b"busy" not in (p.stderr.read() or b""):
                return None
            time.sleep(0.5)
        return None

    # --- one turn -------------------------------------------------------------------------
    def turn(self, source, frames, called="", question="", depth=0, interrupted=False):
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
                resp, stream = self.reply_stream(heard, interrupted)
            except Exception as e:
                self.journal.write("error", where="llm", error=str(e))
                self.play(path=os.path.join(self.a.voice_dir, f"brain_offline_{lang}.wav"))
                return
            said, first, cut = [], None, None
            # Synthesis runs one sentence ahead of playback, so sentences follow without a gap.
            ready, stop = queue.Queue(maxsize=2), threading.Event()

            def produce():
                try:
                    for sentence in sentences(stream):
                        if stop.is_set():
                            break
                        ready.put((sentence, self.synthesize(sentence)))
                except Exception as e:
                    ready.put((None, e))
                ready.put(None)

            bgate = SpeechGate(self.barge_vad, min_s=0.3)
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
                    cut = self.play_listening(wav, frames, bgate, " ".join(said + [sentence]))
                    said.append(sentence)
                    if cut:
                        stop.set()
                        break
            reply = " ".join(said) + (" [interrupted]" if cut else "")
            self.journal.write("reply", text=reply, model=self.a.model_name, first_sound_ms=first,
                               ms=round((time.monotonic() - t2) * 1000))
            # An interrupted answer stays in the history only as a stub, so the model does not pick it up again.
            kept = "(I started answering but Paul cut me off.)" if cut else reply
            self.history.extend([{"role": "user", "content": heard}, {"role": "assistant", "content": kept}])
            self.convo_until = time.monotonic() + 0.3 + self.a.follow_s
            if cut and isinstance(cut, tuple):           # a sound: listen to what Paul is saying, from just before it
                self.counts["interrupts"] += 1
                seg = Endpointer(self.vad, start_s=3.0)
                pcm = None
                for f in cut[1]:
                    done, pcm = seg.feed(f)
                if not pcm:
                    for f in frames:
                        done, pcm = seg.feed(f)
                        if done:
                            break
                said_now = ""
                if pcm:
                    try:
                        said_now = self.transcribe(pcm)
                    except Exception as e:
                        self.journal.write("error", where="stt", error=str(e))
                self.journal.write("interrupted", by="sound", heard=said_now)
                woke, rest = split_wake(said_now)
                question = rest if woke else said_now
                if depth < 3 and is_speech(question) and not is_end(question) and not INTERRUPT.match(question):
                    self.speaking = False
                    self.turn("interrupt", frames, called=said_now, question=question, depth=depth + 1, interrupted=True)
            elif cut:
                self.counts["interrupts"] += 1
                self.journal.write("interrupted", by=cut)
                _, rest = barge_in(cut, "")
                woke, _ = split_wake(cut)
                if depth < 3 and (rest or woke):         # "Kalman, ..." or a sentence gets an answer; "stop" just stops
                    self.speaking = False
                    self.turn("interrupt", frames, called=cut, question=rest, depth=depth + 1, interrupted=True)
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
    ap.add_argument("--tts", default="http://127.0.0.1:8097", help="Supertonic on the Mac mini through rover-brainlink")
    ap.add_argument("--tts-fallback", default="http://127.0.0.1:8093", help="the Jetson's own Supertonic (rover-tts-st)")
    ap.add_argument("--voice", default="M1")
    ap.add_argument("--language", default="en", help="Whisper language for now (English-only model setting)")
    ap.add_argument("--model-name", default="gemma-4-E2B-it-Q4_K_M", help="recorded in the journal")
    ap.add_argument("--persona", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "persona.txt"))
    ap.add_argument("--journal", default="/journal")
    ap.add_argument("--voice-dir", default="/voice")
    ap.add_argument("--follow-s", type=float, default=8.0, help="after a reply, seconds in which no name is needed")
    ap.add_argument("--tts-steps", type=int, default=10, help="Mac mini: 0.27-0.34 s per audio second at 10 steps")
    ap.add_argument("--fallback-steps", type=int, default=6, help="Jetson: 10 steps took 1.3-1.7 s per audio second, 6 about 0.6-0.8")
    ap.add_argument("--tts-speed", type=float, default=1.1)
    ap.add_argument("--port", type=int, default=8096)
    ap.add_argument("--vad-model", default="/models/sherpa/silero_vad.onnx")
    args = ap.parse_args()
    mind = Mind(args)
    control_server(mind, args.port)
    mind.run()


if __name__ == "__main__":
    sys.exit(main())
