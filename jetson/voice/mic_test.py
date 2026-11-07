#!/usr/bin/env python3
"""Can Whisper understand Paul through the rover's camera microphone? Run from the Mac.

Records a quiet baseline, then one short clip per test phrase, on the rover, and transcribes each
with the running rover-stt container. Text, levels and the clips are kept under private/mic-test/
(gitignored), so the same clips can be re-run through a larger model to tell the microphone from
the model. Nothing is played on the speaker.

  python3 jetson/voice/mic_test.py --distance 1
  python3 jetson/voice/mic_test.py --distance 2 --lang ko
"""
import argparse
import datetime
import difflib
import json
import os
import re
import subprocess
import sys
import time

HOST = "paulcho@192.168.1.238"
DEVICE = "plughw:0,0"
SECONDS = 5
PHRASES = {
    "en": ["Hey Kalman", "Hey Kalman, what time is it?", "Hey Kalman, stop.", "Hey Kalman, look to the left.",
           "Hey Kalman, how is your battery?", "Hey Kalman, do you see the cat?"],
    "ko": ["헤이 칼만", "헤이 칼만, 지금 몇 시야?", "헤이 칼만, 멈춰.", "헤이 칼만, 왼쪽 봐.",
           "헤이 칼만, 배터리 어때?", "헤이 칼만, 고양이 보여?"],
}
WAKE = re.compile(r"kalman|calman|colman|coleman|칼만|칼먼|갈만", re.I)
LEVELS = ("import wave,array,math;w=wave.open('/tmp/mic_test.wav');a=array.array('h',w.readframes(w.getnframes()));"
          "print(round(math.sqrt(sum(x*x for x in a)/max(len(a),1))),max(abs(x) for x in a))")


def ssh(cmd, timeout=60):
    return subprocess.run(["ssh", "-o", "BatchMode=yes", HOST, cmd], capture_output=True, text=True, timeout=timeout)


def clip(seconds, lang, keep, cue=None):
    # "go" is printed on the Jetson just before arecord opens, so the cue is not ahead of the recording
    rec = subprocess.Popen(["ssh", "-o", "BatchMode=yes", HOST,
                            f"echo go; arecord -q -D {DEVICE} -f S16_LE -r 16000 -c 1 -d {seconds} /tmp/mic_test.wav"],
                           stdout=subprocess.PIPE, text=True)
    rec.stdout.readline()
    if cue:
        print(cue, flush=True)
    if rec.wait(timeout=seconds + 20) != 0:
        sys.exit("arecord failed")
    subprocess.run(["scp", "-q", "-o", "BatchMode=yes", HOST + ":/tmp/mic_test.wav", keep], check=True)
    cmd = (f"python3 -c \"{LEVELS}\" && docker cp /tmp/mic_test.wav rover-stt:/tmp/mic_test.wav >/dev/null && "
           f"docker exec rover-stt curl -s -F file=@/tmp/mic_test.wav -F temperature=0 -F language={lang} "
           "-F response_format=json http://127.0.0.1:8080/inference")
    r = ssh(cmd)
    if r.returncode != 0:
        sys.exit("capture failed: " + (r.stderr.strip() or r.stdout.strip()))
    levels, body = r.stdout.split("\n", 1)
    rms, peak = (int(x) for x in levels.split())
    return rms, peak, json.loads(body).get("text", "").strip()


def norm(s):
    return re.sub(r"[^\w]", "", s.lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--distance", type=float, required=True, help="metres between Paul and the rover")
    ap.add_argument("--lang", choices=list(PHRASES), default="en")
    ap.add_argument("--note", default="", help="free text, for example 'TV on'")
    args = ap.parse_args()

    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "private", "mic-test")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    clips = os.path.join(root, f"{stamp}-{args.lang}-{args.distance:g}m")
    os.makedirs(clips, exist_ok=True)
    print(f"Stay quiet for {SECONDS} s (baseline)...", flush=True)
    base_rms, base_peak, base_text = clip(SECONDS, args.lang, os.path.join(clips, "baseline.wav"))
    print(f"baseline: RMS {base_rms}, peak {base_peak}, heard {base_text!r}\n")
    rows = []
    for i, phrase in enumerate(PHRASES[args.lang], 1):
        print(f"[{i}/{len(PHRASES[args.lang])}] next:  {phrase}", flush=True)
        time.sleep(3)
        rms, peak, text = clip(SECONDS, args.lang, os.path.join(clips, f"{i}.wav"), cue="        SPEAK NOW")
        score = difflib.SequenceMatcher(None, norm(phrase), norm(text)).ratio()
        wake = bool(WAKE.search(text))
        rows.append({"phrase": phrase, "heard": text, "rms": rms, "peak": peak, "match": round(score, 2), "wake": wake})
        print(f"        heard {text!r}  (RMS {rms}, peak {peak}, match {score:.2f}, wake {'yes' if wake else 'NO'})\n", flush=True)

    n = len(rows)
    summary = {"when": datetime.datetime.now().isoformat(timespec="seconds"), "clips": os.path.basename(clips), "distance_m": args.distance, "lang": args.lang,
               "note": args.note, "baseline_rms": base_rms, "wake_heard": sum(r["wake"] for r in rows), "phrases": n,
               "mean_match": round(sum(r["match"] for r in rows) / n, 2),
               "speech_to_noise": round(sum(r["rms"] for r in rows) / n / max(base_rms, 1), 1)}
    print("summary:", json.dumps(summary, ensure_ascii=False))
    with open(os.path.join(root, "runs.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({**summary, "rows": rows}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
