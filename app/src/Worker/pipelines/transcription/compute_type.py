import logging

logger = logging.getLogger("TRANSCRIBE_COMPUTE")

_CUDA_PREFERRED = ("float16", "int8_float16", "int8_float32", "int8", "float32")
_CPU_PREFERRED = ("int8", "int8_float32", "float32")


def _cuda_compute_capability():
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        major, minor = torch.cuda.get_device_capability(0)
        return int(major), int(minor)
    except Exception as exc:
        logger.warning("Unable to query CUDA compute capability: %s", exc)
        return None


def resolve_faster_whisper_device(preferred_device: str = "") -> str:
    safe_device = str(preferred_device or "").strip().lower()
    if safe_device not in {"cuda", "cpu"}:
        try:
            import torch

            safe_device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            safe_device = "cpu"

    if safe_device != "cuda":
        return "cpu"

    capability = _cuda_compute_capability()
    if capability and capability[0] <= 6:
        logger.warning(
            "CUDA device compute capability %s.%s is not reliable with faster-whisper/CTranslate2 CUDA wheels; "
            "falling back to CPU int8.",
            capability[0],
            capability[1],
        )
        return "cpu"

    return "cuda"


def get_supported_compute_types(device: str):
    safe_device = str(device or "cpu").strip().lower()
    try:
        import ctranslate2

        return set(ctranslate2.get_supported_compute_types(safe_device))
    except Exception as exc:
        logger.warning("Unable to query ctranslate2 compute types for %s: %s", safe_device, exc)
        return set()


def select_faster_whisper_compute_type(device: str) -> str:
    safe_device = resolve_faster_whisper_device(device)
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
    requested_device = str(device or "cpu").strip().lower()
    safe_device = resolve_faster_whisper_device(requested_device)
    preferred = _CUDA_PREFERRED if safe_device == "cuda" else _CPU_PREFERRED
    supported = sorted(get_supported_compute_types(safe_device))
    capability = _cuda_compute_capability() if requested_device == "cuda" else None
    return {
        "requested_device": requested_device,
        "device": safe_device,
        "cuda_compute_capability": f"{capability[0]}.{capability[1]}" if capability else "",
        "supported": supported,
        "preferred_order": list(preferred),
        "selected": select_faster_whisper_compute_type(safe_device),
    }
