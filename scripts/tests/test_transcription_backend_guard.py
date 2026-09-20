import unittest
from unittest.mock import patch

from app.src.Api.routes.transcriptions_handlers.params import (
    apply_transcription_form_params,
    validate_transcription_backend_guard,
)


class TranscriptionBackendGuardTests(unittest.TestCase):
    def test_unknown_backend_is_rejected(self):
        params, error = apply_transcription_form_params({"transcription_backend": "unknown"})

        self.assertIsNone(params)
        self.assertIn("不支持的转录引擎", error)

    def test_elevenlabs_requires_server_side_key(self):
        with patch(
            "app.src.Api.routes.transcriptions_handlers.params.get_elevenlabs_api_key",
            return_value="",
        ):
            error = validate_transcription_backend_guard({"transcription_backend": "elevenlabs"})

        self.assertIn("API Key", error)

    def test_installed_whisper_model_is_accepted(self):
        with patch(
            "app.src.Api.routes.transcriptions_handlers.params.build_whisper_model_entry",
            return_value={"installed": True},
        ):
            error = validate_transcription_backend_guard(
                {"transcription_backend": "whisper", "whisper_model": "small"}
            )

        self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
