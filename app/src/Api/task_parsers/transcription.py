from app.src.Config import settings as config

from .common import bool_from_form, float_from_form, int_from_form, merge_unparsed_form_fields

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
    requested_provider = (form.get("translator_provider", default_provider) or default_provider).strip().lower()
    default_base_url = (
        defaults.get("translator_base_url", config.TRANSCRIPTION_TRANSLATOR_BASE_URL)
        or ""
    ).strip()
    if "translator_base_url" in form:
        requested_base_url = str(form.get("translator_base_url") or "").strip()
    else:
        requested_base_url = default_base_url
    if requested_provider == "openai":
        requested_base_url = requested_base_url or "https://api.openai.com/v1"

    parsed = {
        "task_category": "transcribe",
        "transcription_backend": "faster_whisper",
        "transcribe_mode": (form.get("transcribe_mode", "subtitle_zip") or "subtitle_zip").lower(),
        "subtitle_format": (form.get("subtitle_format", "srt") or "srt").lower(),
        "whisper_model": (
            form.get("whisper_model", defaults.get("whisper_model", "large-v3"))
            or defaults.get("whisper_model", "large-v3")
            or "large-v3"
        ).lower(),
        "language": (form.get("language", "auto") or "auto").strip().lower(),
        "translate_to": (form.get("translate_to", "") or "").strip(),
        "translator_provider": requested_provider,
        "translator_base_url": requested_base_url,
        "translator_model": (
            form.get("translator_model", defaults.get("translator_model", config.TRANSCRIPTION_TRANSLATOR_MODEL))
            or defaults.get("translator_model", config.TRANSCRIPTION_TRANSLATOR_MODEL)
            or ""
        ).strip(),
        "translator_api_key": (
            form.get("translator_api_key", defaults.get("translator_api_key", config.TRANSCRIPTION_TRANSLATOR_API_KEY))
            or defaults.get("translator_api_key", config.TRANSCRIPTION_TRANSLATOR_API_KEY)
            or ""
        ).strip(),
        "translator_prompt": (
            form.get("translator_prompt", defaults.get("translator_prompt", config.TRANSCRIPTION_TRANSLATOR_PROMPT))
            or defaults.get("translator_prompt", config.TRANSCRIPTION_TRANSLATOR_PROMPT)
            or ""
        ).strip(),
        "translator_fallback_mode": (
            form.get("translator_fallback_mode", defaults.get("translator_fallback_mode", "model_full_text"))
            or defaults.get("translator_fallback_mode", "model_full_text")
            or "model_full_text"
        ).strip().lower(),
        "transcribe_runtime_mode": (
            defaults.get("transcribe_runtime_mode", "parallel")
            or "parallel"
        ).strip().lower(),
        "translator_timeout_sec": float_from_form(
            form,
            "translator_timeout_sec",
            defaults.get("translator_timeout_sec", config.TRANSCRIPTION_TRANSLATOR_TIMEOUT_SECONDS),
        ),
        "generate_bilingual": bool_from_form(form, "generate_bilingual", True),
        "export_json": bool_from_form(form, "export_json", False),
        "prepend_timestamps": bool_from_form(form, "prepend_timestamps", False),
        "max_line_chars": int_from_form(form, "max_line_chars", 42),
        "temperature": float_from_form(form, "temperature", 0.0),
        "beam_size": int_from_form(form, "beam_size", 5),
        "best_of": int_from_form(form, "best_of", 5),
        "output_video_codec": (form.get("output_video_codec", "h264") or "h264").lower(),
        "output_audio_bitrate_k": int_from_form(form, "output_audio_bitrate_k", 192),
    }
    return merge_unparsed_form_fields(form, parsed)
