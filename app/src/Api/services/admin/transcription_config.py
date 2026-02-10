import copy
from typing import Any, Dict

from app.src.Config import settings as config
from app.src.Data.transcription_languages import (
    TRANSCRIPTION_LANGUAGE_CODES,
    TRANSCRIPTION_TARGET_LANGUAGE_CODES,
)
from app.src.Database import transcription_admin as db_transcription


_VALID_BACKENDS = {"whisper", "faster_whisper"}
_VALID_TRANSLATORS = {"none", "ollama", "openai_compatible"}
_VALID_TRANSLATION_FALLBACK_MODES = {"model_full_text", "source_text"}


def default_transcription_config() -> Dict[str, Any]:
    return {
        "version": 1,
        "transcription": {
            "backend": "whisper",
            "active_model": "medium",
            "allowed_models": [
                "tiny",
                "tiny.en",
                "base",
                "base.en",
                "small",
                "small.en",
                "medium",
                "medium.en",
                "large",
                "large-v1",
                "large-v2",
                "large-v3",
                "turbo",
                "distil-large-v2",
                "distil-large-v3",
                "large-v3-turbo",
            ],
        },
        "translation": {
            "provider": config.TRANSCRIPTION_TRANSLATOR_PROVIDER or "none",
            "base_url": config.TRANSCRIPTION_TRANSLATOR_BASE_URL,
            "model": config.TRANSCRIPTION_TRANSLATOR_MODEL,
            "api_key": config.TRANSCRIPTION_TRANSLATOR_API_KEY,
            "timeout_sec": config.TRANSCRIPTION_TRANSLATOR_TIMEOUT_SECONDS,
            "prompt": config.TRANSCRIPTION_TRANSLATOR_PROMPT,
            "fallback_mode": "model_full_text",
        },
        "download": {
            "aria2": {
                "split": 16,
                "max_connection_per_server": 16,
                "proxy": "",
                "max_tries": 10,
                "retry_wait": 2,
                "connect_timeout_sec": 10,
                "timeout_sec": 120,
            }
        },
    }


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _normalize_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    merged = _deep_merge(default_transcription_config(), raw or {})

    backend = str(merged["transcription"].get("backend") or "whisper").strip().lower()
    if backend not in _VALID_BACKENDS:
        backend = "whisper"
    merged["transcription"]["backend"] = backend
    merged["transcription"]["active_model"] = str(
        merged["transcription"].get("active_model") or "medium"
    ).strip().lower()

    allowed = merged["transcription"].get("allowed_models") or []
    if not isinstance(allowed, list):
        allowed = []
    merged["transcription"]["allowed_models"] = [
        str(item).strip().lower() for item in allowed if str(item).strip()
    ]

    provider = str(merged["translation"].get("provider") or "none").strip().lower()
    if provider not in _VALID_TRANSLATORS:
        provider = "none"
    merged["translation"]["provider"] = provider
    merged["translation"]["base_url"] = str(merged["translation"].get("base_url") or "").strip()
    merged["translation"]["model"] = str(merged["translation"].get("model") or "").strip()
    merged["translation"]["api_key"] = str(merged["translation"].get("api_key") or "").strip()
    merged["translation"]["prompt"] = str(merged["translation"].get("prompt") or "").strip()
    fallback_mode = str(merged["translation"].get("fallback_mode") or "model_full_text").strip().lower()
    if fallback_mode not in _VALID_TRANSLATION_FALLBACK_MODES:
        fallback_mode = "model_full_text"
    merged["translation"]["fallback_mode"] = fallback_mode
    try:
        timeout_sec = float(merged["translation"].get("timeout_sec") or 120.0)
    except (TypeError, ValueError):
        timeout_sec = 120.0
    merged["translation"]["timeout_sec"] = max(1.0, min(timeout_sec, 1200.0))

    aria2 = merged["download"].get("aria2") or {}
    try:
        split = int(aria2.get("split") or 16)
    except (TypeError, ValueError):
        split = 16
    try:
        max_conn = int(aria2.get("max_connection_per_server") or 16)
    except (TypeError, ValueError):
        max_conn = 16
    try:
        max_tries = int(aria2.get("max_tries") or 10)
    except (TypeError, ValueError):
        max_tries = 10
    try:
        retry_wait = int(aria2.get("retry_wait") or 2)
    except (TypeError, ValueError):
        retry_wait = 2
    try:
        connect_timeout_sec = int(aria2.get("connect_timeout_sec") or 10)
    except (TypeError, ValueError):
        connect_timeout_sec = 10
    try:
        timeout_sec = int(aria2.get("timeout_sec") or 120)
    except (TypeError, ValueError):
        timeout_sec = 120

    merged["download"]["aria2"] = {
        "split": max(1, min(split, 64)),
        "max_connection_per_server": max(1, min(max_conn, 64)),
        "proxy": str(aria2.get("proxy") or "").strip(),
        "max_tries": max(1, min(max_tries, 100)),
        "retry_wait": max(1, min(retry_wait, 30)),
        "connect_timeout_sec": max(3, min(connect_timeout_sec, 120)),
        "timeout_sec": max(10, min(timeout_sec, 600)),
    }

    return merged


def get_transcription_config() -> Dict[str, Any]:
    current = db_transcription.get_transcription_config(default_transcription_config)
    normalized = _normalize_config(current)
    if normalized != current:
        db_transcription.set_transcription_config(normalized)
    _sync_transcription_constraints(normalized)
    return normalized


def update_transcription_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    merged = _deep_merge(get_transcription_config(), payload or {})
    normalized = _normalize_config(merged)
    db_transcription.set_transcription_config(normalized)
    _sync_transcription_constraints(normalized)
    return normalized


def get_parser_defaults() -> Dict[str, Any]:
    current = get_transcription_config()
    transcription = current.get("transcription") or {}
    translation = current.get("translation") or {}
    return {
        "whisper_model": str(transcription.get("active_model") or "medium").strip().lower(),
        "translator_provider": str(translation.get("provider") or "none").strip().lower(),
        "translator_base_url": str(translation.get("base_url") or "").strip(),
        "translator_model": str(translation.get("model") or "").strip(),
        "translator_api_key": str(translation.get("api_key") or "").strip(),
        "translator_prompt": str(translation.get("prompt") or "").strip(),
        "translator_fallback_mode": str(translation.get("fallback_mode") or "model_full_text").strip().lower(),
        "translator_timeout_sec": float(translation.get("timeout_sec") or 120.0),
    }


def _sync_transcription_constraints(current: Dict[str, Any]):
    """Keep transcribe form constraint options aligned with admin transcription config."""
    try:
        from app.src.Api.services.form_constraints import (
            get_form_constraints_config,
            update_form_constraints_config,
        )
    except Exception:
        return

    config = get_form_constraints_config()
    categories = config.get("categories") or {}
    transcribe = categories.get("transcribe") or {}
    fields = copy.deepcopy(transcribe.get("fields") or {})
    whisper_field = fields.get("whisper_model") or {}
    language_field = fields.get("language") or {}
    translate_to_field = fields.get("translate_to") or {}

    transcription = current.get("transcription") or {}
    allowed = [
        str(item).strip().lower()
        for item in (transcription.get("allowed_models") or [])
        if str(item).strip()
    ]
    active_model = str(transcription.get("active_model") or "medium").strip().lower()
    if active_model and active_model not in allowed:
        allowed.append(active_model)
    if allowed:
        whisper_field["allowed_values"] = allowed
    whisper_field["default_value"] = active_model or whisper_field.get("default_value", "medium")
    if whisper_field.get("lock") == "fixed":
        whisper_field["fixed_value"] = active_model or whisper_field.get("fixed_value", "medium")
    fields["whisper_model"] = whisper_field
    language_allowed_set = {str(item).strip().lower() for item in TRANSCRIPTION_LANGUAGE_CODES}
    language_field["kind"] = "enum"
    language_field["allowed_values"] = list(TRANSCRIPTION_LANGUAGE_CODES)
    default_language = str(language_field.get("default_value") or "auto").strip().lower()
    if default_language not in language_allowed_set:
        default_language = "auto"
    language_field["default_value"] = default_language
    fixed_language = str(language_field.get("fixed_value") or default_language).strip().lower()
    if fixed_language not in language_allowed_set:
        fixed_language = default_language
    language_field["fixed_value"] = fixed_language
    fields["language"] = language_field

    target_allowed_set = {str(item).strip().lower() for item in TRANSCRIPTION_TARGET_LANGUAGE_CODES}
    translate_to_field["kind"] = "enum"
    translate_to_field["allowed_values"] = list(TRANSCRIPTION_TARGET_LANGUAGE_CODES)
    default_target = str(translate_to_field.get("default_value") or "").strip().lower()
    if default_target not in target_allowed_set:
        default_target = ""
    translate_to_field["default_value"] = default_target
    fixed_target = str(translate_to_field.get("fixed_value") or default_target).strip().lower()
    if fixed_target not in target_allowed_set:
        fixed_target = default_target
    translate_to_field["fixed_value"] = fixed_target
    fields["translate_to"] = translate_to_field

    update_form_constraints_config(
        {
            "categories": {
                "transcribe": {
                    "fields": fields,
                }
            }
        }
    )
