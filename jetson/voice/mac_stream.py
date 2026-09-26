"""Send live Mac microphone PCM to Jetson through an existing SSH tunnel.

Fixed capture window, NOT automatic end-of-speech or wake-word detection.
--wav is for repeatable transport tests only; normal mode uses the live microphone.
"""
import argparse
import datetime
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import wave

from protocol import BYTES_PER_SECOND, MAX_BYTES, RATE, receive_json, send_json


def expect(stream, op):
    message = receive_json(stream)
    if message.get("op") != op:
        raise RuntimeError(f"Expected {op}: {message}")
    return message


def run(args):
    wav_pcm = None
    if args.wav:
        with wave.open(args.wav, "rb") as source:
            if (source.getnchannels(), source.getsampwidth(), source.getframerate(),
                    source.getcomptype()) != (1, 2, RATE, "NONE"):
                raise ValueError("WAV must be mono, 16kHz, uncompressed int16")
            if source.getnframes() * 2 > MAX_BYTES:
                raise ValueError("WAV must be at most 30 seconds")
            wav_pcm = source.readframes(source.getnframes())
        size = len(wav_pcm)
    else:
        size = round(args.seconds * RATE) * 2
    if not 0 < size <= MAX_BYTES:
        raise ValueError("Capture duration must be >0 and <=30 seconds")
    process = None
    started = time.perf_counter()
    with tempfile.TemporaryFile() as errors, socket.create_connection(
            ("127.0.0.1", args.port), timeout=10) as sock:
        sock.settimeout(150)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        with sock.makefile("rwb") as stream:
            ping = time.perf_counter()
            send_json(stream, {"op": "ping"})
            expect(stream, "pong")
            rtt = time.perf_counter() - ping
            send_json(stream, {"op": "transcribe", "bytes": size, "rate": RATE})
            expect(stream, "ready")
            try:
                capture_started = time.perf_counter()
                if wav_pcm is None:
                    print(f"Speak for {size / BYTES_PER_SECOND:g}s after the mic opens.", flush=True)
                    process = subprocess.Popen([
                        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                        "-f", "avfoundation", "-i", f":{args.device}",
                        "-ac", "1", "-ar", str(RATE),
                        "-f", "s16le", "pipe:1"], stdout=subprocess.PIPE, stderr=errors)
                sent = 0
                first = None
                while sent < size:
                    chunk = (process.stdout.read(min(640, size - sent)) if process
                             else wav_pcm[sent:sent + 640])
                    if not chunk:
                        errors.seek(0)
                        raise RuntimeError("Microphone ended early: " + errors.read().decode(errors="replace"))
                    if first is None:
                        first = time.perf_counter()
                        if process:
                            print("Microphone is streaming.", flush=True)
                    sock.sendall(chunk)
                    sent += len(chunk)
                sent_at = time.perf_counter()
                expect(stream, "received")
                ack_at = time.perf_counter()
                result = expect(stream, "result")
                finished = time.perf_counter()
            finally:
                if process:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                    process.stdout.close()
    result.update({
        "recorded_at": datetime.datetime.now().astimezone().isoformat(),
        "input": "wav-test" if args.wav else "mac-microphone",
        "model": "whisper-base",
        "transport_rtt_s": rtt,
        "capture_startup_s": first - capture_started,
        "capture_and_send_s": sent_at - capture_started,
        "upload_tail_ack_s": ack_at - sent_at,
        "post_capture_result_s": finished - sent_at,
        "total_s": finished - started,
        "transport_and_overhead_residual_s":
            finished - sent_at - result["server_processing_s"],
    })
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.out:
        destination = Path(args.out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("a") as log:
            log.write(json.dumps(result, ensure_ascii=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18090)
    parser.add_argument("--device", default="0", help="AVFoundation audio device index/name")
    parser.add_argument("--seconds", type=float, default=8)
    parser.add_argument("--wav", help="Optional deterministic test WAV instead of live microphone")
    parser.add_argument("--out", help="Optional JSONL result log; contains transcript, no audio")
    args = parser.parse_args()
    try:
        run(args)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
