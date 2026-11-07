import array
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mind  # noqa: E402


def frame(level):
    return array.array("h", [level, -level] * (mind.FRAME // 2)).tobytes()


class SegmenterTests(unittest.TestCase):
    def test_utterance_ends_after_silence(self):
        seg = mind.Segmenter(noise_rms=400)                  # threshold 800
        quiet, loud = frame(300), frame(3000)
        out = [seg.feed(f) for f in [quiet] * 5 + [loud] * 20]
        self.assertFalse(any(d for d, _ in out))
        for _ in range(seg.silence_frames - 1):
            self.assertFalse(seg.feed(quiet)[0])
        done, pcm = seg.feed(quiet)
        self.assertTrue(done)
        self.assertEqual(len(pcm), (5 + 20 + seg.silence_frames) * mind.FRAME * 2)

    def test_nobody_speaks(self):
        seg = mind.Segmenter(noise_rms=400)
        res = [seg.feed(frame(300)) for _ in range(seg.start_frames)]
        self.assertEqual(res[-1], (True, None))

    def test_long_speech_is_cut(self):
        seg = mind.Segmenter(noise_rms=400, max_s=1.0)
        res = [seg.feed(frame(3000)) for _ in range(seg.max_frames)]
        self.assertTrue(res[-1][0])
        self.assertIsNotNone(res[-1][1])

    def test_threshold_has_a_floor(self):
        self.assertEqual(mind.Segmenter(noise_rms=10).threshold, 300.0)


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
