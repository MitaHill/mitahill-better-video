import importlib
import logging
import threading
from pathlib import Path
from typing import Callable

import torch
import whisper

from app.src.Worker.gpu_model_coordinator import is_cuda_oom, prepare_model_load, register_release_hook


_WHISPER_ROOT = Path("/workspace/storage/models/transcription/whisper")

logger = logging.getLogger("TRANSCRIBE_ENGINE")
whisper_transcribe = importlib.import_module("whisper.transcribe")


class WhisperEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._backend = ""
        self._model_name = ""
        self._model_backend_device = ""
        self._model = None
        self._device = "cuda"
        self._fp16 = False
        _WHISPER_ROOT.mkdir(parents=True, exist_ok=True)
        register_release_hook("whisper", self.release)

    def _resolve_fp16(self) -> bool:
        return torch.cuda.is_available()

    def _require_downloaded_model(self, model_name: str):
        urls = getattr(whisper, "_MODELS", {}) or {}
        url = urls.get(model_name)
        if not url:
            raise RuntimeError(f"Unsupported Whisper model: {model_name}")
        filename = str(url).rstrip("/").split("/")[-1] or f"{model_name}.pt"
        model_path = _WHISPER_ROOT / filename
        if not model_path.exists():
            raise RuntimeError(f"Whisper model not downloaded: {model_name} ({model_path})")

    def _load(self, backend: str, model_name: str):
        safe_backend = (backend or "whisper").strip().lower()
        safe_model = (model_name or "medium").strip().lower()

        if safe_backend != "whisper":
            raise ValueError(f"unsupported transcription backend: {safe_backend}")
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA not available. NVIDIA GPU required for transcription.")
        self._require_downloaded_model(safe_model)

        self._device = "cuda"
        self._fp16 = self._resolve_fp16()
        logger.info("Loading OpenAI Whisper model %s on %s with fp16=%s", safe_model, self._device, self._fp16)
        self._model = whisper.load_model(safe_model, device=self._device, download_root=str(_WHISPER_ROOT))
        self._model_backend_device = self._device

        self._backend = safe_backend
        self._model_name = safe_model

    def release(self):
        with self._lock:
            if self._model is None:
                return
            self._model = None
            self._model_backend_device = ""
            logger.info("Whisper model released from GPU memory.")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _offload_to_cpu(self):
        self.release()

    def finalize_task(self):
        self._offload_to_cpu()

    def _transcribe_with_progress(self, model, media_path, options, progress_callback=None):
        if not progress_callback:
            return model.transcribe(str(media_path), **options)

        tqdm_module = getattr(whisper_transcribe, "tqdm", None)
        original_tqdm = getattr(tqdm_module, "tqdm", None)
        if not original_tqdm:
            return model.transcribe(str(media_path), **options)

        class ProgressTqdm:
            def __init__(self, *args, **kwargs):
                self._bar = original_tqdm(*args, **kwargs)
                self.total = int(kwargs.get("total") or getattr(self._bar, "total", 0) or 0)
                self.n = 0
                if self.total > 0:
                    progress_callback(0, self.total)

            def __enter__(self):
                self._bar.__enter__()
                return self

            def __exit__(self, exc_type, exc, tb):
                return self._bar.__exit__(exc_type, exc, tb)

            def update(self, value=1):
                self.n = max(0, min(self.total, self.n + int(value or 0)))
                if self.total > 0:
                    progress_callback(self.n, self.total)
                return self._bar.update(value)

            def __getattr__(self, name):
                return getattr(self._bar, name)

        tqdm_module.tqdm = ProgressTqdm
        try:
            return model.transcribe(str(media_path), **options)
        finally:
            tqdm_module.tqdm = original_tqdm

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
        task_id="",
        progress_callback: Callable[[int, int], None] = None,
    ):
        safe_backend = (backend or "whisper").strip().lower()
        safe_model = (model_name or "medium").strip().lower()

        with self._lock:
            if self._model is None or self._model_name != safe_model or self._backend != safe_backend:
                try:
                    prepare_model_load("whisper")
                    self._load(safe_backend, safe_model)
                except RuntimeError as exc:
                    if not is_cuda_oom(exc):
                        raise
                    logger.warning(
                        "CUDA OOM while loading Whisper model %s; releasing peer models and retrying once.",
                        safe_model,
                    )
                    prepare_model_load("whisper")
                    self._load(safe_backend, safe_model)
            model = self._model

        language_value = (language or "auto").strip().lower()
        if safe_backend != "whisper":
            raise ValueError(f"unsupported transcription backend: {safe_backend}")

        temperature_value = max(0.0, float(temperature or 0.0))
        options = {
            "temperature": temperature_value,
            "fp16": self._fp16,
        }
        if temperature_value <= 0.0:
            options["beam_size"] = max(1, int(beam_size or 1))
        else:
            options["best_of"] = max(1, int(best_of or 1))
        if language_value and language_value != "auto":
            options["language"] = language_value
        result = self._transcribe_with_progress(model, media_path, options, progress_callback)
        return {"segments": result.get("segments") or []}


ENGINE = WhisperEngine()
