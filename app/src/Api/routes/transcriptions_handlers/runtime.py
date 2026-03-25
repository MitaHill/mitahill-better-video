from ...services.admin import get_parser_defaults


def build_transcription_runtime_payload():
    defaults = get_parser_defaults() or {}
    provider = str(defaults.get("translator_provider") or "none").strip().lower()
    model = str(defaults.get("translator_model") or "").strip()
    base_url = str(defaults.get("translator_base_url") or "").strip()
    api_key = str(defaults.get("translator_api_key") or "").strip()
    translation_enabled = provider != "none" and bool(model) and bool(base_url) and (provider != "openai" or bool(api_key))
    return {
        "ok": True,
        "transcription": {
            "backend": str(defaults.get("transcription_backend") or "faster_whisper").strip().lower(),
            "active_model": str(defaults.get("whisper_model") or "large-v3").strip().lower(),
        },
        "translation": {
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "requires_api_key": provider == "openai",
            "enabled": translation_enabled,
        },
    }
