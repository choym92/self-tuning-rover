"""Unit tests for the stage-1 controller and API. Standard library only; no Jetson needed.

    python3 -B -m unittest discover -s jetson/control -p 'test_*.py' -v
"""
import json
import os
import sys
import threading
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

    def test_snapshot_reports_clock(self):
        ctl, _, _ = make(synced=False)
        self.assertFalse(ctl.snapshot()["clock_synced"])


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.link = FakeLink()
        self.ctl = server.Controller(self.link, cap=80, allow_drive=False, synced=lambda: True)
        page = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
        self.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(self.ctl, page))
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

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


if __name__ == "__main__":
    unittest.main()
