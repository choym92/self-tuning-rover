"""Receive live PCM and time a persistent local whisper-server request.

Publish this port only on Jetson loopback and reach it through SSH. No auth is
implemented here. One utterance at a time; audio remains in RAM, not on disk.
"""
import argparse
import io
import json
import socketserver
import subprocess
import time
import urllib.error
import urllib.request
import uuid
import wave

from protocol import BYTES_PER_SECOND, MAX_BYTES, RATE, receive_json, send_json


def transcribe(pcm, url, language):
    wav = io.BytesIO()
    with wave.open(wav, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(pcm)
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in (("language", language), ("response_format", "json")):
        parts.append((f"--{boundary}\r\nContent-Disposition: form-data; "
                      f'name="{name}"\r\n\r\n{value}\r\n').encode())
    parts.append((f"--{boundary}\r\nContent-Disposition: form-data; "
                  'name="file"; filename="capture.wav"\r\n'
                  'Content-Type: audio/wav\r\n\r\n').encode()
                 + wav.getvalue() + f"\r\n--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        url + "/inference", data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        raise ValueError(f"Whisper HTTP error {status}") from None
    elapsed = time.perf_counter() - started
    if not isinstance(result.get("text"), str):
        raise ValueError("Whisper did not return a text field")
    return result["text"].strip(), elapsed


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(60)
        try:
            header = receive_json(self.rfile)
            while header.get("op") == "ping":
                send_json(self.wfile, {"op": "pong"})
                header = receive_json(self.rfile)
            size = header.get("bytes")
            if (header.get("op") != "transcribe" or type(size) is not int
                    or not 0 < size <= MAX_BYTES or size % 2
                    or header.get("rate") != RATE):
                raise ValueError("Expected 0–30s of mono 16kHz int16 PCM")
            send_json(self.wfile, {"op": "ready"})
            started = time.perf_counter()
            pcm = self.rfile.read(size)
            received = time.perf_counter()
            if len(pcm) != size:
                raise ValueError("Audio stream ended before its declared size")
            send_json(self.wfile, {"op": "received", "bytes": size})
            text, inference_s = transcribe(
                pcm, self.server.backend, self.server.language)
            send_json(self.wfile, {
                "op": "result", "text": text, "audio_s": size / BYTES_PER_SECOND,
                "language": self.server.language,
                "server_receive_s": received - started,
                "server_inference_api_s": inference_s,
                "server_processing_s": time.perf_counter() - received,
            })
        except (ValueError, OSError, KeyError) as exc:
            try:
                send_json(self.wfile, {"op": "error", "error": str(exc)})
            except OSError:
                pass


class Server(socketserver.TCPServer):
    allow_reuse_address = True


def wait_backend(url, process):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("whisper-server exited; inspect its startup log")
        try:
            with urllib.request.urlopen(url + "/health", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.25)
    raise RuntimeError("whisper-server did not become ready within 120 seconds")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--backend", default="http://127.0.0.1:8080")
    parser.add_argument("--start-whisper", action="store_true")
    parser.add_argument("--model", default="/models/ggml-base.bin")
    parser.add_argument("--language", default="en")
    args = parser.parse_args()
    process = None
    try:
        if args.start_whisper:
            if args.backend != "http://127.0.0.1:8080":
                parser.error("--start-whisper requires the default backend")
            process = subprocess.Popen([
                "whisper-server", "--host", "127.0.0.1", "--port", "8080",
                "-m", args.model, "-l", args.language, "-t", "4"])
            wait_backend(args.backend, process)
        with Server((args.host, args.port), Handler) as server:
            server.backend = args.backend
            server.language = args.language
            print(f"Ready: {args.host}:{args.port}; language={args.language}",
                  flush=True)
            server.serve_forever()
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
