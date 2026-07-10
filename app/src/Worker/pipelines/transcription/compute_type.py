import logging

logger = logging.getLogger("TRANSCRIBE_COMPUTE")


def _is_low_vram_cuda() -> bool:
    try:
        import torch

        if not torch.cuda.is_available():
            return False
        total_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        return total_gb <= 5.0
    except Exception:
        return False


def select_faster_whisper_compute_type(device: str) -> str:
    safe_device = str(device or "cpu").strip().lower()
    if safe_device == "cuda":
        preferred = ("int8_float32", "int8", "float32", "float16") if _is_low_vram_cuda() else (
            "float16",
            "int8_float16",
            "int8",
            "int8_float32",
            "float32",
        )
    else:
        preferred = ("int8", "int8_float32", "float32")

    try:
        import ctranslate2

        supported = set(ctranslate2.get_supported_compute_types(safe_device))
    except Exception as exc:
        logger.warning("Unable to query ctranslate2 compute types for %s: %s", safe_device, exc)
        return "float32" if safe_device == "cuda" else "int8"

    for compute_type in preferred:
        if compute_type in supported:
            return compute_type

    if supported:
        fallback = sorted(supported)[0]
        logger.warning("No preferred compute type available for %s, fallback to %s", safe_device, fallback)
        return fallback

    return "float32" if safe_device == "cuda" else "int8"
