import unittest

from app.src.Worker.pipelines.transcription.formatting import (
    format_segment_text,
    segments_to_srt,
)
from app.src.Worker.pipelines.transcription.translation.segments import (
    build_bilingual_segments,
)


class FormatSegmentTextTests(unittest.TestCase):
    def test_single_line_behaviour_unchanged(self):
        self.assertEqual(format_segment_text("  hello   world ", 42), "hello world")

    def test_single_line_still_wraps_at_width(self):
        self.assertEqual(format_segment_text("aaa bbb ccc", 7), "aaa bbb\nccc")

    def test_zero_width_disables_wrapping(self):
        self.assertEqual(format_segment_text("aaa bbb ccc", 0), "aaa bbb ccc")

    def test_line_break_is_preserved(self):
        self.assertEqual(format_segment_text("译文\n原文", 42), "译文\n原文")

    def test_each_line_wraps_independently(self):
        # 第一行需要折行，第二行不需要，两边不能互相串行。
        result = format_segment_text("aaa bbb ccc\nddd", 7)
        self.assertEqual(result, "aaa bbb\nccc\nddd")

    def test_blank_lines_are_dropped(self):
        self.assertEqual(format_segment_text("译文\n   \n原文", 42), "译文\n原文")

    def test_empty_input_returns_empty(self):
        self.assertEqual(format_segment_text("   ", 42), "")
        self.assertEqual(format_segment_text(None, 42), "")


class BilingualSegmentTests(unittest.TestCase):
    def test_bilingual_text_uses_real_line_break(self):
        merged = build_bilingual_segments(
            [{"start": 0.0, "end": 1.0, "text": "hello world"}],
            [{"start": 0.0, "end": 1.0, "text": "你好世界"}],
        )
        text = merged[0]["text"]
        self.assertEqual(text, "你好世界\nhello world")
        self.assertNotIn("\\n", text)

    def test_missing_translation_falls_back_to_single_line(self):
        merged = build_bilingual_segments(
            [{"start": 0.0, "end": 1.0, "text": "hello"}],
            [],
        )
        self.assertEqual(merged[0]["text"], "hello")

    def test_bilingual_segment_occupies_two_lines_in_srt(self):
        merged = build_bilingual_segments(
            [{"start": 0.0, "end": 1.5, "text": "hello world"}],
            [{"start": 0.0, "end": 1.5, "text": "你好世界"}],
        )
        srt = segments_to_srt(merged, max_line_chars=42)
        self.assertIn("你好世界\nhello world", srt)
        self.assertNotIn("\\n", srt)
        body = srt.strip().splitlines()
        self.assertEqual(body[0], "1")
        self.assertEqual(body[1], "00:00:00,000 --> 00:00:01,500")
        self.assertEqual(body[2], "你好世界")
        self.assertEqual(body[3], "hello world")


if __name__ == "__main__":
    unittest.main()
