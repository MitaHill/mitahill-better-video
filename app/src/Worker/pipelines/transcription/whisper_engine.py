import logging
from pathlib import Path
from typing import Callable

import torch
from faster_whisper import WhisperModel
from faster_whisper.feature_extractor import FeatureExtractor

from app.src.Data.transcription_models import get_whisper_model

_WHISPER_ROOT = Path("/workspace/storage/models/transcription/whisper")
_MODEL_ID = "large-v3"

logger = logging.getLogger("TRANSCRIBE_ENGINE")


def load_whisper_model(model_path: Path, model_name: str = _MODEL_ID):
    model = WhisperModel(str(model_path), device="cuda", compute_type="float16")

    model_info = get_whisper_model(model_name) or {}
    # Faster-Whisper 0.9 does not read the model feature size from config
    model.feature_extractor = FeatureExtractor(feature_size=int(model_info.get("feature_size") or 80))
    return model


class WhisperEngine:
    def __init__(self):
        self._model_name = ""
        self._model = None
        _WHISPER_ROOT.mkdir(parents=True, exist_ok=True)

    def _model_path(self, model_name: str) -> Path:
        model_info = get_whisper_model(model_name)
        if not model_info:
            raise RuntimeError(f"Unsupported Whisper model: {model_name}")
        model_path = _WHISPER_ROOT / model_name
        required_files = ("model.bin", "config.json", "tokenizer.json", model_info["vocabulary"])
        missing_files = [name for name in required_files if not (model_path / name).is_file()]
        if missing_files:
            raise RuntimeError(
                f"Whisper model not downloaded: {model_name} (missing: {', '.join(missing_files)})"
            )
        return model_path

    def _load(self, backend: str, model_name: str):
        safe_backend = (backend or "whisper").strip().lower()
        safe_model = (model_name or _MODEL_ID).strip().lower()
        if safe_backend != "whisper":
            raise ValueError(f"unsupported transcription backend: {safe_backend}")
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA not available. NVIDIA GPU required for transcription.")

        model_path = self._model_path(safe_model)
        logger.info("Loading Faster-Whisper model %s on CUDA with float16", safe_model)
        self._model = load_whisper_model(model_path, safe_model)
        self._model_name = safe_model

    def release(self):
        if self._model is None:
            return
        self._model = None
        self._model_name = ""

    def finalize_task(self):
        self.release()

    def transcribe(
        self,
        media_path,
        *,
        backend="whisper",
        model_name=_MODEL_ID,
        language="auto",
        temperature=0.0,
        beam_size=5,
        best_of=5,
        task_id="",
        progress_callback: Callable[[float, float], None] = None,
    ):
        safe_backend = (backend or "whisper").strip().lower()
        safe_model = (model_name or _MODEL_ID).strip().lower()

        if self._model is None or self._model_name != safe_model:
            self._load(safe_backend, safe_model)
        model = self._model

        language_value = (language or "auto").strip().lower()
        segments, info = model.transcribe(
            str(media_path),
            language=None if language_value == "auto" else language_value,
            temperature=max(0.0, float(temperature or 0.0)),
            beam_size=max(1, int(beam_size or 1)),
            best_of=max(1, int(best_of or 1)),
        )
        duration = max(float(getattr(info, "duration", 0.0) or 0.0), 0.01)
        result = []
        for segment in segments:
            result.append(
                {
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "text": str(segment.text or "").strip(),
                }
            )
            if progress_callback:
                progress_callback(min(float(segment.end), duration), duration)
        if progress_callback:
            progress_callback(duration, duration)
        return {"segments": result}


ENGINE = WhisperEngine()
