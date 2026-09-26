"""Bounded JSON lines followed by a declared amount of raw PCM; standard library only."""
import json

RATE = 16000
BYTES_PER_SECOND = RATE * 2  # signed little-endian int16, mono
MAX_BYTES = 30 * BYTES_PER_SECOND


def receive_json(stream):
    line = stream.readline(8193)
    if not line or len(line) > 8192 or not line.endswith(b"\n"):
        raise ValueError("Missing or oversized JSON header")
    value = json.loads(line)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def send_json(stream, value):
    stream.write(json.dumps(value, ensure_ascii=False).encode() + b"\n")
    stream.flush()
