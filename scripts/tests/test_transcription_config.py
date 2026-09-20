import copy
import unittest
from unittest.mock import patch

from app.src.Api.services.admin import transcription_config


class TranscriptionConfigTests(unittest.TestCase):
    def setUp(self):
        self.saved = transcription_config.default_transcription_config()
        self.get_patch = patch.object(
            transcription_config.db_transcription,
            "get_transcription_config",
            side_effect=lambda _factory: copy.deepcopy(self.saved),
        )
        self.set_patch = patch.object(
            transcription_config.db_transcription,
            "set_transcription_config",
            side_effect=self._save,
        )
        self.get_patch.start()
        self.set_patch.start()

    def tearDown(self):
        self.get_patch.stop()
        self.set_patch.stop()

    def _save(self, value):
        self.saved = copy.deepcopy(value)

    def test_public_config_never_returns_api_key(self):
        transcription_config.update_transcription_config({"elevenlabs": {"api_key": "secret"}})

        public = transcription_config.get_public_transcription_config()

        self.assertTrue(public["elevenlabs"]["api_key_configured"])
        self.assertNotIn("api_key", public["elevenlabs"])

    def test_blank_key_preserves_existing_value_and_clear_is_explicit(self):
        transcription_config.update_transcription_config({"elevenlabs": {"api_key": "secret"}})
        transcription_config.update_transcription_config({"elevenlabs": {"api_key": ""}})
        self.assertEqual(transcription_config.get_elevenlabs_api_key(), "secret")

        transcription_config.update_transcription_config({"elevenlabs": {"clear_api_key": True}})
        self.assertEqual(transcription_config.get_elevenlabs_api_key(), "")


if __name__ == "__main__":
    unittest.main()
