"""Unit tests for the eyes service with a fake camera and a fake encoder (no numpy, no Jetson).

    python3 -B -m unittest discover -s jetson/eyes -p 'test_*.py' -v
"""
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eyes_server as es  # noqa: E402


class FakeEncoder:
    def __init__(self):
        self.calls = 0

    def color_jpeg(self, frame):
        self.calls += 1
        return b"\xff\xd8C" + frame

    def depth_jpeg(self, frame, scale):
        self.calls += 1
        return b"\xff\xd8D" + frame

    def depth_stats(self, frame, scale):
        return {"valid": 0.69, "center_m": 2.47}


class EyesTests(unittest.TestCase):
    def test_encode_once_per_frame_and_stats(self):
        enc = FakeEncoder()
        eyes = es.Eyes(None, enc)
        self.assertEqual(eyes.jpeg("color"), (b"", 0))
        self.assertFalse(eyes.state()["connected"])
        eyes.push(b"c1", b"d1")
        self.assertEqual(eyes.jpeg("color"), (b"\xff\xd8Cc1", 1))
        self.assertEqual(eyes.jpeg("color"), (b"\xff\xd8Cc1", 1))      # cached
        self.assertEqual(eyes.jpeg("depth"), (b"\xff\xd8Dd1", 1))
        self.assertEqual(enc.calls, 2)
        eyes.push(b"c2", b"d2")
        self.assertEqual(eyes.jpeg("depth")[0], b"\xff\xd8Dd2")
        self.assertEqual(enc.calls, 3)
        s = eyes.state()
        self.assertEqual((s["connected"], s["frames"], s["valid"], s["center_m"], s["fps"]), (True, 2, 0.69, 2.47, 1.0))
        self.assertIsNone(eyes.wait(2, timeout=0.01))
        self.assertEqual(eyes.wait(0, timeout=0.01), 2)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.eyes = es.Eyes(None, FakeEncoder())
        self.httpd = es.serve(self.eyes, "127.0.0.1", 0)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=5) as r:
                return r.status, r.headers["Content-Type"], r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers["Content-Type"], e.read()

    def test_endpoints(self):
        self.assertEqual(self.get("/color.jpg")[0], 503)
        self.assertEqual(json.loads(self.get("/api/state")[2])["connected"], False)
        self.eyes.push(b"c1", b"d1")
        self.assertEqual(self.get("/depth.jpg"), (200, "image/jpeg", b"\xff\xd8Dd1"))
        stream = urllib.request.urlopen(self.base + "/color.mjpg?fps=5", timeout=5)
        self.assertTrue(stream.headers["Content-Type"].startswith("multipart/x-mixed-replace"))
        head = b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: 5\r\n\r\n"
        self.assertEqual(stream.read(len(head) + 5 + 2), head + b"\xff\xd8Cc1\r\n")
        self.assertEqual(json.loads(self.get("/api/state")[2])["clients"], 1)
        stream.close()
        self.assertEqual(self.get("/nope")[0], 404)


if __name__ == "__main__":
    unittest.main()
