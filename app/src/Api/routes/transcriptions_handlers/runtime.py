from ...services.admin import get_parser_defaults


def build_transcription_runtime_payload():
    defaults = get_parser_defaults() or {}
    provider = str(defaults.get("translator_provider") or "none").strip().lower()
    model = str(defaults.get("translator_model") or "").strip()
    base_url = str(defaults.get("translator_base_url") or "").strip()
    translation_enabled = provider != "none" and bool(model) and bool(base_url)
    return {
        "ok": True,
        "transcription": {
            "backend": str(defaults.get("transcription_backend") or "whisper").strip().lower(),
            "active_model": str(defaults.get("whisper_model") or "medium").strip().lower(),
        },
        "translation": {
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "enabled": translation_enabled,
        },
    }
