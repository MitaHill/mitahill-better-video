import logging
import threading
import time
from pathlib import Path
from typing import Dict, Iterable, List

import torch

from app.src.Database import core as db


_FASTER_ROOT = Path("/workspace/storage/models/transcription/faster-whisper")

logger = logging.getLogger("TRANSCRIBE_ENGINE")


class WhisperEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._backend = ""
        self._model_name = ""
        self._model_backend_device = ""
        self._model = None
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        _FASTER_ROOT.mkdir(parents=True, exist_ok=True)

    def _resolve_faster_model_ref(self, model_name: str):
        safe_model = (model_name or "large-v3").strip().lower()
        local_dir = _FASTER_ROOT / safe_model
        # 管理后台允许把模型预下载到本地目录。
        # 如果本地已经存在，就优先走本地路径，避免任务执行时再去远端拉权重。
        if local_dir.exists():
            return str(local_dir)
        return safe_model

    def _load(self, backend: str, model_name: str):
        safe_backend = (backend or "faster_whisper").strip().lower()
        safe_model = (model_name or "large-v3").strip().lower()

        if safe_backend != "faster_whisper":
            raise ValueError(f"unsupported transcription backend: {safe_backend}")

        from faster_whisper import WhisperModel

        model_ref = self._resolve_faster_model_ref(safe_model)
        # 这里不再保留普通 whisper 的分支，整个系统只接受 faster-whisper。
        # compute_type 也按设备显式切分，GPU 走 float16，CPU 才退到 int8。
        compute_type = "float16" if self._device == "cuda" else "int8"
        self._model = WhisperModel(model_ref, device=self._device, compute_type=compute_type)
        self._model_backend_device = self._device

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
            # memory_saving 模式的目标不是“快”，而是主动串行化 GPU 占用。
            # 因此这里会等待其他任务让出显存，而不是硬上导致多个大模型互相挤爆。
            time.sleep(max(0.2, float(poll_sec or 1.0)))

    def _offload_to_cpu(self):
        with self._lock:
            if self._model is None:
                return
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
        backend="faster_whisper",
        model_name="large-v3",
        language="auto",
        temperature=0.0,
        beam_size=5,
        best_of=5,
        runtime_mode="parallel",
        task_id="",
    ):
        safe_backend = (backend or "faster_whisper").strip().lower()
        safe_model = (model_name or "large-v3").strip().lower()
        safe_runtime_mode = str(runtime_mode or "parallel").strip().lower()

        if safe_runtime_mode == "memory_saving":
            # 只有在显存节约模式下，任务才会在开跑前主动等队列清空。
            self._wait_until_no_other_processing(task_id=task_id, timeout_sec=1800.0, poll_sec=1.0)

        with self._lock:
            # 模型按 backend + model 维度做缓存。
            # 同模型复用实例，不同模型切换时才重载，避免每段任务都重新初始化。
            if self._model is None or self._model_name != safe_model or self._backend != safe_backend:
                self._load(safe_backend, safe_model)
            model = self._model

        language_value = (language or "auto").strip().lower()
        if safe_backend != "faster_whisper":
            raise ValueError(f"unsupported transcription backend: {safe_backend}")

        options = {
            "beam_size": max(1, int(beam_size or 1)),
            "best_of": max(1, int(best_of or 1)),
            "temperature": max(0.0, float(temperature or 0.0)),
        }
        if language_value and language_value != "auto":
            options["language"] = language_value
        # faster-whisper 返回的是 segment 迭代器，这里统一转成纯 dict，
        # 后面的字幕、翻译、导出链路就不用再关心底层 SDK 的对象类型。
        segments, _info = model.transcribe(str(media_path), **options)
        return self._faster_segments_to_dict(segments)


ENGINE = WhisperEngine()
