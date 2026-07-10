from ...services.admin import get_parser_defaults
from ...services.admin.transcription_catalog import list_transcription_models


def build_transcription_runtime_payload():
    defaults = get_parser_defaults() or {}
    installed_models = [
        str(item.get("model_id") or "").strip().lower()
        for item in list_transcription_models()
        if item.get("installed") and str(item.get("model_id") or "").strip()
    ]
    provider = str(defaults.get("translator_provider") or "none").strip().lower()
    model = str(defaults.get("translator_model") or "").strip()
    base_url = str(defaults.get("translator_base_url") or "").strip()
    translation_enabled = provider == "openai_compatible" and bool(model) and bool(base_url)
    return {
        "ok": True,
        "transcription": {
            "backend": str(defaults.get("transcription_backend") or "whisper").strip().lower(),
            "active_model": str(defaults.get("whisper_model") or "medium").strip().lower(),
            "installed_models": installed_models,
        },
        "translation": {
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "requires_api_key": False,
            "enabled": translation_enabled,
        },
    }
