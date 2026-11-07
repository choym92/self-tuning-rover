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
                 "Hey Kalmanson": (False, ""), "": (False, "")}
        for text, want in cases.items():
            self.assertEqual(mind.split_wake(text), want, text)

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


if __name__ == "__main__":
    unittest.main()
