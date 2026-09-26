"""Local tests use a fake Whisper HTTP backend. No microphone, model or Jetson."""
import argparse
from contextlib import redirect_stdout
import http.server
import io
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest
import wave

from bridge import Handler, Server
from mac_stream import run
from protocol import MAX_BYTES, receive_json, send_json


class Backend(http.server.BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.calls.append(body)
        if self.path != "/inference":
            self.send_error(404)
            return
        if self.server.fail:
            self.send_error(500, "Simulated model failure")
            return
        payload = json.dumps({"text": "주방으로 가 줘"}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class TransportTest(unittest.TestCase):
    def setUp(self):
        Backend.calls = []
        self.backend = http.server.HTTPServer(("127.0.0.1", 0), Backend)
        self.backend.fail = False
        self.bridge = Server(("127.0.0.1", 0), Handler)
        self.bridge.backend = f"http://127.0.0.1:{self.backend.server_port}"
        self.bridge.language = "en"
        self.threads = []
        for server in (self.backend, self.bridge):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.threads.append(thread)

    def tearDown(self):
        for server in (self.bridge, self.backend):
            server.shutdown()
            server.server_close()
        for thread in self.threads:
            thread.join()

    def connect(self):
        return socket.create_connection(self.bridge.server_address, timeout=3)

    def test_client_roundtrip_and_repeated_requests(self):
        with tempfile.TemporaryDirectory() as folder:
            wav_path = Path(folder) / "test.wav"
            pcm = b"\x01\x00" * 1600
            with wave.open(str(wav_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(pcm)
            args = argparse.Namespace(wav=str(wav_path), seconds=1, device="0",
                                      port=self.bridge.server_address[1],
                                      out=str(Path(folder) / "results.jsonl"))
            for _ in range(2):
                with redirect_stdout(io.StringIO()):
                    result = run(args)
                self.assertEqual(result["text"], "주방으로 가 줘")
                self.assertEqual(result["language"], "en")
                self.assertEqual(result["audio_s"], 0.1)
                self.assertGreaterEqual(result["total_s"], result["post_capture_result_s"])
                self.assertGreaterEqual(result["server_processing_s"], result["server_inference_api_s"])
            self.assertEqual(len(Path(args.out).read_text().splitlines()), 2)
            self.assertIn(b'name="language"\r\n\r\nen', Backend.calls[0])
            self.assertIn(b"RIFF", Backend.calls[0])
            self.assertIn(pcm, Backend.calls[0])

    def test_reject_oversized_audio_without_backend_call(self):
        with self.connect() as sock, sock.makefile("rwb") as stream:
            send_json(stream, {"op": "transcribe", "rate": 16000, "bytes": MAX_BYTES + 2})
            self.assertEqual(receive_json(stream)["op"], "error")
        self.assertEqual(Backend.calls, [])

    def test_reject_truncated_audio(self):
        with self.connect() as sock, sock.makefile("rwb") as stream:
            send_json(stream, {"op": "transcribe", "rate": 16000, "bytes": 100})
            self.assertEqual(receive_json(stream)["op"], "ready")
            sock.sendall(b"\x00\x00")
            sock.shutdown(socket.SHUT_WR)
            self.assertEqual(receive_json(stream)["op"], "error")
        self.assertEqual(Backend.calls, [])

    def test_backend_failure_is_reported(self):
        self.backend.fail = True
        with self.connect() as sock, sock.makefile("rwb") as stream:
            send_json(stream, {"op": "transcribe", "rate": 16000, "bytes": 3200})
            self.assertEqual(receive_json(stream)["op"], "ready")
            sock.sendall(b"\x00" * 3200)
            self.assertEqual(receive_json(stream)["op"], "received")
            self.assertEqual(receive_json(stream)["op"], "error")


if __name__ == "__main__":
    unittest.main()
