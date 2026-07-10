import logging

logger = logging.getLogger("TRANSCRIBE_COMPUTE")

_CUDA_PREFERRED = ("float16", "int8_float16", "int8_float32", "int8", "float32")
_CPU_PREFERRED = ("int8", "int8_float32", "float32")


def get_supported_compute_types(device: str):
    safe_device = str(device or "cpu").strip().lower()
    try:
        import ctranslate2

        return set(ctranslate2.get_supported_compute_types(safe_device))
    except Exception as exc:
        logger.warning("Unable to query ctranslate2 compute types for %s: %s", safe_device, exc)
        return set()


def select_faster_whisper_compute_type(device: str) -> str:
    safe_device = str(device or "cpu").strip().lower()
    preferred = _CUDA_PREFERRED if safe_device == "cuda" else _CPU_PREFERRED
    supported = get_supported_compute_types(safe_device)

    for compute_type in preferred:
        if compute_type in supported:
            return compute_type

    if supported:
        fallback = sorted(supported)[0]
        logger.warning("No preferred compute type available for %s, fallback to %s", safe_device, fallback)
        return fallback

    return "float32" if safe_device == "cuda" else "int8"


def inspect_faster_whisper_compute_types(device: str):
    safe_device = str(device or "cpu").strip().lower()
    preferred = _CUDA_PREFERRED if safe_device == "cuda" else _CPU_PREFERRED
    supported = sorted(get_supported_compute_types(safe_device))
    return {
        "device": safe_device,
        "supported": supported,
        "preferred_order": list(preferred),
        "selected": select_faster_whisper_compute_type(safe_device),
    }
