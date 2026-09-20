import unittest

from app.src.Api.services.admin.transcription_catalog import build_whisper_model_entry, get_models_for_backend


class TranscriptionCatalogTests(unittest.TestCase):
    def test_standard_models_have_download_entries(self):
        model_ids = get_models_for_backend("whisper")

        self.assertEqual(
            model_ids,
            [
                "tiny.en", "tiny", "base.en", "base", "small.en", "small",
                "medium.en", "medium", "large-v1", "large-v2", "large-v3",
            ],
        )
        for model_id in model_ids:
            entry = build_whisper_model_entry(model_id)
            self.assertEqual(entry["model_id"], model_id)
            self.assertEqual(entry["download_files"][0]["name"], "model.bin")
            self.assertIn(f"faster-whisper-{model_id}", entry["download_files"][0]["url"])

    def test_large_v3_uses_its_json_vocabulary(self):
        entry = build_whisper_model_entry("large-v3")

        self.assertIn("vocabulary.json", entry["required_files"])


if __name__ == "__main__":
    unittest.main()
