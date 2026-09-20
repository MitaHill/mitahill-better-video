import unittest
from unittest.mock import patch

from app.src.Worker.pipelines.transcription.engine import TranscriptionEngine


class FakeWhisper:
    def __init__(self):
        self.kwargs = None

    def transcribe(self, _path, **kwargs):
        self.kwargs = kwargs
        kwargs["progress_callback"](2.0, 4.0)
        return {"segments": []}

    def finalize_task(self):
        return None


class FakeScribe:
    def __init__(self):
        self.kwargs = None

    def transcribe(self, _path, **kwargs):
        self.kwargs = kwargs
        return {"segments": []}

    def finalize_task(self):
        return None


class TranscriptionEngineTests(unittest.TestCase):
    def test_whisper_progress_is_adapted(self):
        whisper = FakeWhisper()
        events = []
        engine = TranscriptionEngine(whisper_engine=whisper, scribe_engine=FakeScribe())

        engine.transcribe(
            "input.wav",
            options={"transcription_backend": "whisper", "whisper_model": "small"},
            progress_callback=events.append,
        )

        self.assertEqual(whisper.kwargs["model_name"], "small")
        self.assertEqual(events[0]["ratio"], 0.5)
        self.assertEqual(events[0]["unit_label"], "音频秒")

    def test_scribe_uses_server_side_key(self):
        scribe = FakeScribe()
        engine = TranscriptionEngine(whisper_engine=FakeWhisper(), scribe_engine=scribe)

        with patch("app.src.Worker.pipelines.transcription.engine.get_elevenlabs_api_key", return_value="server-key"):
            engine.transcribe(
                "input.wav",
                options={"transcription_backend": "elevenlabs", "language": "auto", "max_line_chars": 60},
            )

        self.assertEqual(scribe.kwargs["api_key"], "server-key")
        self.assertEqual(scribe.kwargs["max_line_chars"], 60)


if __name__ == "__main__":
    unittest.main()
