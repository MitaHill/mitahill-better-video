import threading
from pathlib import Path

import torch


class WhisperEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._model_name = None
        self._model = None
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._download_root = Path("/workspace/storage/models/whisper")
        self._download_root.mkdir(parents=True, exist_ok=True)

    def _load(self, model_name):
        import whisper

        self._model = whisper.load_model(model_name, device=self._device, download_root=str(self._download_root))
        self._model_name = model_name

    def transcribe(
        self,
        media_path,
        *,
        model_name="medium",
        language="auto",
        temperature=0.0,
        beam_size=5,
        best_of=5,
    ):
        safe_model = (model_name or "medium").strip().lower()
        with self._lock:
            if self._model is None or self._model_name != safe_model:
                self._load(safe_model)
            model = self._model

        options = {
            "task": "transcribe",
            "temperature": max(0.0, float(temperature or 0.0)),
            "beam_size": max(1, int(beam_size or 1)),
            "best_of": max(1, int(best_of or 1)),
            "condition_on_previous_text": False,
            "verbose": False,
            "fp16": self._device == "cuda",
        }
        language_value = (language or "auto").strip().lower()
        if language_value and language_value != "auto":
            options["language"] = language_value

        return model.transcribe(str(media_path), **options)


ENGINE = WhisperEngine()
