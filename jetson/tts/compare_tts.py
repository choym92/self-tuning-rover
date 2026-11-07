#!/usr/bin/env python3
"""Synthesize the same sentences with two on-robot TTS servers and report speed, loudness and
audio length. Runs on the Jetson host with the standard library only.

    python3 compare_tts.py            # measure, write /tmp/cmp_<engine>_<lang>.wav
    python3 compare_tts.py --play     # ... and play each clip on the rover speaker
"""
import argparse
import array
import io
import json
import subprocess
import time
import urllib.request
import wave

SENTENCES = {
    "en": "Honestly, I'm pretty happy just hanging out here. The floor's a bit slippery, but the cat keeps me company.",
    "ko": "솔직히 말하면 여기서 그냥 있는 게 꽤 좋아. 바닥이 좀 미끄럽긴 한데, 고양이가 옆에 있어 주거든.",
}
ENGINES = {
    "supertonic": lambda text, lang: ("http://127.0.0.1:8093/say",
                                      {"text": text, "lang": lang, "voice": "M1", "steps": 8, "speed": 1.0}),
    "audio8": lambda text, lang: ("http://127.0.0.1:8094/api/tts",
                                  {"text": text, "voice_name": "default", "max_new_tokens": 1024, "seed": 42}),
}


def synth(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as r:
        data = r.read()
    return data, time.perf_counter() - t0


def normalise(data, target=0.89):
    """Peak-normalise 16-bit PCM so both engines play at the same level; returns (wav bytes, rate, seconds, peak)."""
    with wave.open(io.BytesIO(data)) as w:
        if w.getsampwidth() != 2:
            raise SystemExit("expected 16-bit PCM, got %d bytes/sample" % w.getsampwidth())
        rate, ch, frames = w.getframerate(), w.getnchannels(), w.readframes(w.getnframes())
    pcm = array.array("h", frames)
    peak = max(1, max(abs(min(pcm)), max(pcm)))
    gain = target * 32767 / peak
    out = array.array("h", (int(max(-32768, min(32767, s * gain))) for s in pcm))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(rate); w.writeframes(out.tobytes())
    return buf.getvalue(), rate, len(pcm) / ch / rate, peak / 32767


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--play", action="store_true")
    ap.add_argument("--engines", default="supertonic,audio8")
    args = ap.parse_args()
    print("engine      lang  audio_s  synth_s  compute/audio  rate   raw_peak")
    for engine in args.engines.split(","):
        for lang, text in SENTENCES.items():
            url, body = ENGINES[engine](text, lang)
            data, dt = synth(url, body)
            wav, rate, secs, peak = normalise(data)
            path = "/tmp/cmp_%s_%s.wav" % (engine, lang)
            open(path, "wb").write(wav)
            print("%-11s %-5s %7.1f %8.1f %14.2f %6d %9.2f" % (engine, lang, secs, dt, dt / secs, rate, peak), flush=True)
            if args.play:
                subprocess.run(["aplay", "-q", "-D", "plughw:1,0", path])


if __name__ == "__main__":
    main()
