import array
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mind  # noqa: E402


def frame(level):
    return array.array("h", [level, -level] * (mind.FRAME // 2)).tobytes()


class FakeVad:
    """Speech while frames are loud; closes a segment after `quiet_needed` quiet frames."""
    def __init__(self, quiet_needed=5):
        self.quiet_needed, self.segments = quiet_needed, 0
        self.reset()

    def reset(self):
        self.speaking, self.quiet = False, 0

    def accept_waveform(self, samples):
        loud = max(abs(x) for x in samples) > 0.05
        if loud:
            self.speaking, self.quiet = True, 0
        elif self.speaking:
            self.quiet += 1
            if self.quiet >= self.quiet_needed:
                self.speaking, self.segments = False, self.segments + 1

    def is_speech_detected(self):
        return self.speaking

    def empty(self):
        return self.segments == 0

    def pop(self):
        self.segments -= 1


class EndpointerTests(unittest.TestCase):
    def test_request_ends_when_the_vad_closes_a_segment(self):
        ep = mind.Endpointer(FakeVad())
        quiet, loud = frame(300), frame(6000)
        res = [ep.feed(f) for f in [quiet] * 3 + [loud] * 10 + [quiet] * 4]
        self.assertFalse(any(d for d, _ in res))
        done, pcm = ep.feed(quiet)
        self.assertTrue(done)
        self.assertEqual(len(pcm), (3 + 10 + 5) * mind.FRAME * 2)   # includes the audio before speech

    def test_nobody_speaks(self):
        ep = mind.Endpointer(FakeVad(), start_s=0.3)
        res = [ep.feed(frame(300)) for _ in range(ep.start_frames)]
        self.assertEqual(res[-1], (True, None))

    def test_long_speech_is_cut(self):
        ep = mind.Endpointer(FakeVad(), max_s=0.6)
        res = [ep.feed(frame(6000)) for _ in range(ep.max_frames)]
        self.assertTrue(res[-1][0])
        self.assertIsNotNone(res[-1][1])

    def test_floats_scale(self):
        self.assertEqual(mind.floats(array.array("h", [16384, -32768]).tobytes()), [0.5, -1.0])


class WakeTests(unittest.TestCase):
    def test_name_at_the_start_wakes(self):
        cases = {"Hey Kalman.": (True, ""), " Hey Kalman, what time is it?": (True, "what time is it?"),
                 "Kalman.": (True, ""), "OK Kalman stop": (True, "stop"), "hey, kalman, how's your battery?": (True, "how's your battery?"),
                 "How is the weather?": (False, ""), "I told Kalman yesterday.": (False, ""), "Hey Google.": (False, ""),
                 "Hey Kalmanson": (False, ""), "": (False, ""),
                 "Kalman's a huge robot. Kalman.": (False, ""), "Kalman is a small robot. Hey Kalman.": (False, "")}
        for text, want in cases.items():
            self.assertEqual(mind.split_wake(text), want, text)

    def test_barge_in(self):
        speaking = "Honestly, my battery is low, so Kalman is feeling sleepy today."
        cases = {"Kalman, stop.": (True, ""), "Stop!": (True, ""), "Wait, Kalman.": (True, ""),
                 "Kalman, what time is it?": (True, "what time is it?"),
                 "my battery is low so Kalman": (False, ""),          # his own voice coming back
                 "Kalman is feeling sleepy": (False, ""),            # echo that happens to start with the name
                 "How is the weather?": (True, "How is the weather?"),       # a real sentence over him
                 "Tell me about the cat instead.": (True, "Tell me about the cat instead."),
                 "Uh huh.": (False, ""), "Thank you.": (False, ""), "": (False, "")}
        for heard, want in cases.items():
            self.assertEqual(mind.barge_in(heard, speaking), want, heard)

    def test_double_talk_learns_echo_then_hears_paul(self):
        dt = mind.DoubleTalk(ratio=2.0, hold_s=0.09, lag_s=0.06, min_level=900, warm_s=0)
        env = [4000.0] * 100                    # Kalman speaking steadily
        dt.reset(env)
        for _ in range(40):                     # alone: mic hears 0.5 x playback
            self.assertFalse(dt.feed(2000.0))
        self.assertAlmostEqual(dt.gain, 0.5, places=2)
        for _ in range(200):                    # quiet stretches in his own speech must not drag it down
            dt.feed(800.0)
        dt.reset(env)
        for _ in range(40):
            dt.feed(2000.0)
        self.assertGreaterEqual(dt.gain, 0.5)
        self.assertFalse(dt.feed(3000.0))       # a little louder: not enough
        hits = [dt.feed(6000.0) for _ in range(3)]   # Paul over him: 3x the echo for 3 frames
        self.assertEqual(hits, [False, False, True])

    def test_double_talk_in_a_pause(self):
        dt = mind.DoubleTalk(ratio=2.0, hold_s=0.09, lag_s=0.06, min_level=900, gain=0.5, warm_s=0)
        dt.reset([4000.0] * 10 + [0.0] * 20)    # Kalman pauses after 0.3 s
        for _ in range(10):                     # under his own voice a normal voice is not enough
            self.assertFalse(dt.feed(1500.0))
        # the 2-frame window still holds his voice for 2 frames, then the same level is heard in the gap
        self.assertEqual([dt.feed(1500.0) for _ in range(5)], [False, False, False, False, True])

    def test_double_talk_ignores_the_start_of_playback(self):
        dt = mind.DoubleTalk(ratio=2.0, hold_s=0.09, lag_s=0.06, min_level=900, warm_s=0.3)
        dt.reset([4000.0] * 40)
        self.assertFalse(any(dt.feed(100.0) for _ in range(dt.warm)))   # silence before the echo arrives
        self.assertIsNone(dt.gain)                                      # nothing learned from it

    def test_strip_echo(self):
        spoken = "Yeah, I do. The cat walks past a lot."
        self.assertEqual(mind.strip_echo("Yeah.", spoken), "")
        self.assertEqual(mind.strip_echo("Yeah, I do. What time is it?", spoken), "What time is it?")
        self.assertEqual(mind.strip_echo("Stop talking about the cat", spoken), "Stop talking about the cat")

    def test_envelope_of_a_wav(self):
        env = mind.play_envelope(mind.tone(seconds=0.3))
        self.assertTrue(9 <= len(env) <= 10)
        self.assertGreater(max(env), 1000)

    def test_echo_share(self):
        self.assertTrue(mind.is_echo("battery is low", "My battery is low."))
        self.assertFalse(mind.is_echo("stop talking now", "My battery is low."))

    def test_end_phrases(self):
        for text, end in (("Thank you.", True), ("Thanks, Kalman!", True), ("OK stop.", True), ("Go to sleep.", True),
                          ("That's all.", True), ("Never mind", True), ("Bye!", True),
                          ("Stop the music and tell me a long story about your day please", False),
                          ("How's your battery?", False), ("Can you stop worrying?", False), ("", False)):
            self.assertEqual(mind.is_end(text), end, text)

    def test_gate_cuts_a_phrase_with_pre_roll(self):
        gate = mind.SpeechGate(FakeVad(quiet_needed=5), pre_s=0.09, min_s=0.2)
        quiet, loud = frame(300), frame(6000)
        out = [gate.feed(f) for f in [quiet] * 6 + [loud] * 10 + [quiet] * 5]
        got = [o for o in out if o]
        self.assertEqual(len(got), 1)
        self.assertEqual(len(got[0]), (2 + 10 + 5) * mind.FRAME * 2)   # 3 pre-roll frames minus the one VAD saw as speech

    def test_gate_drops_clicks(self):
        gate = mind.SpeechGate(FakeVad(quiet_needed=2), pre_s=0.03, min_s=0.4)
        out = [gate.feed(f) for f in [frame(300)] * 3 + [frame(6000)] + [frame(300)] * 4]
        self.assertFalse(any(out))


class TextTests(unittest.TestCase):
    def test_sentences_stream_out_as_they_end(self):
        pieces = ["Hmm. I", " don't know", "! Maybe the", " cat? ", "No"]
        self.assertEqual(list(mind.sentences(iter(pieces))), ["Hmm.", "I don't know!", "Maybe the cat?", "No"])

    def test_long_first_sentence_starts_at_its_first_comma(self):
        pieces = ["The battery is getting low", ", so I feel", " sleepy. Also, the cat."]
        self.assertEqual(list(mind.sentences(iter(pieces))), ["The battery is getting low,", "so I feel sleepy.", "Also, the cat."])

    def test_korean_sentences(self):
        self.assertEqual(list(mind.sentences(iter(["음, 그냥 그래. ", "너는?"]))), ["음, 그냥 그래.", "너는?"])

    def test_sse_parsing(self):
        lines = [b'data: {"choices":[{"delta":{"role":"assistant"}}]}', b"",
                 b'data: {"choices":[{"delta":{"content":"Hi"}}]}', b": keep-alive",
                 b'data: {"choices":[{"delta":{"content":" there."}}]}', b"data: [DONE]",
                 b'data: {"choices":[{"delta":{"content":"ignored"}}]}']
        self.assertEqual("".join(mind.sse_text(lines)), "Hi there.")

    def test_multipart_contains_fields_and_file(self):
        body, ctype = mind.multipart({"language": "en", "prompt": "Hey Kalman."}, b"RIFFdata")
        boundary = ctype.split("boundary=")[1]
        self.assertIn(b'name="prompt"\r\n\r\nHey Kalman.', body)
        self.assertIn(b"RIFFdata", body)
        self.assertTrue(body.endswith(("--" + boundary + "--\r\n").encode()))

    def test_noise_and_invented_lines_are_not_speech(self):
        for text, speech in (("[BEEP]", False), (" [BLANK_AUDIO]", False), ("(cough) [Music]", False),
                             ("Thank you for watching that well.", False), ("Thanks for watching!", False),
                             ("Thank you.", False), (" you", False), ("Please subscribe to my channel", False),
                             ("Hey Kalman, stop.", True), ("Thank you, Kalman, that was funny.", True),
                             ("Did it work?", True), ("How's your battery?", True)):
            self.assertEqual(mind.is_speech(text), speech, text)

    def test_tone_is_a_wav(self):
        self.assertEqual(mind.tone()[:4], b"RIFF")


class JournalTests(unittest.TestCase):
    def test_one_json_line_per_event(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            j = mind.Journal(d)
            j.write("heard", text="Hey Kalman, stop.", ms=120)
            j.write("reply", text="음.", ms=300)
            (name,) = os.listdir(d)
            lines = open(os.path.join(d, name), encoding="utf-8").read().splitlines()
            self.assertEqual([json.loads(x)["kind"] for x in lines], ["heard", "reply"])
            self.assertEqual(json.loads(lines[1])["text"], "음.")


class ConfigTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        seed = os.path.join(self.tmp.name, "seed")
        os.makedirs(seed)
        for k, v in (("identity", "You are Kalman, a small robot."), ("style", "Short sentences."), ("rules", "Be honest."),
                     ("summary", "Summarise."), ("day", "Summarise the day.")):
            with open(os.path.join(seed, k + ".md"), "w", encoding="utf-8") as f:
                f.write(v + "\n")
        self.cfg = mind.Config(os.path.join(self.tmp.name, "config"), seed)

    def tearDown(self):
        self.tmp.cleanup()

    def test_parts_seeded_then_edited(self):
        self.assertEqual(self.cfg.parts()["identity"], "You are Kalman, a small robot.")
        import time as _t
        _t.sleep(0.01)
        self.cfg.write_part("rules", "Never mention the battery unless asked.")
        self.assertEqual(self.cfg.parts()["rules"], "Never mention the battery unless asked.")
        with self.assertRaises(ValueError):
            self.cfg.write_part("tools", "x")
        with self.assertRaises(ValueError):
            self.cfg.write_part("style", "x" * 5000)

    def test_settings_defaults_ranges_and_types(self):
        self.assertEqual(self.cfg.settings()["follow_s"], 8.0)
        out = self.cfg.write_settings({"follow_s": "12", "max_tokens": 80})
        self.assertEqual((out["follow_s"], out["max_tokens"]), (12.0, 80))
        self.assertEqual(self.cfg.settings()["max_tokens"], 80)
        for bad in ({"follow_s": 99}, {"nope": 1}, {"temperature": "hot"}):
            with self.assertRaises(ValueError):
                self.cfg.write_settings(bad)

    def test_messages_layer_parts_state_and_history(self):
        import types
        m = mind.Mind.__new__(mind.Mind)
        m.cfg = self.cfg
        m.a = types.SimpleNamespace(control="http://127.0.0.1:9")   # rover-control unreachable: state has only the time
        m.convo_until = 0.0
        m.history = mind.deque([{"role": "user", "content": str(i)} for i in range(10)], maxlen=40)
        m.journal = mind.Journal(os.path.join(self.tmp.name, "journal"))
        m.memory = mind.Memory(m.journal.folder, m.journal.write, None, self.cfg.memory_prompts)
        self.cfg.write_settings({"history_messages": 2})
        msgs = m.messages("How are you?")
        system = msgs[0]["content"].split("\n\n")
        self.assertEqual(system[:3], ["You are Kalman, a small robot.", "Short sentences.", "Be honest."])
        self.assertTrue(system[3].startswith("Right now: "))
        self.assertEqual(system[4], "Answer in English.")
        self.assertEqual([x["content"] for x in msgs[1:]], ["8", "9", "How are you?"])
        self.assertIn("반말", m.messages("배고파?")[0]["content"])
        # a summary of a finished session from today joins the system message, labelled as possibly misheard
        sid = mind.datetime.now().strftime("s%Y%m%d-0905")
        m.journal.write("session_summary", session=sid, day=mind.datetime.now().strftime("%Y-%m-%d"), text="Talked about the cat.")
        system = m.messages("How are you?")[0]["content"].split("\n\n")
        self.assertTrue(system[3].startswith("Earlier today"))
        self.assertIn("- 09:05 Talked about the cat.", system[3])
        self.assertTrue(system[4].startswith("Right now: "))

    def test_sessions_tag_events_and_scope_the_prompt_history(self):
        m = mind.Mind.__new__(mind.Mind)
        m.journal = mind.Journal(os.path.join(self.tmp.name, "journal"))
        m.history = mind.deque([{"role": "user", "content": "old"}], maxlen=40)
        m.convo_until = 0.0
        m.speaking = False
        m.play = lambda *a, **k: True
        m.memory = mind.Memory(m.journal.folder, m.journal.write, None, None)
        m.begin_session()
        first = m.journal.session
        self.assertTrue(first.startswith("s"))
        self.assertEqual(list(m.history), [])                     # the prompt starts clean...
        m.journal.write("heard", text="Hi")
        m.end_conversation("quiet")
        self.assertEqual(m.journal.session, first)                 # a short pause keeps the session
        m.end_session("quiet")
        self.assertIsNone(m.journal.session)
        self.assertTrue(m.memory.nudged.is_set())                  # the summariser is woken
        m.journal.write("heard", text="outside a session")
        events = [json.loads(l) for f in os.listdir(m.journal.folder) for l in open(os.path.join(m.journal.folder, f), encoding="utf-8")]
        self.assertEqual([e.get("session") for e in events], [first, first, first, first, None])   # ...the journal keeps everything
        self.assertEqual([e["kind"] for e in events], ["session_start", "heard", "conversation_end", "session_end", "heard"])

    def test_recent_journal_keeps_conversation_events(self):
        j = mind.Journal(os.path.join(self.tmp.name, "journal"))
        j.write("start", mic="x")
        j.write("heard", text="Hi")
        j.write("while_speaking", text="x")
        j.write("reply", text="Hey.")
        self.assertEqual([e["kind"] for e in mind.recent_journal(j.folder)], ["heard", "reply"])


class MemoryTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.j = mind.Journal(os.path.join(self.tmp.name, "journal"))
        self.asked = []

        def ask(system, user):
            self.asked.append((system, user))
            return " summary %d " % len(self.asked)
        self.mem = mind.Memory(self.j.folder, self.j.write, ask, lambda: {"summary": "S", "day": "D"})

    def tearDown(self):
        self.tmp.cleanup()

    def events(self):
        return [json.loads(l) for f in sorted(os.listdir(self.j.folder)) for l in open(os.path.join(self.j.folder, f), encoding="utf-8")]

    def talk(self, sid, heard, reply, end=True):
        self.j.session = sid
        self.j.write("session_start")
        self.j.write("reply", heard=heard, text=reply)
        if end:
            self.j.write("session_end", reason="quiet")
        self.j.session = None

    def test_closed_sessions_are_summarised_once_from_what_was_said(self):
        self.talk("s20261107-090500", "My sister visits Sunday.", "Nice!")
        self.talk("s20261107-100000", "Hi", "Hey.", end=False)        # still open: not yet
        self.j.session = "s20261107-110000"; self.j.write("session_start"); self.j.write("session_end"); self.j.session = None  # nothing said
        self.mem.catch_up(today="2026-11-07")
        self.assertEqual(self.asked, [("S", "Paul: My sister visits Sunday.\nKalman: Nice!")])
        summ = [e for e in self.events() if e["kind"] == "session_summary"]
        self.assertEqual([(e["session"], e["day"], e["text"]) for e in summ], [("s20261107-090500", "2026-11-07", "summary 1")])
        self.mem.catch_up(today="2026-11-07")
        self.assertEqual(len(self.asked), 1)                                   # never twice, and no day summary today
        self.assertEqual(self.mem.earlier_today("s20261107-100000", today="2026-11-07"), [("09:05", "summary 1")])
        self.assertEqual(self.mem.earlier_today("s20261107-090500", today="2026-11-07"), [])   # not its own

    def test_a_finished_day_gets_one_summary_after_its_sessions(self):
        self.talk("s20261107-090500", "A", "a")
        self.talk("s20261107-210000", "B", "b")
        self.mem.catch_up(today="2026-11-08")
        self.assertEqual([a[0] for a in self.asked], ["S", "S", "D"])
        self.assertEqual(self.asked[2][1], "09:05 summary 1\n\n21:00 summary 2")
        day = [e for e in self.events() if e["kind"] == "day_summary"]
        self.assertEqual([(e["day"], e["text"], "session" in e) for e in day], [("2026-11-07", "summary 3", False)])
        self.mem.catch_up(today="2026-11-08")
        self.assertEqual(len(self.asked), 3)

    def test_a_restart_closes_the_open_session_so_it_is_summarised(self):
        self.talk("s20261107-090500", "A", "a", end=False)
        self.mem.close_dangling()
        self.mem.close_dangling()
        ends = [e for e in self.events() if e["kind"] == "session_end"]
        self.assertEqual([(e["session"], e["reason"]) for e in ends], [("s20261107-090500", "restart")])

    def test_model_offline_is_logged_once_and_retried(self):
        self.talk("s20261107-090500", "A", "a")
        def down(system, user):
            raise OSError("connection refused")
        self.mem.ask = down
        for _ in range(2):
            try:
                self.mem.catch_up(today="2026-11-07")
            except OSError:
                pass
        self.assertEqual(self.mem.pending(today="2026-11-07")[0], ["s20261107-090500"])


class KoreanTests(unittest.TestCase):
    def test_wake_end_and_invented_lines_in_korean(self):
        self.assertEqual(mind.split_wake("헤이 칼만, 오늘 기분 어때?"), (True, "오늘 기분 어때?"))
        self.assertEqual(mind.split_wake("칼만아 배고파?"), (True, "배고파?"))
        self.assertEqual(mind.split_wake("칼만"), (True, ""))
        self.assertEqual(mind.split_wake("칼만은?"), (True, ""))
        self.assertEqual(mind.split_wake("칼만필터 공부했어"), (False, ""))
        self.assertEqual(mind.split_wake("Hey Kalman, what time is it?"), (True, "what time is it?"))
        for text, end in (("고마워", True), ("그만!", True), ("잘 자", True), ("고마워 근데 하나만 더 물어볼게 오늘 날씨는 어때", False),
                          ("배고파?", False)):
            self.assertEqual(mind.is_end(text), end, text)
        for text in ("시청해 주셔서 감사합니다.", "구독과 좋아요 부탁드립니다", "MBC 뉴스 이덕영입니다."):
            self.assertFalse(mind.is_speech(text), text)
        self.assertTrue(mind.is_speech("오늘 뭐 했어?"))


if __name__ == "__main__":
    unittest.main()
