#!/usr/bin/env python3
"""Tiny HTTP front for Kokoro: POST /say {"text": "...", "voice": "af_heart", "speed": 1.0} -> WAV bytes.
GET /health -> {"ok": true, "load_s": ...}. Standard library plus kokoro-onnx and soundfile."""
import argparse
import io
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--voices", required=True)
ap.add_argument("--port", type=int, default=8092)
ap.add_argument("--voice", default="af_heart")
args = ap.parse_args()

t0 = time.perf_counter()
kokoro = Kokoro(args.model, args.voices)
LOAD_S = round(time.perf_counter() - t0, 2)
print("kokoro ready, load %.2f s, model %s" % (LOAD_S, args.model), flush=True)


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/health"):
            self._send(200, json.dumps({"ok": True, "load_s": LOAD_S, "voices": list(kokoro.get_voices())[:60]}).encode(), "application/json")
        else:
            self._send(404, b"{}", "application/json")

    def do_POST(self):
        if self.path != "/say":
            return self._send(404, b"{}", "application/json")
        n = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(n)) if n else {}
            text = str(req.get("text", "")).strip()
            if not text:
                raise ValueError("empty text")
            t = time.perf_counter()
            samples, rate = kokoro.create(text, voice=req.get("voice", args.voice), speed=float(req.get("speed", 1.0)), lang="en-us")
            # Kokoro peaks around -9 dBFS; the rover speaker has no gain above 0 dB, so normalise
            # to -1 dBFS here (optional "gain" multiplies on top, clipped to full scale).
            peak = float(np.max(np.abs(samples))) if len(samples) else 0.0
            if peak > 0:
                samples = np.clip(samples * (0.89 / peak) * float(req.get("gain", 1.0)), -1.0, 1.0)
            buf = io.BytesIO()
            sf.write(buf, samples, rate, format="WAV", subtype="PCM_16")
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(buf.getbuffer().nbytes))
            self.send_header("X-Synth-Seconds", "%.2f" % (time.perf_counter() - t))
            self.send_header("X-Audio-Seconds", "%.2f" % (len(samples) / rate))
            self.end_headers()
            self.wfile.write(buf.getvalue())
        except Exception as e:  # report the reason to the caller instead of a bare 500
            self._send(400, json.dumps({"error": str(e)}).encode(), "application/json")

    def log_message(self, fmt, *a):
        pass


ThreadingHTTPServer(("0.0.0.0", args.port), H).serve_forever()
