#!/usr/bin/env python3
"""Record Paul saying the wake phrase on the rover microphone, for tuning and training the wake detector.

Run from the Mac. rover-mind is stopped for the session (it owns the microphone) and started again at
the end. Each take: the rover beeps, then records 2.5 s; say the phrase right after the beep. Two
beeps mean "move to the next spot". Clips go to private/wake/<session>/ (gitignored) with a CSV of
what each clip is meant to contain.

  python3 jetson/voice/wake_record.py              # the full session, about 10 minutes
  python3 jetson/voice/wake_record.py --quick      # 3 takes per group, to try it out
"""
import argparse
import csv
import datetime
import os
import subprocess
import sys
import time

HOST = "paulcho@192.168.1.238"
SECONDS = 2.5
# (label, what to say, how, takes)
GROUPS = [
    ("pos", "Hey Kalman", "about 1 m (1.5 steps), facing the rover, normal voice", 12),
    ("pos", "Hey Kalman", "about 2 m (3 steps), facing the rover, normal voice", 12),
    ("pos", "Hey Kalman", "about 3 m (4-5 steps), a bit louder", 10),
    ("pos", "Hey Kalman", "about 2 m, turned to the side or walking", 8),
    ("pos", "Hey Kalman", "about 1-2 m, quiet voice", 8),
    ("neg", "Hey Calvin", "about 2 m, normal voice", 3),
    ("neg", "Hey common", "about 2 m, normal voice", 3),
    ("neg", "Hey Carmen", "about 2 m, normal voice", 3),
    ("neg", "Hey Siri / Hey Google / OK Google (any)", "about 2 m, normal voice", 3),
    ("neg", "any sentence without the name, e.g. 'how is the weather'", "about 2 m, normal voice", 4),
    ("quiet", "(stay silent)", "room as it is", 4),
]
PREP = ("python3 -c \"import wave,math,array;r=16000\n"
        "def t(p,f,s):\n"
        " n=int(s*r);a=array.array('h',(int(9000*math.sin(2*math.pi*f*i/r)*min(1,i/160,(n-i)/160)) for i in range(n)))\n"
        " w=wave.open(p,'wb');w.setnchannels(1);w.setsampwidth(2);w.setframerate(r);w.writeframes(a.tobytes())\n"
        "t('/tmp/wake_beep.wav',880,0.12);t('/tmp/wake_move.wav',660,0.5)\"")


def ssh(cmd, timeout=60):
    return subprocess.run(["ssh", "-o", "BatchMode=yes", HOST, cmd], capture_output=True, text=True, timeout=timeout)


def play(name):
    ssh(f"for i in $(seq 1 10); do aplay -q -D plughw:1,0 /tmp/{name}.wav 2>/dev/null && break; sleep 0.3; done")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "private", "wake", stamp)
    os.makedirs(root, exist_ok=True)
    total = sum(3 if args.quick else g[3] for g in GROUPS)
    print(f"{total} takes. rover-mind pauses during the session.", flush=True)
    r = ssh("docker stop rover-mind >/dev/null 2>&1; " + PREP)
    if r.returncode != 0:
        sys.exit("prepare failed: " + r.stderr)
    rows, n = [], 0
    try:
        for gi, (label, say, how, takes) in enumerate(GROUPS):
            takes = 3 if args.quick else takes
            print(f"\n== Group {gi + 1}/{len(GROUPS)}: say \"{say}\" | {how} | {takes} takes", flush=True)
            print("   Get in place: starting in 8 s (a long low beep = start).", flush=True)
            time.sleep(6)
            play("wake_move")
            time.sleep(1.5)
            for k in range(takes):
                n += 1
                name = f"{label}_{n:03d}.wav"
                r = ssh(f"aplay -q -D plughw:1,0 /tmp/wake_beep.wav 2>/dev/null; "
                        f"arecord -q -D plughw:0,0 -f S16_LE -r 16000 -c 1 -s {int(SECONDS * 16000)} /tmp/wake_take.wav", timeout=30)
                if r.returncode != 0:
                    print("   recording failed: " + r.stderr.strip(), flush=True)
                    continue
                subprocess.run(["scp", "-q", "-o", "BatchMode=yes", HOST + ":/tmp/wake_take.wav", os.path.join(root, name)], check=True)
                rows.append({"file": name, "label": label, "said": say, "how": how})
                print(f"   {k + 1}/{takes} {name}", flush=True)
                time.sleep(1.2)
    finally:
        with open(os.path.join(root, "takes.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["file", "label", "said", "how"])
            w.writeheader()
            w.writerows(rows)
        ssh("rm -f /tmp/wake_take.wav; docker start rover-mind >/dev/null")
        print(f"\nDone: {len(rows)} clips in private/wake/{stamp}/. rover-mind started again.", flush=True)


if __name__ == "__main__":
    main()
