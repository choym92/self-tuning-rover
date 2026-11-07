#!/usr/bin/env python3
"""HTTP front for Supertonic 3: POST /say {"text","lang":"ko"|"en","voice":"F1","steps":8,"speed":1.05} -> WAV."""
import argparse, inspect, io, json, os, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import numpy as np
import soundfile as sf
from supertonic import TTS

ap = argparse.ArgumentParser()
ap.add_argument("--assets", required=True)
ap.add_argument("--port", type=int, default=8093)
ap.add_argument("--host", default="0.0.0.0", help="127.0.0.1 outside a container (the Mac mini)")
args = ap.parse_args()

t0 = time.perf_counter()
sig = inspect.signature(TTS.__init__)
kw = {}
for name in ("model_dir", "assets_dir", "onnx_dir", "local_dir", "path"):
    if name in sig.parameters:
        kw[name] = args.assets
        break
if "auto_download" in sig.parameters:
    kw["auto_download"] = not kw
tts = TTS(**kw)
LOAD_S = round(time.perf_counter() - t0, 2)
print("supertonic ready, load %.2f s, init kwargs %s, signature %s" % (LOAD_S, kw, sig), flush=True)
STYLE_CACHE = {}
CONFIG_RATE = 0
for cfg in (os.path.join(args.assets, "onnx", "tts.json"), os.path.join(args.assets, "config.json")):
    try:
        with open(cfg) as f:
            CONFIG_RATE = int(json.load(f).get("sample_rate") or 0) or CONFIG_RATE
    except (OSError, ValueError):
        pass
print("sample rate from config:", CONFIG_RATE, flush=True)


def style(name):
    if name not in STYLE_CACHE:
        STYLE_CACHE[name] = tts.get_voice_style(voice_name=name)
    return STYLE_CACHE[name]


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        self._send(200, json.dumps({"ok": True, "load_s": LOAD_S, "init": kw, "signature": str(sig)}).encode(), "application/json")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(n)) if n else {}
            text = str(req.get("text", "")).strip()
            if not text:
                raise ValueError("empty text")
            t = time.perf_counter()
            wav, duration = tts.synthesize(text, voice_style=style(req.get("voice", "M1")), lang=req.get("lang", "en"),
                                           total_steps=int(req.get("steps", 8)), speed=float(req.get("speed", 1.05)))
            synth = time.perf_counter() - t
            samples = np.concatenate([np.asarray(w, dtype=np.float32).ravel() for w in (wav if isinstance(wav, (list, tuple)) else [wav])])
            duration = float(np.sum(np.asarray(duration, dtype=np.float64)))
            rate = int(getattr(tts, "sample_rate", 0) or CONFIG_RATE or 44100)
            peak = float(np.max(np.abs(samples))) if samples.size else 0.0
            if peak > 0:
                samples = np.clip(samples * (0.89 / peak), -1.0, 1.0)
            buf = io.BytesIO(); sf.write(buf, samples, rate, format="WAV", subtype="PCM_16")
            self.send_response(200); self.send_header("Content-Type", "audio/wav"); self.send_header("Content-Length", str(buf.getbuffer().nbytes))
            self.send_header("X-Synth-Seconds", "%.2f" % synth); self.send_header("X-Audio-Seconds", "%.2f" % float(duration)); self.send_header("X-Rate", str(rate)); self.end_headers()
            self.wfile.write(buf.getvalue())
        except Exception as e:
            self._send(400, json.dumps({"error": repr(e)}).encode(), "application/json")

    def log_message(self, *a):
        pass


ThreadingHTTPServer((args.host, args.port), H).serve_forever()
