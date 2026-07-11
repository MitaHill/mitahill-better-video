import copy
from typing import Any, Dict

from app.src.Config import settings as config
from app.src.Data.transcription_languages import (
    TRANSCRIPTION_LANGUAGE_CODES,
    TRANSCRIPTION_TARGET_LANGUAGE_CODES,
)
from app.src.Database import transcription_admin as db_transcription

from .transcription_catalog import get_models_for_backend


_VALID_BACKENDS = {"whisper"}
_VALID_TRANSLATORS = {"none", "openai_compatible"}
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
                "large-v1",
                "large-v2",
                "large-v3",
                "large",
            ],
        },
        "translation": {
            "provider": config.TRANSCRIPTION_TRANSLATOR_PROVIDER or "none",
            "base_url": config.TRANSCRIPTION_TRANSLATOR_BASE_URL,
            "model": config.TRANSCRIPTION_TRANSLATOR_MODEL,
            "api_key": config.TRANSCRIPTION_TRANSLATOR_API_KEY,
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
            "startup_self_check_enabled": True,
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

    backend_supported = get_models_for_backend(backend)
    if merged["transcription"]["active_model"] not in set(backend_supported):
        merged["transcription"]["active_model"] = "medium"
    merged["transcription"]["allowed_models"] = list(backend_supported)

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
    merged["translation"].pop("timeout_sec", None)

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

    merged["runtime"] = {
        "startup_self_check_enabled": True,
    }

    return merged


def get_transcription_config() -> Dict[str, Any]:
    current = db_transcription.get_transcription_config(default_transcription_config)
    normalized = _normalize_config(current)
    if normalized != current:
        db_transcription.set_transcription_config(normalized)
    return normalized


def update_transcription_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    merged = _deep_merge(get_transcription_config(), payload or {})
    normalized = _normalize_config(merged)
    db_transcription.set_transcription_config(normalized)
    return normalized


def get_parser_defaults() -> Dict[str, Any]:
    current = get_transcription_config()
    transcription = current.get("transcription") or {}
    translation = current.get("translation") or {}
    return {
        "transcription_backend": str(transcription.get("backend") or "whisper").strip().lower(),
        "whisper_model": str(transcription.get("active_model") or "medium").strip().lower(),
        "translator_provider": str(translation.get("provider") or "none").strip().lower(),
        "translator_base_url": str(translation.get("base_url") or "").strip(),
        "translator_model": str(translation.get("model") or "").strip(),
        "translator_api_key": str(translation.get("api_key") or "").strip(),
        "translator_prompt": str(translation.get("prompt") or "").strip(),
        "translator_fallback_mode": str(translation.get("fallback_mode") or "model_full_text").strip().lower(),
    }
