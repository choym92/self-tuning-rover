#!/usr/bin/env python3
"""One spoken English turn with the rover, orchestrated from the Mac over SSH.

  record (rover microphone) -> Whisper (Jetson, rover-stt container)
  -> Gemma (Jetson, rover-llm container) -> macOS `say` -> rover speaker

The Jetson side uses host `arecord`/`aplay`, `curl` and three containers: rover-stt (Whisper),
rover-llm (Gemma) and rover-tts (Kokoro, `jetson/tts/`). `--tts mac` falls back to macOS `say`.

  python3 jetson/voice/talk.py                 # record 5 s, answer, speak
  python3 jetson/voice/talk.py --text "Hi"     # skip the microphone, type the question
  python3 jetson/voice/talk.py --seconds 7 --voice Samantha
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time

HOST = "paulcho@192.168.1.238"
SYSTEM = ("You are Rover, a small indoor robot that Paul built on a Jetson Orin Nano. "
          "Talk like a relaxed, warm friend: plain spoken English, contractions, one or two short sentences, "
          "no lists, no formal phrasing, no exclamation marks in a row. "
          "You can see with a camera and hear with a microphone, but you cannot drive on your own yet; "
          "if asked to move, say you'll be able to soon.")
# macOS voices, best first; only the ones installed are used (Premium voices are a free download
# in System Settings > Accessibility > Spoken Content > System Voice > Manage Voices).
PREFERRED_VOICES = ["Ava (Premium)", "Zoe (Premium)", "Evan (Enhanced)", "Samantha (Enhanced)", "Samantha"]


def ssh(cmd, timeout=120):
    return subprocess.run(["ssh", "-o", "BatchMode=yes", HOST, cmd], capture_output=True, text=True, timeout=timeout)


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
    body = json.dumps({"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}],
                       "max_tokens": 80, "temperature": 0.7,
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


def speak_robot(text, voice):
    """Kokoro on the Jetson: POST the text, play the returned WAV on the rover speaker."""
    body = json.dumps({"text": text, "voice": voice or "af_heart", "speed": 1.0})
    cmd = ("curl -sf -o /tmp/talk_out.wav -D /tmp/talk_out.h -X POST -H Content-Type:application/json -d "
           + shlex.quote(body) + " http://127.0.0.1:8092/say && grep -i X-Synth-Seconds /tmp/talk_out.h"
           " && aplay -q -D plughw:1,0 /tmp/talk_out.wav")
    t0 = time.perf_counter()
    r = ssh(cmd)
    if r.returncode != 0:
        sys.exit("robot tts failed: " + (r.stderr.strip() or r.stdout.strip()))
    synth = r.stdout.strip().split(":")[-1].strip()
    return time.perf_counter() - t0, synth


def speak(text, voice):
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as d:
        aiff, wav = os.path.join(d, "a.aiff"), os.path.join(d, "a.wav")
        subprocess.run(["say", "-v", voice, "-r", "178", "-o", aiff, text], check=True)
        # loudnorm brings quiet synthesized speech up to a consistent level for the small speaker
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", aiff, "-af", "loudnorm=I=-14:TP=-1:LRA=11",
                        "-ar", "48000", "-ac", "2", wav], check=True)
        subprocess.run(["scp", "-q", "-o", "BatchMode=yes", wav, HOST + ":/tmp/talk_out.wav"], check=True)
    r = ssh("aplay -q -D plughw:1,0 /tmp/talk_out.wav")
    if r.returncode != 0:
        sys.exit("aplay failed: " + r.stderr.strip())
    return time.perf_counter() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", help="skip the microphone and use this question")
    ap.add_argument("--seconds", type=float, default=5)
    ap.add_argument("--tts", choices=["robot", "mac"], default="robot", help="Kokoro on the rover (default) or macOS say")
    ap.add_argument("--voice", default=None, help="Kokoro voice such as af_heart, am_michael; or a macOS voice with --tts mac")
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
        t_tts, synth = speak_robot(reply, args.voice)
        print(f"spoken ({t_tts:.1f} s incl. playback, synth {synth} s, Kokoro {args.voice or 'af_heart'})")
    else:
        voice = pick_voice(args.voice)
        t_tts = speak(reply, voice)
        print(f"spoken ({t_tts:.1f} s, macOS voice {voice})")


if __name__ == "__main__":
    main()
