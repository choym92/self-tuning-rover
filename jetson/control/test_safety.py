"""Unit tests for the stage-1 controller and API. Standard library only; no Jetson needed.

    python3 -B -m unittest discover -s jetson/control -p 'test_*.py' -v
"""
import json
import os
import socket
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server  # noqa: E402


class FakeLink:
    def __init__(self, voltage=1150):
        self.sent = []
        self.fb = {"T": 1001, "L": 0, "R": 0, "odl": 0, "odr": 0, "v": voltage, "pan": 0.0, "tilt": 0.0}

    def send(self, obj):
        self.sent.append(obj)

    def latest(self):
        return dict(self.fb)

    def stats(self):
        return {"rate_hz": 19.5, "feedback_age_s": 0.05, "bad_lines": 0, "sent": len(self.sent)}


class FakeClock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def make(allow=True, voltage=1150, synced=True):
    link = FakeLink(voltage)
    clock = FakeClock()
    ctl = server.Controller(link, cap=80, allow_drive=allow, clock=clock, synced=lambda: synced)
    return ctl, link, clock


class ControllerTests(unittest.TestCase):
    def test_drive_disabled_sends_nothing(self):
        ctl, link, clock = make(allow=False)
        self.assertEqual(ctl.drive(1, 1), "disabled")
        for _ in range(5):
            ctl.tick()
            clock.advance(server.TICK)
        self.assertEqual(link.sent, [])
        self.assertFalse(ctl.snapshot()["allow_drive"])

    def test_drive_scales_by_cap_and_clamps(self):
        ctl, link, clock = make()
        self.assertEqual(ctl.drive(1, 1), "ok")
        ctl.tick()
        self.assertEqual(link.sent[-1], {"T": 11, "L": 80, "R": 80})
        self.assertEqual(ctl.drive(0.5, -3), "ok")
        ctl.tick()
        self.assertEqual(link.sent[-1], {"T": 11, "L": 40, "R": -80})
        self.assertEqual(ctl.drive("x", 1), "bad_request")

    def test_unchanged_target_is_not_resent_every_tick(self):
        ctl, link, clock = make()
        ctl.drive(1, 1)
        for _ in range(4):
            ctl.tick()
            clock.advance(server.TICK)
        self.assertEqual(len(link.sent), 1)

    def test_command_expires_and_stops_once(self):
        ctl, link, clock = make()
        ctl.drive(1, 1)
        ctl.tick()
        clock.advance(server.CMD_TTL + 0.01)
        ctl.tick()
        self.assertEqual(link.sent[-1], {"T": 11, "L": 0, "R": 0})
        self.assertEqual(ctl.last_reason, "expired")
        n = len(link.sent)
        for _ in range(10):
            clock.advance(server.TICK)
            ctl.tick()
        self.assertEqual(len(link.sent), n)
        self.assertEqual(ctl.last_reason, "idle")

    def test_estop_latches_until_reset(self):
        ctl, link, clock = make()
        ctl.drive(1, 1)
        ctl.tick()
        ctl.emergency_stop()
        self.assertEqual(link.sent[-2:], [{"T": 11, "L": 0, "R": 0}, {"T": 1, "L": 0, "R": 0}])
        self.assertEqual(ctl.drive(1, 1), "estop")
        n = len(link.sent)
        for _ in range(5):
            ctl.tick()
            clock.advance(server.TICK)
        self.assertEqual(len(link.sent), n)
        self.assertTrue(ctl.snapshot()["estop"])
        self.assertEqual(ctl.reset(), "ok")
        self.assertEqual(ctl.drive(0.25, 0.25), "ok")
        ctl.tick()
        self.assertEqual(link.sent[-1], {"T": 11, "L": 20, "R": 20})

    def test_low_voltage_refuses_drive_and_reset(self):
        ctl, link, clock = make(voltage=950)
        self.assertEqual(ctl.drive(1, 1), "low_voltage")
        ctl.emergency_stop()
        self.assertEqual(ctl.reset(), "low_voltage")
        self.assertEqual(ctl.snapshot()["battery_state"], "stop")
        link.fb["v"] = 1040
        self.assertEqual(ctl.snapshot()["battery_state"], "warn")
        link.fb["v"] = 1150
        self.assertEqual(ctl.snapshot()["battery_state"], "ok")

    def test_cap_limits(self):
        ctl, link, clock = make()
        self.assertEqual(ctl.set_cap(server.CAP_MAX + 1), "out_of_range")
        self.assertEqual(ctl.set_cap(-1), "out_of_range")
        self.assertEqual(ctl.set_cap("abc"), "bad_request")
        self.assertEqual(ctl.set_cap(40), "ok")
        ctl.drive(1, 1)
        ctl.tick()
        self.assertEqual(link.sent[-1], {"T": 11, "L": 40, "R": 40})

    def test_head_clamps_rate_limits_and_estop(self):
        ctl, link, clock = make()
        self.assertEqual(ctl.move_head(pan=200, tilt=-50), "ok")
        ctl.tick()
        self.assertEqual(link.sent[-1], {"T": 133, "X": 120.0, "Y": -30.0, "SPD": server.HEAD_SPD, "ACC": server.HEAD_ACC})
        self.assertEqual(ctl.move_head(dpan=-5), "ok")
        ctl.tick()                      # too soon: rate limited
        self.assertEqual(len(link.sent), 1)
        clock.advance(server.HEAD_MIN_INTERVAL + 0.01)
        ctl.tick()
        self.assertEqual(link.sent[-1]["X"], 115.0)
        self.assertEqual(ctl.move_head(pan="x"), "bad_request")
        ctl.emergency_stop()
        self.assertEqual(ctl.move_head(pan=0, tilt=0), "estop")
        self.assertEqual(ctl.snapshot()["head"]["pan"], 115.0)

    def test_head_settles_against_gear_play(self):
        ctl, link, clock = make()
        ctl.move_head(pan=0, tilt=0)
        ctl.tick()                                   # command sent
        self.assertEqual(link.sent[-1]["X"], 0.0)
        link.fb["pan"], link.fb["tilt"] = -1.1, 0.3  # the servo stopped short, as seen on 2026-11-07
        clock.advance(0.3); ctl.tick()
        self.assertEqual(len(link.sent), 1)          # too early to trust the reading
        clock.advance(server.HEAD_SETTLE + 0.01); ctl.tick()
        self.assertEqual((link.sent[-1]["X"], link.sent[-1]["Y"]), (1.1, 0.0))   # nudge by the error; tilt within tolerance
        link.fb["pan"] = 0.1                         # now close enough
        clock.advance(server.HEAD_SETTLE + 0.01); ctl.tick()
        self.assertEqual(len(link.sent), 2)
        self.assertEqual(ctl.snapshot()["head"]["actual_pan"], 0.1)
        # never more than HEAD_SETTLE_TRIES nudges for one target
        ctl.move_head(pan=30); clock.advance(server.HEAD_MIN_INTERVAL + 0.01); ctl.tick()
        for _ in range(6):
            link.fb["pan"] = 20.0
            clock.advance(server.HEAD_SETTLE + 0.01); ctl.tick()
        self.assertEqual(len(link.sent), 3 + server.HEAD_SETTLE_TRIES)

    def test_head_settle_waits_for_the_servo_to_stop(self):
        ctl, link, clock = make()
        ctl.move_head(pan=40); ctl.tick()            # command sent
        for p in (5.0, 15.0, 25.0, 35.0):            # readings still changing: the head is travelling
            link.fb["pan"] = p; clock.advance(0.3); ctl.tick()
            self.assertEqual(len(link.sent), 1)
        link.fb["pan"] = 38.1                        # stopped short
        clock.advance(0.3); ctl.tick()
        self.assertEqual(len(link.sent), 1)          # changed again: not trusted yet
        clock.advance(server.HEAD_SETTLE + 0.01); ctl.tick()
        self.assertEqual(link.sent[-1]["X"], 41.9)   # nudge by the error once the readings held still

    def test_head_trim_shifts_commands_and_readings(self):
        link = FakeLink(); clock = FakeClock()
        ctl = server.Controller(link, cap=80, allow_drive=True, clock=clock, synced=lambda: True, trim=(-1.1, 0.3))
        ctl.move_head(pan=0, tilt=0); ctl.tick()
        self.assertEqual((link.sent[-1]["X"], link.sent[-1]["Y"]), (-1.1, 0.3))   # forward is where the servo reads -1.1
        link.fb["pan"], link.fb["tilt"] = -1.1, 0.3
        self.assertEqual((ctl.snapshot()["head"]["actual_pan"], ctl.snapshot()["head"]["actual_tilt"]), (0.0, 0.0))

    def test_snapshot_reports_clock(self):
        ctl, _, _ = make(synced=False)
        self.assertFalse(ctl.snapshot()["clock_synced"])


class CameraTests(unittest.TestCase):
    def test_push_wait_and_stats(self):
        cam = server.Camera()                       # no device: frames come from push()
        self.assertFalse(cam.stats()["ok"])
        self.assertEqual(cam.wait(0, timeout=0.01), (None, 0))
        cam.push(b"\xff\xd8one")
        self.assertEqual(cam.wait(0, timeout=0.01), (b"\xff\xd8one", 1))
        self.assertEqual(cam.wait(1, timeout=0.01), (None, 1))
        cam.push(b"\xff\xd8two")
        self.assertEqual(cam.wait(0, timeout=0.01), (b"\xff\xd8two", 2))   # a slow client skips to the newest
        st = cam.stats()
        self.assertEqual((st["ok"], st["size"], st["fps"], st["clients"]), (True, "1280x720", 1.0, 0))


class FakeEyesHandler(server.BaseHTTPRequestHandler):
    """Stands in for the eyes service: a state document and one picture."""
    def log_message(self, *a):
        pass

    def do_GET(self):
        body, ctype = (b'{"connected": true, "fps": 29.5, "center_m": 2.47}', "application/json") if self.path == "/api/state" \
            else (b"\xff\xd8eyes", "image/jpeg") if self.path.startswith("/color.jpg") else (b"{}", "application/json")
        self.send_response(200 if ctype else 404)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = b'{"echo": ' + (self.rfile.read(n) if n else b"null") + b"}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class FakeBrainHandler(server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        body = b'{"status":"ok"}' if self.path == "/health" else b"{}"
        self.send_response(200 if self.path == "/health" else 404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class BrainTests(unittest.TestCase):
    def test_brain_link_reports_up_and_down(self):
        fake = server.ThreadingHTTPServer(("127.0.0.1", 0), FakeBrainHandler)
        threading.Thread(target=fake.serve_forever, daemon=True).start()
        up = server.BrainLink("http://127.0.0.1:%d" % fake.server_address[1])
        free = socket.socket(); free.bind(("127.0.0.1", 0)); port = free.getsockname()[1]; free.close()
        down = server.BrainLink("http://127.0.0.1:%d" % port)
        deadline = time.time() + 3
        while time.time() < deadline and (up.state["error"] == "not reached yet" or down.state["error"] == "not reached yet"):
            time.sleep(0.05)
        self.assertTrue(up.state["ok"])
        self.assertIsInstance(up.state["ms"], int)
        self.assertEqual((down.state["ok"], down.state["error"]), (False, "unreachable"))
        self.assertEqual(server.BrainLink().state["error"], "not configured")
        fake.shutdown(); fake.server_close()

    def test_host_stats_is_a_plain_dict(self):
        st = server.host_stats()                     # empty on a Mac, filled on the Jetson
        self.assertIsInstance(st, dict)
        self.assertTrue(set(st) <= {"mem_total_mb", "mem_avail_mb", "temp_c"})


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.link = FakeLink()
        self.cam = server.Camera()
        self.fake_eyes = server.ThreadingHTTPServer(("127.0.0.1", 0), FakeEyesHandler)
        threading.Thread(target=self.fake_eyes.serve_forever, daemon=True).start()
        self.eyes = server.EyesLink("http://127.0.0.1:%d" % self.fake_eyes.server_address[1])
        self.ctl = server.Controller(self.link, cap=80, allow_drive=False, synced=lambda: True)
        page = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
        self.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(self.ctl, page, self.cam, self.eyes))
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.fake_eyes.shutdown()
        self.fake_eyes.server_close()

    def call(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def test_page_and_state(self):
        with urllib.request.urlopen(self.base + "/", timeout=5) as r:
            self.assertEqual(r.status, 200)
            self.assertIn(b"<title>", r.read())
        code, state = self.call("GET", "/api/state")
        self.assertEqual(code, 200)
        self.assertEqual(state["battery_v"], 11.5)
        self.assertEqual(state["uart"]["rate_hz"], 19.5)

    def test_drive_is_403_until_allowed(self):
        code, body = self.call("POST", "/api/drive", {"l": 1, "r": 1})
        self.assertEqual((code, body["result"]), (403, "disabled"))
        self.assertEqual(self.link.sent, [])
        self.ctl.allow_drive = True
        code, body = self.call("POST", "/api/drive", {"l": 1, "r": 1})
        self.assertEqual((code, body["result"]), (200, "ok"))
        code, body = self.call("POST", "/api/drive", {"l": "no", "r": 1})
        self.assertEqual(code, 400)

    def test_estop_reset_cap(self):
        self.assertEqual(self.call("POST", "/api/estop")[0], 200)
        self.assertTrue(self.call("GET", "/api/state")[1]["estop"])
        self.assertEqual(self.call("POST", "/api/reset")[0], 200)
        self.assertEqual(self.call("POST", "/api/cap", {"pwm": 60})[1]["cap"], 60)
        self.assertEqual(self.call("POST", "/api/cap", {"pwm": 999})[0], 400)
        code, body = self.call("POST", "/api/head", {"pan": 30, "tilt": 10})
        self.assertEqual((code, body["head"]["pan"], body["head"]["tilt"]), (200, 30.0, 10.0))
        self.assertEqual(self.call("GET", "/nope")[0], 404)

    def test_video_endpoints(self):
        self.assertEqual(self.call("GET", "/frame.jpg")[0], 503)
        self.assertFalse(self.call("GET", "/api/state")[1]["camera"]["ok"])
        self.cam.push(b"\xff\xd8abc")
        with urllib.request.urlopen(self.base + "/frame.jpg", timeout=5) as r:
            self.assertEqual((r.status, r.headers["Content-Type"], r.read()), (200, "image/jpeg", b"\xff\xd8abc"))
        stream = urllib.request.urlopen(self.base + "/video.mjpg", timeout=5)
        self.assertTrue(stream.headers["Content-Type"].startswith("multipart/x-mixed-replace"))
        head = b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: 5\r\n\r\n"
        self.assertEqual(stream.read(len(head) + 5 + 2), head + b"\xff\xd8abc\r\n")
        self.assertEqual(self.call("GET", "/api/state")[1]["camera"]["clients"], 1)
        self.cam.push(b"\xff\xd8defgh")
        head = head.replace(b"Length: 5", b"Length: 7")
        self.assertEqual(stream.read(len(head) + 7 + 2), head + b"\xff\xd8defgh\r\n")
        stream.close()

    def test_d436_proxy_and_state(self):
        import time
        for _ in range(40):                                   # the poller's first read lands within a second
            if self.eyes.state.get("connected"):
                break
            time.sleep(0.05)
        self.assertEqual(self.call("GET", "/api/state")[1]["d436"]["center_m"], 2.47)
        with urllib.request.urlopen(self.base + "/d436/color.jpg", timeout=5) as r:
            self.assertEqual((r.status, r.headers["Content-Type"], r.read()), (200, "image/jpeg", b"\xff\xd8eyes"))
        code, body = self.call("POST", "/d436/api/camera", {"on": False})
        self.assertEqual((code, body), (200, {"echo": {"on": False}}))
        dead = server.make_handler(self.ctl, os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"),
                                   self.cam, server.EyesLink("http://127.0.0.1:1"))
        httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), dead)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            req = urllib.request.Request("http://127.0.0.1:%d/d436/color.jpg" % httpd.server_address[1])
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(req, timeout=5)
            self.assertEqual(cm.exception.code, 503)
        finally:
            httpd.shutdown(); httpd.server_close()


if __name__ == "__main__":
    unittest.main()
