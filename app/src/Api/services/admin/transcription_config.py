import copy
from typing import Any, Dict

from app.src.Config import settings as config
from app.src.Data.transcription_languages import (
    TRANSCRIPTION_LANGUAGE_CODES,
    TRANSCRIPTION_TARGET_LANGUAGE_CODES,
)
from app.src.Database import transcription_admin as db_transcription

from .transcription_catalog import get_models_for_backend


_VALID_BACKENDS = {"faster_whisper"}
_VALID_TRANSLATORS = {"none", "ollama", "openai", "openai_compatible"}
_VALID_TRANSLATION_FALLBACK_MODES = {"model_full_text", "source_text"}
_VALID_RUNTIME_MODES = {"parallel", "memory_saving"}

_DEFAULT_MODEL_BY_BACKEND = {
    "faster_whisper": "large-v3",
}


def default_transcription_config() -> Dict[str, Any]:
    return {
        "version": 1,
        "transcription": {
            "backend": "faster_whisper",
            "active_model": "large-v3",
            "allowed_models": [
                "tiny",
                "tiny.en",
                "base",
                "base.en",
                "small",
                "small.en",
                "medium",
                "medium.en",
                "large-v1",
                "large-v2",
                "large-v3",
                "distil-large-v2",
                "distil-large-v3",
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
        "runtime": {
            "transcribe_runtime_mode": "parallel",
            "startup_self_check_enabled": False,
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

    backend = str(merged["transcription"].get("backend") or "faster_whisper").strip().lower()
    # 后台配置层面也只允许 faster-whisper。
    # 这里做二次收口，避免数据库残留旧值时把普通 whisper 又放回来。
    if backend not in _VALID_BACKENDS:
        backend = "faster_whisper"
    merged["transcription"]["backend"] = backend
    merged["transcription"]["active_model"] = str(
        merged["transcription"].get("active_model") or "large-v3"
    ).strip().lower()

    allowed = merged["transcription"].get("allowed_models") or []
    if not isinstance(allowed, list):
        allowed = []
    merged["transcription"]["allowed_models"] = [
        str(item).strip().lower() for item in allowed if str(item).strip()
    ]
    backend_supported = get_models_for_backend(backend)
    backend_supported_set = {str(item).strip().lower() for item in backend_supported}
    merged["transcription"]["allowed_models"] = [
        item for item in merged["transcription"]["allowed_models"] if item in backend_supported_set
    ]
    active_model = str(merged["transcription"].get("active_model") or "").strip().lower()
    if active_model not in backend_supported_set:
        # 如果当前活动模型已经不兼容，就按“默认模型 -> 允许列表 -> 后端首选”顺序回退。
        # 目的不是保留原值，而是保证任何时候都能落到一个可运行模型。
        compatible_from_allowed = [
            item for item in merged["transcription"]["allowed_models"] if item in backend_supported_set
        ]
        preferred = _DEFAULT_MODEL_BY_BACKEND.get(backend, "large-v3")
        if preferred in backend_supported_set:
            fallback_model = preferred
        elif compatible_from_allowed:
            fallback_model = compatible_from_allowed[0]
        else:
            fallback_model = backend_supported[0] if backend_supported else "large-v3"
        merged["transcription"]["active_model"] = fallback_model

    provider = str(merged["translation"].get("provider") or "none").strip().lower()
    if provider not in _VALID_TRANSLATORS:
        provider = "none"
    merged["translation"]["provider"] = provider
    merged["translation"]["base_url"] = str(merged["translation"].get("base_url") or "").strip()
    if provider == "openai" and not merged["translation"]["base_url"]:
        merged["translation"]["base_url"] = "https://api.openai.com/v1"
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

    runtime = merged.get("runtime") or {}
    runtime_mode = str(runtime.get("transcribe_runtime_mode") or "parallel").strip().lower()
    if runtime_mode not in _VALID_RUNTIME_MODES:
        runtime_mode = "parallel"
    startup_self_check_enabled = bool(runtime.get("startup_self_check_enabled"))
    merged["runtime"] = {
        "transcribe_runtime_mode": runtime_mode,
        "startup_self_check_enabled": startup_self_check_enabled,
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
        "transcription_backend": str(transcription.get("backend") or "faster_whisper").strip().lower(),
        "whisper_model": str(transcription.get("active_model") or "large-v3").strip().lower(),
        "translator_provider": str(translation.get("provider") or "none").strip().lower(),
        "translator_base_url": str(translation.get("base_url") or "").strip(),
        "translator_model": str(translation.get("model") or "").strip(),
        "translator_api_key": str(translation.get("api_key") or "").strip(),
        "translator_prompt": str(translation.get("prompt") or "").strip(),
        "translator_fallback_mode": str(translation.get("fallback_mode") or "model_full_text").strip().lower(),
        "translator_timeout_sec": float(translation.get("timeout_sec") or 120.0),
        "transcribe_runtime_mode": str((current.get("runtime") or {}).get("transcribe_runtime_mode") or "parallel").strip().lower(),
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
    translator_provider_field = fields.get("translator_provider") or {}
    translator_base_url_field = fields.get("translator_base_url") or {}
    translator_model_field = fields.get("translator_model") or {}
    translator_api_key_field = fields.get("translator_api_key") or {}
    translator_prompt_field = fields.get("translator_prompt") or {}
    translator_timeout_field = fields.get("translator_timeout_sec") or {}

    transcription = current.get("transcription") or {}
    backend = str(transcription.get("backend") or "faster_whisper").strip().lower()
    backend_supported = [
        str(item).strip().lower()
        for item in get_models_for_backend(backend)
        if str(item).strip()
    ]
    backend_supported_set = set(backend_supported)
    allowed = [
        str(item).strip().lower()
        for item in (transcription.get("allowed_models") or [])
        if str(item).strip()
    ]
    compatible_allowed = [item for item in allowed if item in backend_supported_set]
    active_model = str(transcription.get("active_model") or "large-v3").strip().lower()
    if active_model and active_model not in compatible_allowed and active_model in backend_supported_set:
        compatible_allowed.append(active_model)
    if not compatible_allowed:
        compatible_allowed = backend_supported or [active_model or "large-v3"]
    # 这里把后台配置同步回前端约束层。
    # 否则管理员明明在后台禁用了某些模型，前端下拉框仍可能继续显示旧值。
    whisper_field["label"] = "Fast-Whisper模型"
    whisper_field["allowed_values"] = compatible_allowed
    whisper_field["default_value"] = active_model or whisper_field.get("default_value", "large-v3")
    if whisper_field.get("lock") == "fixed":
        whisper_field["fixed_value"] = active_model or whisper_field.get("fixed_value", "large-v3")
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
    default_target = str(translate_to_field.get("default_value") or "zh").strip().lower()
    if default_target not in target_allowed_set:
        default_target = "zh"
    translate_to_field["default_value"] = default_target
    fixed_target = str(translate_to_field.get("fixed_value") or default_target).strip().lower()
    if fixed_target not in target_allowed_set:
        fixed_target = default_target
    translate_to_field["fixed_value"] = fixed_target
    fields["translate_to"] = translate_to_field

    translation = current.get("translation") or {}
    provider = str(translation.get("provider") or "none").strip().lower()
    if provider not in _VALID_TRANSLATORS:
        provider = "none"
    translator_provider_field["kind"] = "enum"
    translator_provider_field["allowed_values"] = ["none", "ollama", "openai", "openai_compatible"]
    translator_provider_field["default_value"] = provider
    if translator_provider_field.get("lock") == "fixed":
        translator_provider_field["fixed_value"] = provider
    fields["translator_provider"] = translator_provider_field

    current_base_url = str(translation.get("base_url") or "").strip()
    current_model = str(translation.get("model") or "").strip()
    current_api_key = str(translation.get("api_key") or "").strip()
    current_prompt = str(translation.get("prompt") or "").strip()
    current_timeout = float(translation.get("timeout_sec") or 120.0)

    translator_base_url_field["default_value"] = current_base_url
    if translator_base_url_field.get("lock") == "fixed":
        translator_base_url_field["fixed_value"] = current_base_url
    fields["translator_base_url"] = translator_base_url_field

    translator_model_field["default_value"] = current_model
    if translator_model_field.get("lock") == "fixed":
        translator_model_field["fixed_value"] = current_model
    fields["translator_model"] = translator_model_field

    translator_api_key_field["default_value"] = current_api_key
    if translator_api_key_field.get("lock") == "fixed":
        translator_api_key_field["fixed_value"] = current_api_key
    fields["translator_api_key"] = translator_api_key_field

    translator_prompt_field["default_value"] = current_prompt
    if translator_prompt_field.get("lock") == "fixed":
        translator_prompt_field["fixed_value"] = current_prompt
    fields["translator_prompt"] = translator_prompt_field

    translator_timeout_field["default_value"] = current_timeout
    if translator_timeout_field.get("lock") == "fixed":
        translator_timeout_field["fixed_value"] = current_timeout
    fields["translator_timeout_sec"] = translator_timeout_field

    update_form_constraints_config(
        {
            "categories": {
                "transcribe": {
                    "fields": fields,
                }
            }
        }
    )
