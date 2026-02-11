from ...services.admin import get_parser_defaults
from app.src.Utils.transcription_model_ref import build_prefixed_model_ref


def build_transcription_runtime_payload():
    defaults = get_parser_defaults() or {}
    backend = str(defaults.get("transcription_backend") or "whisper").strip().lower()
    active_model = str(defaults.get("whisper_model") or "medium").strip().lower()
    provider = str(defaults.get("translator_provider") or "none").strip().lower()
    model = str(defaults.get("translator_model") or "").strip()
    base_url = str(defaults.get("translator_base_url") or "").strip()
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
            "enabled": translation_enabled,
        },
    }
