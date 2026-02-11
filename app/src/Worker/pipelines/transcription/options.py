from app.src.Config import settings as config
from app.src.Utils.transcription_model_ref import parse_prefixed_model_ref

VALID_TRANSCRIBE_MODES = {"subtitle_zip", "subtitled_video", "subtitle_and_video_zip"}
VALID_SUBTITLE_FORMATS = {"srt", "vtt"}
VALID_TRANSLATOR_PROVIDERS = {"none", "ollama", "openai_compatible"}
VALID_TRANSLATOR_FALLBACK_MODES = {"model_full_text", "source_text"}
VALID_TRANSCRIPTION_BACKENDS = {"whisper", "faster_whisper"}
VALID_TRANSCRIBE_RUNTIME_MODES = {"parallel", "memory_saving"}


def _to_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value, default=0, min_value=None, max_value=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def _to_float(value, default=0.0, min_value=None, max_value=None):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def normalize_transcription_options(raw):
    options = raw or {}
    backend_raw = (options.get("transcription_backend") or "whisper").strip().lower()
    if backend_raw not in VALID_TRANSCRIPTION_BACKENDS:
        backend_raw = "whisper"
    model_raw = (options.get("whisper_model") or "medium").strip().lower() or "medium"
    parsed_backend, parsed_model = parse_prefixed_model_ref(model_raw, fallback_backend=backend_raw)
    backend = parsed_backend if parsed_backend in VALID_TRANSCRIPTION_BACKENDS else backend_raw

    mode = (options.get("transcribe_mode") or "subtitle_zip").strip().lower()
    if mode not in VALID_TRANSCRIBE_MODES:
        mode = "subtitle_zip"

    subtitle_format = (options.get("subtitle_format") or "srt").strip().lower()
    if subtitle_format not in VALID_SUBTITLE_FORMATS:
        subtitle_format = "srt"

    whisper_model = parsed_model or "medium"
    language = (options.get("language") or "auto").strip().lower() or "auto"

    translate_to = (options.get("translate_to") or "").strip()
    provider = (options.get("translator_provider") or config.TRANSCRIPTION_TRANSLATOR_PROVIDER or "none").strip().lower()
    if provider not in VALID_TRANSLATOR_PROVIDERS:
        provider = "none"
    fallback_mode = (options.get("translator_fallback_mode") or "model_full_text").strip().lower()
    if fallback_mode not in VALID_TRANSLATOR_FALLBACK_MODES:
        fallback_mode = "model_full_text"
    runtime_mode = (options.get("transcribe_runtime_mode") or "parallel").strip().lower()
    if runtime_mode not in VALID_TRANSCRIBE_RUNTIME_MODES:
        runtime_mode = "parallel"

    normalized = {
        "transcription_backend": backend,
        "transcribe_mode": mode,
        "subtitle_format": subtitle_format,
        "whisper_model": whisper_model,
        "language": language,
        "temperature": _to_float(options.get("temperature"), 0.0, min_value=0.0, max_value=1.0),
        "beam_size": _to_int(options.get("beam_size"), 5, min_value=1, max_value=20),
        "best_of": _to_int(options.get("best_of"), 5, min_value=1, max_value=20),
        "prepend_timestamps": _to_bool(options.get("prepend_timestamps"), False),
        "max_line_chars": _to_int(options.get("max_line_chars"), 42, min_value=0, max_value=200),
        "output_video_codec": (options.get("output_video_codec") or "h264").strip().lower() or "h264",
        "output_audio_bitrate_k": _to_int(options.get("output_audio_bitrate_k"), 192, min_value=32, max_value=1024),
        "translate_to": translate_to,
        "translator_provider": provider,
        "translator_base_url": (
            options.get("translator_base_url")
            or config.TRANSCRIPTION_TRANSLATOR_BASE_URL
            or ""
        ).strip(),
        "translator_model": (
            options.get("translator_model")
            or config.TRANSCRIPTION_TRANSLATOR_MODEL
            or ""
        ).strip(),
        "translator_api_key": (
            options.get("translator_api_key")
            or config.TRANSCRIPTION_TRANSLATOR_API_KEY
            or ""
        ).strip(),
        "translator_enable_thinking": _to_bool(
            options.get("translator_enable_thinking"),
            config.TRANSCRIPTION_TRANSLATOR_ENABLE_THINKING,
        ),
        "translator_prompt": (
            options.get("translator_prompt")
            or config.TRANSCRIPTION_TRANSLATOR_PROMPT
            or ""
        ).strip(),
        "translator_fallback_mode": fallback_mode,
        "transcribe_runtime_mode": runtime_mode,
        "translator_timeout_sec": _to_float(
            options.get("translator_timeout_sec"),
            config.TRANSCRIPTION_TRANSLATOR_TIMEOUT_SECONDS,
            min_value=1.0,
            max_value=1200.0,
        ),
        "generate_bilingual": _to_bool(options.get("generate_bilingual"), True),
        "export_json": _to_bool(options.get("export_json"), False),
    }
    return normalized
