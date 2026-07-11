from app.src.Config import settings as config

from .common import float_from_form, int_from_form

try:
    from app.src.Api.services.admin.transcription_config import get_parser_defaults
except Exception:  # pragma: no cover - optional runtime import guard
    get_parser_defaults = None


def _load_parser_defaults():
    if not get_parser_defaults:
        return {}
    try:
        return get_parser_defaults() or {}
    except Exception:
        return {}


def parse_transcription_task_params(form):
    defaults = _load_parser_defaults()
    default_provider = (
        defaults.get("translator_provider", config.TRANSCRIPTION_TRANSLATOR_PROVIDER)
        or "none"
    ).strip().lower()
    translate_to = (form.get("translate_to", "") or "").strip()
    requested_provider = default_provider if translate_to else "none"
    if requested_provider not in {"none", "openai_compatible"}:
        requested_provider = "none"
    default_base_url = (
        defaults.get("translator_base_url", config.TRANSCRIPTION_TRANSLATOR_BASE_URL)
        or ""
    ).strip()

    parsed = {
        "task_category": "transcribe",
        "transcription_backend": "whisper",
        "transcribe_mode": (form.get("transcribe_mode", "subtitle_zip") or "subtitle_zip").lower(),
        "subtitle_format": (form.get("subtitle_format", "srt") or "srt").lower(),
        "whisper_model": (
            form.get("whisper_model", defaults.get("whisper_model", "medium"))
            or defaults.get("whisper_model", "medium")
            or "medium"
        ).lower(),
        "language": (form.get("language", "auto") or "auto").strip().lower(),
        "translate_to": translate_to,
        "translator_provider": requested_provider,
        "translator_base_url": default_base_url,
        "translator_model": (
            defaults.get("translator_model", config.TRANSCRIPTION_TRANSLATOR_MODEL)
            or ""
        ).strip(),
        "translator_api_key": (
            defaults.get("translator_api_key", config.TRANSCRIPTION_TRANSLATOR_API_KEY)
            or ""
        ).strip(),
        "translator_prompt": (
            defaults.get("translator_prompt", config.TRANSCRIPTION_TRANSLATOR_PROMPT)
            or ""
        ).strip(),
        "translator_fallback_mode": (
            form.get("translator_fallback_mode", defaults.get("translator_fallback_mode", "model_full_text"))
            or defaults.get("translator_fallback_mode", "model_full_text")
            or "model_full_text"
        ).strip().lower(),
        "generate_bilingual": True,
        "export_json": False,
        "prepend_timestamps": False,
        "max_line_chars": int_from_form(form, "max_line_chars", 42),
        "temperature": float_from_form(form, "temperature", 0.0),
        "beam_size": int_from_form(form, "beam_size", 5),
        "best_of": int_from_form(form, "best_of", 5),
    }
    return parsed
