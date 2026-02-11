import logging
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

import torch

from app.src.Database import core as db


_OPENAI_ROOT = Path("/workspace/storage/models/transcription/whisper-openai")
_FASTER_ROOT = Path("/workspace/storage/models/transcription/faster-whisper")
_OPENAI_MODEL_ALIASES = {
    "large-v3-turbo": "turbo",
    "large": "large-v2",
}

logger = logging.getLogger("TRANSCRIBE_ENGINE")


class WhisperEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._backend = ""
        self._model_name = ""
        self._model_backend_device = ""
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
            self._model_backend_device = self._device
        elif safe_backend == "faster_whisper":
            from faster_whisper import WhisperModel

            model_ref = self._resolve_faster_model_ref(safe_model)
            compute_type = "float16" if self._device == "cuda" else "int8"
            self._model = WhisperModel(model_ref, device=self._device, compute_type=compute_type)
            self._model_backend_device = self._device
        else:
            raise ValueError(f"unsupported transcription backend: {safe_backend}")

        self._backend = safe_backend
        self._model_name = safe_model

    @staticmethod
    def _wait_until_no_other_processing(task_id: str = "", timeout_sec: float = 1800.0, poll_sec: float = 1.0):
        deadline = time.time() + max(1.0, float(timeout_sec or 1800.0))
        while True:
            processing = db.count_processing_tasks(exclude_task_id=task_id)
            if processing <= 0:
                return
            if time.time() >= deadline:
                raise TimeoutError(f"waiting for idle processing tasks timed out ({processing} active)")
            time.sleep(max(0.2, float(poll_sec or 1.0)))

    def _move_whisper_to_cuda_if_needed(self):
        if self._backend != "whisper":
            return
        if self._device != "cuda":
            return
        if self._model is None:
            return
        if self._model_backend_device == "cuda":
            return
        self._model = self._model.to("cuda")
        self._model_backend_device = "cuda"
        logger.info("Whisper model moved back to GPU.")

    def _offload_to_cpu(self):
        with self._lock:
            if self._model is None:
                return
            if self._backend == "whisper":
                self._model = self._model.to("cpu")
                self._model_backend_device = "cpu"
                logger.info("Whisper model offloaded to CPU.")
            else:
                # faster-whisper has no stable in-place to-cpu transfer; release instance.
                self._model = None
                self._model_backend_device = ""
                logger.info("Faster-whisper model released from GPU memory.")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def after_transcription_step(self, runtime_mode: str = "parallel"):
        safe_mode = str(runtime_mode or "parallel").strip().lower()
        if safe_mode != "memory_saving":
            return
        time.sleep(1.0)
        self._offload_to_cpu()

    def finalize_task(self, runtime_mode: str = "parallel"):
        safe_mode = str(runtime_mode or "parallel").strip().lower()
        if safe_mode != "memory_saving":
            return
        self._offload_to_cpu()

    @staticmethod
    def _safe_float(value, default=0.0):
        try:
            return float(value)
        except Exception:
            return float(default)

    def _faster_segments_to_dict(
        self,
        segments: Iterable,
        *,
        progress_callback: Optional[Callable[[float, float], None]] = None,
        total_duration_sec: float = 0.0,
    ) -> Dict:
        out_segments: List[Dict] = []
        safe_total = max(0.0, self._safe_float(total_duration_sec, 0.0))
        last_reported = 0.0
        for seg in segments:
            try:
                start_sec = self._safe_float(getattr(seg, "start", 0.0), 0.0)
                end_sec = self._safe_float(getattr(seg, "end", 0.0), 0.0)
                out_segments.append(
                    {
                        "start": start_sec,
                        "end": end_sec,
                        "text": str(getattr(seg, "text", "") or "").strip(),
                    }
                )
                if progress_callback:
                    done_sec = max(last_reported, end_sec)
                    if safe_total > 0:
                        done_sec = min(done_sec, safe_total)
                    last_reported = done_sec
                    progress_callback(done_sec, safe_total)
            except Exception:
                continue
        if progress_callback:
            if safe_total > 0:
                progress_callback(safe_total, safe_total)
            else:
                progress_callback(last_reported, last_reported)
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
        runtime_mode="parallel",
        task_id="",
        progress_callback: Optional[Callable[[float, float], None]] = None,
        expected_duration_sec: float = 0.0,
    ):
        safe_backend = (backend or "whisper").strip().lower()
        safe_model = (model_name or "medium").strip().lower()
        safe_runtime_mode = str(runtime_mode or "parallel").strip().lower()

        if safe_runtime_mode == "memory_saving":
            self._wait_until_no_other_processing(task_id=task_id, timeout_sec=1800.0, poll_sec=1.0)

        with self._lock:
            if self._model is None or self._model_name != safe_model or self._backend != safe_backend:
                self._load(safe_backend, safe_model)
            elif safe_runtime_mode == "memory_saving":
                self._move_whisper_to_cuda_if_needed()
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
            result = model.transcribe(str(media_path), **options)
            if progress_callback:
                safe_expected = max(0.0, self._safe_float(expected_duration_sec, 0.0))
                progress_callback(safe_expected, safe_expected)
            return result

        if safe_backend == "faster_whisper":
            options = {
                "beam_size": max(1, int(beam_size or 1)),
                "best_of": max(1, int(best_of or 1)),
                "temperature": max(0.0, float(temperature or 0.0)),
            }
            if language_value and language_value != "auto":
                options["language"] = language_value
            segments, info = model.transcribe(str(media_path), **options)
            info_duration = self._safe_float(getattr(info, "duration", 0.0), 0.0)
            total_duration_sec = max(info_duration, self._safe_float(expected_duration_sec, 0.0))
            return self._faster_segments_to_dict(
                segments,
                progress_callback=progress_callback,
                total_duration_sec=total_duration_sec,
            )

        raise ValueError(f"unsupported transcription backend: {safe_backend}")


ENGINE = WhisperEngine()
