from typing import Tuple


_BACKEND_TO_PREFIX = {
    "whisper": "whisper-openai",
    "faster_whisper": "fast-whisper",
}

_PREFIX_TO_BACKEND = {
    "whisper-openai": "whisper",
    "openai-whisper": "whisper",
    "whisper": "whisper",
    "fast-whisper": "faster_whisper",
    "faster-whisper": "faster_whisper",
    "faster_whisper": "faster_whisper",
}


def normalize_backend_name(backend: str, fallback: str = "whisper") -> str:
    safe_backend = str(backend or "").strip().lower()
    return _PREFIX_TO_BACKEND.get(safe_backend, safe_backend or str(fallback or "whisper").strip().lower())


def backend_prefix(backend: str) -> str:
    safe_backend = normalize_backend_name(backend, fallback="whisper")
    return _BACKEND_TO_PREFIX.get(safe_backend, safe_backend or "whisper-openai")


def build_prefixed_model_ref(backend: str, model_id: str) -> str:
    safe_model = str(model_id or "").strip().lower()
    prefix = backend_prefix(backend)
    if not safe_model:
        return prefix
    return f"{prefix}/{safe_model}"


def parse_prefixed_model_ref(model_ref: str, fallback_backend: str = "whisper") -> Tuple[str, str]:
    safe_fallback_backend = normalize_backend_name(fallback_backend, fallback="whisper")
    safe_value = str(model_ref or "").strip().lower()
    if not safe_value:
        return safe_fallback_backend, ""

    if "/" not in safe_value:
        return safe_fallback_backend, safe_value

    prefix, tail = safe_value.split("/", 1)
    safe_tail = str(tail or "").strip().lower()
    if not safe_tail:
        return safe_fallback_backend, safe_value

    mapped_backend = normalize_backend_name(prefix, fallback=safe_fallback_backend)
    if mapped_backend == prefix and prefix not in _PREFIX_TO_BACKEND:
        return safe_fallback_backend, safe_value
    return mapped_backend, safe_tail
