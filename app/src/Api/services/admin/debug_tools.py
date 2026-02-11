import logging
from typing import Dict

from .model_checks import (
    resolve_model_entry,
    test_translation_provider,
    verify_model_hashes,
    warmup_transcription_model,
)
from .transcription_config import get_transcription_config

logger = logging.getLogger("ADMIN_DEBUG")


def _pick_hash_error_message(hash_res: Dict) -> str:
    checks = hash_res.get("checks") or []
    for item in checks:
        if str(item.get("status") or "").strip().lower() != "failed":
            continue
        message = str(item.get("message") or "").strip()
        if message:
            return message
    return "HASH 校验失败"


def run_transcription_model_test(mode: str = "full") -> Dict:
    safe_mode = str(mode or "full").strip().lower()
    if safe_mode not in {"full", "hash", "warmup"}:
        safe_mode = "full"

    current = get_transcription_config()
    transcription = current.get("transcription") or {}
    backend = str(transcription.get("backend") or "whisper").strip().lower()
    model_id = str(transcription.get("active_model") or "medium").strip().lower()

    result = {
        "ok": False,
        "backend": backend,
        "model_id": model_id,
        "mode": safe_mode,
        "steps": [],
    }

    try:
        model_entry = resolve_model_entry(backend, model_id)
    except Exception as exc:
        logger.error("Model resolve failed: %s", exc)
        result["error"] = str(exc)
        return result

    hash_res = verify_model_hashes(model_entry)
    result["steps"].append({"name": "hash", **hash_res})
    if not hash_res.get("ok"):
        result["error"] = _pick_hash_error_message(hash_res)
        logger.error("Model hash validation failed: %s/%s (%s)", backend, model_id, result["error"])
        return result

    if safe_mode == "hash":
        result["ok"] = True
        result["message"] = "HASH 校验通过"
        return result

    warmup_res = warmup_transcription_model(model_entry)
    result["steps"].append({"name": "warmup", **warmup_res})
    if not warmup_res.get("ok"):
        result["error"] = warmup_res.get("message") or "热身失败"
        logger.error("Model warmup failed: %s", warmup_res.get("message"))
        return result

    result["ok"] = True
    result["message"] = "模型测试通过"
    return result


def run_translation_provider_test() -> Dict:
    current = get_transcription_config()
    translation = current.get("translation") or {}
    result = test_translation_provider(translation)
    if not result.get("ok"):
        logger.error("Translation source test failed: %s", result.get("error"))
    return result
