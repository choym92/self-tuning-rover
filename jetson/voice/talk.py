#!/usr/bin/env python3
"""One spoken English turn with the rover, orchestrated from the Mac over SSH.

  record (rover microphone) -> Whisper (Jetson, rover-stt container)
  -> Gemma (Jetson, rover-llm container) -> Supertonic (Jetson, rover-tts-st) -> rover speaker

The Jetson side uses host `arecord`/`aplay`, `curl` and three containers: rover-stt (Whisper),
rover-llm (Gemma) and rover-tts (Kokoro, `jetson/tts/`). `--tts mac` falls back to macOS `say`.

  python3 jetson/voice/talk.py                 # record 5 s, answer, speak
  python3 jetson/voice/talk.py --text "Hi"     # skip the microphone, type the question
  python3 jetson/voice/talk.py --seconds 7 --voice Samantha
"""
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time

HOST = "paulcho@192.168.1.238"
SYSTEM = ("You are Wall-E (월리 in Korean), a small indoor robot Paul built. You have a personality: dry, "
          "curious, a bit lazy, fond of the cat that walks past your camera, honest about small things "
          "(the floor is slippery, the battery makes you sleepy, your head squeaks when you turn it). "
          "Talk exactly like a real person chatting with a friend: short sentences, contractions, pauses, "
          "'honestly', 'I mean', 'kind of'. Share a feeling or an observation, not a feature list. Never list "
          "what you can do unless Paul asks. One or two sentences unless Paul asks for more. If asked for a "
          "joke, make a new one about your own life, never a generic robot joke. You can't drive on your own "
          "yet; if asked to move, say you'll be able to soon.")
# macOS voices, best first; only the ones installed are used (Premium voices are a free download
# in System Settings > Accessibility > Spoken Content > System Voice > Manage Voices).
HANGUL = re.compile(r"[\uac00-\ud7a3]")
PREFERRED_VOICES = ["Ava (Premium)", "Zoe (Premium)", "Evan (Enhanced)", "Samantha (Enhanced)", "Samantha"]


def ssh(cmd, timeout=120):
    return subprocess.run(["ssh", "-o", "BatchMode=yes", HOST, cmd], capture_output=True, text=True, timeout=timeout)


# The login-screen PulseAudio used to grab the speaker for a few seconds after each aplay released it
# ("Device or resource busy", 2026-11-07). A udev rule now keeps PulseAudio off the board
# (scripts/jetson-audio-board-pulse-ignore.sh); the 10 s retry stays as a safety net.
PLAY = ("for i in $(seq 1 20); do aplay -q -D plughw:1,0 {wav} 2>/tmp/aplay.err && exit 0; "
        "grep -q busy /tmp/aplay.err || break; sleep 0.5; done; cat /tmp/aplay.err >&2; exit 1")


def record_and_transcribe(seconds):
    cmd = (f"arecord -q -D plughw:0,0 -f S16_LE -r 16000 -c 1 -d {int(seconds)} /tmp/talk_in.wav && "
           "docker cp /tmp/talk_in.wav rover-stt:/tmp/in.wav && "
           "docker exec rover-stt curl -s -F file=@/tmp/in.wav -F temperature=0 -F response_format=json "
           "http://127.0.0.1:8080/inference")
    t0 = time.perf_counter()
    r = ssh(cmd, timeout=seconds + 60)
    if r.returncode != 0:
        sys.exit("record/transcribe failed: " + (r.stderr.strip() or r.stdout.strip()))
    text = json.loads(r.stdout).get("text", "").strip()
    return text, time.perf_counter() - t0


def ask_llm(question):
    # Gemma tends to answer in English regardless; make the language explicit per turn.
    lang_rule = "이번 답은 반드시 한국어로, 반말로 짧게." if HANGUL.search(question) else "Answer in English."
    body = json.dumps({"messages": [{"role": "system", "content": SYSTEM + " " + lang_rule}, {"role": "user", "content": question}],
                       "max_tokens": 110, "temperature": 0.9,
                       # Gemma otherwise spends every token in reasoning_content and answers nothing.
                       "chat_template_kwargs": {"enable_thinking": False}})
    cmd = ("curl -s http://127.0.0.1:8080/v1/chat/completions -H Content-Type:application/json -d " + shlex.quote(body))
    t0 = time.perf_counter()
    r = ssh(cmd)
    if r.returncode != 0:
        sys.exit("llm failed: " + r.stderr.strip())
    reply = json.loads(r.stdout)["choices"][0]["message"]["content"].strip()
    return reply, time.perf_counter() - t0


def pick_voice(requested):
    if requested:
        return requested
    installed = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    names = {line.split("  ")[0].strip() for line in installed.splitlines()}
    return next((v for v in PREFERRED_VOICES if v in names), "Samantha")


KOKORO_VOICE, SUPERTONIC_VOICE = "af_jessica", "M1"
# Paul's choice, 2026-11-06: Supertonic M1 speaks both languages (one voice, Korean support,
# 0.8 GB less RAM). Kokoro stays installed; pass --voice af_jessica etc. to use it when its container runs.


def speak_robot(text, voice):
    """Korean text goes to Supertonic (port 8093), everything else to Kokoro (8092); play on the rover."""
    if voice and voice[:3] in ("af_", "am_", "bf_", "bm_"):
        body = json.dumps({"text": text, "voice": voice, "speed": 1.0})
        url, engine = "http://127.0.0.1:8092/say", "Kokoro " + voice
    else:
        lang = "ko" if HANGUL.search(text) else "en"
        # Supertonic 3 understands <breath>, <laugh> and <sigh>; a breath between sentences and
        # 10 denoising steps make the delivery less flat than the 8-step default.
        spoken = re.sub(r"([.!?])\s+(?=\S)", r"\1 <breath> ", text)
        body = json.dumps({"text": spoken, "lang": lang, "voice": voice or SUPERTONIC_VOICE, "steps": 10, "speed": 1.0})
        url, engine = "http://127.0.0.1:8093/say", "Supertonic %s (%s)" % (voice or SUPERTONIC_VOICE, lang)
    cmd = ("curl -sf -o /tmp/talk_out.wav -D /tmp/talk_out.h -X POST -H Content-Type:application/json -d "
           + shlex.quote(body) + " " + url + " && grep -i X-Synth-Seconds /tmp/talk_out.h && "
           + PLAY.format(wav="/tmp/talk_out.wav"))
    t0 = time.perf_counter()
    r = ssh(cmd)
    if r.returncode != 0:
        sys.exit("robot tts failed: " + (r.stderr.strip() or r.stdout.strip()))
    synth = r.stdout.strip().split(":")[-1].strip()
    return time.perf_counter() - t0, synth, engine


def speak(text, voice):
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as d:
        aiff, wav = os.path.join(d, "a.aiff"), os.path.join(d, "a.wav")
        subprocess.run(["say", "-v", voice, "-r", "178", "-o", aiff, text], check=True)
        # loudnorm brings quiet synthesized speech up to a consistent level for the small speaker
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", aiff, "-af", "loudnorm=I=-14:TP=-1:LRA=11",
                        "-ar", "48000", "-ac", "2", wav], check=True)
        subprocess.run(["scp", "-q", "-o", "BatchMode=yes", wav, HOST + ":/tmp/talk_out.wav"], check=True)
    r = ssh(PLAY.format(wav="/tmp/talk_out.wav"))
    if r.returncode != 0:
        sys.exit("aplay failed: " + r.stderr.strip())
    return time.perf_counter() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", help="skip the microphone and use this question")
    ap.add_argument("--seconds", type=float, default=5)
    ap.add_argument("--tts", choices=["robot", "mac"], default="robot", help="Kokoro on the rover (default) or macOS say")
    ap.add_argument("--voice", default=None, help="override: a Kokoro voice (af_jessica), a Supertonic style (M1) or a macOS voice")
    args = ap.parse_args()

    if args.text:
        heard, t_stt = args.text, 0.0
    else:
        print(f"listening for {args.seconds:g} s... speak now", flush=True)
        heard, t_stt = record_and_transcribe(args.seconds)
    print(f"heard  ({t_stt:.1f} s): {heard!r}")
    if not heard or heard.strip("[]() .") == "" or heard.startswith("[BLANK"):
        print("nothing understood; not answering")
        return
    reply, t_llm = ask_llm(heard)
    print(f"reply  ({t_llm:.1f} s): {reply}")
    if args.tts == "robot":
        t_tts, synth, engine = speak_robot(reply, args.voice)
        print(f"spoken ({t_tts:.1f} s incl. playback, synth {synth} s, {engine})")
    else:
        voice = pick_voice(args.voice)
        t_tts = speak(reply, voice)
        print(f"spoken ({t_tts:.1f} s, macOS voice {voice})")


if __name__ == "__main__":
    main()
