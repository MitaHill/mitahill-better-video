from ...services.admin import get_parser_defaults
from app.src.Utils.transcription_model_ref import build_prefixed_model_ref


def _to_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def build_transcription_runtime_payload():
    defaults = get_parser_defaults() or {}
    backend = str(defaults.get("transcription_backend") or "whisper").strip().lower()
    active_model = str(defaults.get("whisper_model") or "medium").strip().lower()
    provider = str(defaults.get("translator_provider") or "none").strip().lower()
    model = str(defaults.get("translator_model") or "").strip()
    base_url = str(defaults.get("translator_base_url") or "").strip()
    context_window_size = _to_int(defaults.get("translator_context_window_size"), 6)
    batch_window_size = _to_int(defaults.get("translator_batch_window_size"), 10)
    batch_max_chars = _to_int(defaults.get("translator_batch_max_chars"), 2500)
    mode = str(defaults.get("translator_mode") or "window_batch").strip().lower()
    if mode not in {"window_batch", "single_sentence"}:
        mode = "window_batch"
    translation_enabled = provider != "none" and bool(model) and bool(base_url)
    return {
        "ok": True,
        "transcription": {
            "backend": backend,
            "active_model": active_model,
            "active_model_prefixed": build_prefixed_model_ref(backend, active_model),
        },
        "translation": {
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "mode": mode,
            "context_window_size": max(1, context_window_size),
            "batch_window_size": max(1, batch_window_size),
            "batch_max_chars": max(500, batch_max_chars),
            "enabled": translation_enabled,
        },
    }
