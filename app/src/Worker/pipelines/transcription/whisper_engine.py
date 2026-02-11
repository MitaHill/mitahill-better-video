import threading
from pathlib import Path
from typing import Dict, Iterable, List

import torch


_OPENAI_ROOT = Path("/workspace/storage/models/transcription/whisper-openai")
_FASTER_ROOT = Path("/workspace/storage/models/transcription/faster-whisper")
_OPENAI_MODEL_ALIASES = {
    "large-v3-turbo": "turbo",
    "large": "large-v2",
}


class WhisperEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._backend = ""
        self._model_name = ""
        self._model = None
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        _OPENAI_ROOT.mkdir(parents=True, exist_ok=True)
        _FASTER_ROOT.mkdir(parents=True, exist_ok=True)

    def _resolve_openai_model_ref(self, model_name: str):
        safe_model = (model_name or "medium").strip().lower()
        alias = _OPENAI_MODEL_ALIASES.get(safe_model, safe_model)
        candidates = [f"{safe_model}.pt"]
        if alias != safe_model:
            candidates.append(f"{alias}.pt")
        for name in candidates:
            path = _OPENAI_ROOT / name
            if path.exists():
                return str(path)
        return alias

    def _resolve_faster_model_ref(self, model_name: str):
        safe_model = (model_name or "medium").strip().lower()
        local_dir = _FASTER_ROOT / safe_model
        if local_dir.exists():
            return str(local_dir)
        return safe_model

    def _load(self, backend: str, model_name: str):
        safe_backend = (backend or "whisper").strip().lower()
        safe_model = (model_name or "medium").strip().lower()

        if safe_backend == "whisper":
            import whisper

            model_ref = self._resolve_openai_model_ref(safe_model)
            self._model = whisper.load_model(model_ref, device=self._device, download_root=str(_OPENAI_ROOT))
        elif safe_backend == "faster_whisper":
            from faster_whisper import WhisperModel

            model_ref = self._resolve_faster_model_ref(safe_model)
            compute_type = "float16" if self._device == "cuda" else "int8"
            self._model = WhisperModel(model_ref, device=self._device, compute_type=compute_type)
        else:
            raise ValueError(f"unsupported transcription backend: {safe_backend}")

        self._backend = safe_backend
        self._model_name = safe_model

    def _faster_segments_to_dict(self, segments: Iterable) -> Dict:
        out_segments: List[Dict] = []
        for seg in segments:
            try:
                out_segments.append(
                    {
                        "start": float(getattr(seg, "start", 0.0) or 0.0),
                        "end": float(getattr(seg, "end", 0.0) or 0.0),
                        "text": str(getattr(seg, "text", "") or "").strip(),
                    }
                )
            except Exception:
                continue
        return {"segments": out_segments}

    def transcribe(
        self,
        media_path,
        *,
        backend="whisper",
        model_name="medium",
        language="auto",
        temperature=0.0,
        beam_size=5,
        best_of=5,
    ):
        safe_backend = (backend or "whisper").strip().lower()
        safe_model = (model_name or "medium").strip().lower()
        with self._lock:
            if self._model is None or self._model_name != safe_model or self._backend != safe_backend:
                self._load(safe_backend, safe_model)
            model = self._model

        language_value = (language or "auto").strip().lower()
        if safe_backend == "whisper":
            options = {
                "task": "transcribe",
                "temperature": max(0.0, float(temperature or 0.0)),
                "beam_size": max(1, int(beam_size or 1)),
                "best_of": max(1, int(best_of or 1)),
                "condition_on_previous_text": False,
                "verbose": False,
                "fp16": self._device == "cuda",
            }
            if language_value and language_value != "auto":
                options["language"] = language_value
            return model.transcribe(str(media_path), **options)

        if safe_backend == "faster_whisper":
            options = {
                "beam_size": max(1, int(beam_size or 1)),
                "best_of": max(1, int(best_of or 1)),
                "temperature": max(0.0, float(temperature or 0.0)),
            }
            if language_value and language_value != "auto":
                options["language"] = language_value
            segments, _info = model.transcribe(str(media_path), **options)
            return self._faster_segments_to_dict(segments)

        raise ValueError(f"unsupported transcription backend: {safe_backend}")


ENGINE = WhisperEngine()
