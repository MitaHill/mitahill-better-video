import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.src.Worker.pipelines.transcription import whisper_engine
from app.src.Worker.pipelines.transcription.whisper_engine import WhisperEngine


class FakeModel:
    def __init__(self):
        self.args = None
        self.kwargs = None

    def transcribe(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        segments = iter([SimpleNamespace(start=0.0, end=2.5, text=" hello ")])
        return segments, SimpleNamespace(duration=2.5)


class FasterWhisperParameterTests(unittest.TestCase):
    def test_transcribe_passes_user_decode_options_to_faster_whisper(self):
        model = FakeModel()
        engine = WhisperEngine()
        engine._model = model
        engine._model_name = "large-v3"

        result = engine.transcribe(
            "/tmp/input.m4a",
            model_name="large-v3",
            language="en",
            temperature=0.4,
            beam_size=7,
            best_of=3,
        )

        self.assertEqual(model.args, ("/tmp/input.m4a",))
        self.assertEqual(
            model.kwargs,
            {
                "language": "en",
                "temperature": 0.4,
                "beam_size": 7,
                "best_of": 3,
            },
        )
        self.assertEqual(result["segments"], [{"start": 0.0, "end": 2.5, "text": "hello"}])

    def test_auto_language_is_forwarded_as_none(self):
        model = FakeModel()
        engine = WhisperEngine()
        engine._model = model
        engine._model_name = "large-v3"

        engine.transcribe("/tmp/input.m4a", model_name="large-v3", language="auto")

        self.assertIsNone(model.kwargs["language"])

    def test_each_model_uses_its_expected_feature_size(self):
        with patch.object(whisper_engine, "WhisperModel", return_value=SimpleNamespace()), patch.object(
            whisper_engine, "FeatureExtractor"
        ) as feature_extractor:
            whisper_engine.load_whisper_model("/tmp/tiny", "tiny")
            feature_extractor.assert_called_once_with(feature_size=80)

        with patch.object(whisper_engine, "WhisperModel", return_value=SimpleNamespace()), patch.object(
            whisper_engine, "FeatureExtractor"
        ) as feature_extractor:
            whisper_engine.load_whisper_model("/tmp/large-v3", "large-v3")
            feature_extractor.assert_called_once_with(feature_size=128)


if __name__ == "__main__":
    unittest.main()
