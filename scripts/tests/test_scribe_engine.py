import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.src.Worker.pipelines.transcription.scribe_engine import (
    MAX_FILE_BYTES,
    ScribeEngine,
    _raise_api_error,
    build_segments,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeEncoder:
    last_fields = None

    def __init__(self, fields):
        self.fields = fields
        self.len = 100
        self.content_type = "multipart/form-data; boundary=test"
        FakeEncoder.last_fields = fields


class FakeMonitor:
    def __init__(self, encoder, callback):
        self.len = encoder.len
        self.content_type = encoder.content_type
        self.bytes_read = 50
        callback(self)
        self.bytes_read = 100
        callback(self)


class ScribeEngineTests(unittest.TestCase):
    def test_build_segments_keeps_spacing_and_splits_at_sentence_end(self):
        result = build_segments(
            {
                "words": [
                    {"type": "word", "text": "Hello", "start": 0.0, "end": 0.4},
                    {"type": "spacing", "text": " "},
                    {"type": "word", "text": "world!", "start": 0.5, "end": 0.9},
                    {"type": "audio_event", "text": "(music)", "start": 1.0, "end": 1.2},
                    {"type": "word", "text": "下一句。", "start": 1.3, "end": 2.0},
                ]
            }
        )

        self.assertEqual(
            result,
            [
                {"start": 0.0, "end": 0.9, "text": "Hello world!"},
                {"start": 1.3, "end": 2.0, "text": "下一句。"},
            ],
        )

    def test_empty_or_untimed_response_has_no_segments(self):
        self.assertEqual(build_segments({"text": "hello"}), [])
        self.assertEqual(build_segments({"words": [{"type": "spacing", "text": " "}]}), [])

    def test_transcribe_streams_expected_fields_and_reports_phases(self):
        response = FakeResponse(
            payload={"words": [{"type": "word", "text": "Hello.", "start": 0.0, "end": 0.5}]}
        )
        events = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            audio = Path(tmp_dir) / "clip.wav"
            audio.write_bytes(b"RIFF-test")
            with patch(
                "app.src.Worker.pipelines.transcription.scribe_engine._load_multipart_classes",
                return_value=(FakeEncoder, FakeMonitor),
            ), patch("app.src.Worker.pipelines.transcription.scribe_engine.requests.post", return_value=response) as post:
                result = ScribeEngine().transcribe(
                    audio,
                    api_key="secret",
                    language="en",
                    progress_callback=events.append,
                )

        fields = FakeEncoder.last_fields
        self.assertEqual(fields["model_id"], "scribe_v2")
        self.assertEqual(fields["language_code"], "en")
        self.assertEqual(fields["tag_audio_events"], "false")
        self.assertEqual(fields["diarize"], "false")
        self.assertEqual(fields["timestamps_granularity"], "word")
        self.assertEqual(post.call_args.kwargs["headers"]["xi-api-key"], "secret")
        self.assertFalse(post.call_args.kwargs["allow_redirects"])
        self.assertEqual([event["stage"] for event in events], ["transcribe_upload", "transcribe_cloud", "transcribe"])
        self.assertEqual(result["segments"][0]["text"], "Hello.")

    def test_common_api_errors_are_actionable(self):
        expected = {
            401: "API Key",
            403: "IP 白名单",
            413: "文件体积",
            429: "额度不足",
            503: "暂时不可用",
        }
        for status, message in expected.items():
            with self.subTest(status=status), self.assertRaisesRegex(RuntimeError, message):
                _raise_api_error(FakeResponse(status))

    def test_file_over_three_gib_is_rejected_before_upload(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            audio = Path(tmp_dir) / "large.wav"
            with audio.open("wb") as file_obj:
                file_obj.truncate(MAX_FILE_BYTES + 1)
            with patch("app.src.Worker.pipelines.transcription.scribe_engine.requests.post") as post:
                with self.assertRaisesRegex(RuntimeError, "3GB"):
                    ScribeEngine().transcribe(audio, api_key="secret")
            post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
