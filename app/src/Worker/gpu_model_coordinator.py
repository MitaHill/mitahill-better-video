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


def cleanup_cuda_cache():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def is_cuda_oom(exc: BaseException) -> bool:
    text = str(exc or "").lower()
    return "cuda out of memory" in text or "out of memory" in text and "cuda" in text
