import logging
from typing import Dict, Optional

from .model_checks import (
    resolve_model_entry,
    test_translation_provider,
    verify_model_hashes,
    warmup_transcription_model,
)
from .transcription_catalog import (
    get_installed_variants,
    get_models_for_backend,
    model_is_supported_by_backend,
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


def _build_backend_mismatch_error(backend: str, model_id: str) -> str:
    supported = get_models_for_backend(backend)
    preview = ", ".join(supported[:10])
    if len(supported) > 10:
        preview += " ..."
    return (
        f"模型与后端不匹配: 当前后端={backend}, 当前模型={model_id}。"
        f"该后端可用模型示例: {preview or '无'}"
    )


def _append_cross_backend_hint(message: str, backend: str, model_id: str) -> str:
    variants = get_installed_variants(model_id)
    others = [item for item in variants if str(item.get("backend") or "").strip().lower() != backend]
    if not others:
        return message
    hint = "；检测到同名模型已安装在其它后端: " + ", ".join(
        f"{item.get('backend')}/{item.get('model_id')} ({item.get('local_path')})" for item in others
    )
    return f"{message}{hint}。请切换后端或下载当前后端对应模型。"


def run_transcription_model_test(
    mode: str = "full",
    backend: Optional[str] = None,
    model_id: Optional[str] = None,
) -> Dict:
    safe_mode = str(mode or "full").strip().lower()
    if safe_mode not in {"full", "hash", "warmup"}:
        safe_mode = "full"

    current = get_transcription_config()
    transcription = current.get("transcription") or {}
    chosen_backend = str(backend or transcription.get("backend") or "faster_whisper").strip().lower()
    chosen_model_id = str(model_id or transcription.get("active_model") or "large-v3").strip().lower()

    result = {
        "ok": False,
        "backend": chosen_backend,
        "model_id": chosen_model_id,
        "mode": safe_mode,
        "steps": [],
    }
    installed_variants = get_installed_variants(chosen_model_id)

    result["steps"].append(
        {
            "name": "resolve",
            "ok": True,
            "checks": [
                {
                    "name": "target",
                    "status": "passed",
                    "message": f"当前测试目标: {chosen_backend}/{chosen_model_id}",
                },
                {
                    "name": "installed_variants",
                    "status": "passed",
                    "message": (
                        "已安装变体: "
                        + (
                            ", ".join(
                                f"{item.get('backend')}/{item.get('model_id')}" for item in installed_variants
                            )
                            if installed_variants
                            else "无"
                        )
                    ),
                },
            ],
        }
    )

    if not model_is_supported_by_backend(chosen_backend, chosen_model_id):
        result["steps"].append(
            {
                "name": "hash",
                "ok": False,
                "checks": [
                    {
                        "name": "hash",
                        "status": "failed",
                        "message": _build_backend_mismatch_error(chosen_backend, chosen_model_id),
                    }
                ],
            }
        )
        result["error"] = _build_backend_mismatch_error(chosen_backend, chosen_model_id)
        logger.error("Model/backend mismatch: %s/%s", chosen_backend, chosen_model_id)
        return result

    try:
        model_entry = resolve_model_entry(chosen_backend, chosen_model_id)
    except Exception as exc:
        logger.error("Model resolve failed: %s", exc)
        result["error"] = str(exc)
        return result

    hash_res = verify_model_hashes(model_entry)
    result["steps"].append({"name": "hash", **hash_res})
    if not hash_res.get("ok"):
        result["error"] = _append_cross_backend_hint(
            _pick_hash_error_message(hash_res),
            chosen_backend,
            chosen_model_id,
        )
        logger.error("Model hash validation failed: %s/%s (%s)", chosen_backend, chosen_model_id, result["error"])
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
