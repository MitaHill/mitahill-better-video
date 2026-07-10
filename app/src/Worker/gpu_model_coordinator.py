import gc
import logging
import threading
from typing import Callable, Dict

import torch

logger = logging.getLogger("GPU_MODEL_COORDINATOR")

_lock = threading.Lock()
_release_hooks: Dict[str, Callable[[], None]] = {}


def register_release_hook(name: str, callback: Callable[[], None]):
    safe_name = str(name or "").strip()
    if not safe_name:
        return
    with _lock:
        _release_hooks[safe_name] = callback


def release_models_except(active_name: str = ""):
    safe_active = str(active_name or "").strip()
    with _lock:
        hooks = [(name, callback) for name, callback in _release_hooks.items() if name != safe_active]

    for name, callback in hooks:
        try:
            callback()
        except Exception:
            logger.warning("Failed to release GPU model: %s", name, exc_info=True)

    cleanup_cuda_cache()


def release_all_models():
    with _lock:
        hooks = list(_release_hooks.items())

    for name, callback in hooks:
        try:
            callback()
        except Exception:
            logger.warning("Failed to release GPU model: %s", name, exc_info=True)

    cleanup_cuda_cache()


def _free_memory_ratio() -> float:
    if not torch.cuda.is_available():
        return 1.0
    try:
        free_bytes, total_bytes = torch.cuda.mem_get_info()
    except Exception:
        return 1.0
    if total_bytes <= 0:
        return 1.0
    return float(free_bytes) / float(total_bytes)


def assert_can_load_model(model_name: str = ""):
    if not torch.cuda.is_available():
        return
    free_ratio = _free_memory_ratio()
    if free_ratio < 0.15:
        label = str(model_name or "model").strip() or "model"
        raise RuntimeError(
            f"GPU memory is insufficient to load {label}. "
            "No new model was loaded; wait for current GPU work to finish or use a smaller/quantized model."
        )


def prepare_model_load(active_name: str = ""):
    release_models_except(active_name)
    assert_can_load_model(active_name)


def cleanup_cuda_cache():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def is_cuda_oom(exc: BaseException) -> bool:
    text = str(exc or "").lower()
    return "cuda out of memory" in text or "out of memory" in text and "cuda" in text
