from pathlib import Path
from typing import Dict, List, Optional

import whisper

_STORAGE_ROOT = Path("/workspace/storage/models/transcription")
_WHISPER_STORAGE_ROOT = _STORAGE_ROOT / "whisper"


def _model_urls() -> Dict[str, str]:
    return dict(getattr(whisper, "_MODELS", {}) or {})


def _target_filename(model_id: str, url: str) -> str:
    filename = str(url or "").rstrip("/").split("/")[-1]
    return filename or f"{model_id}.pt"


def _expected_sha256(url: str) -> str:
    parts = str(url or "").split("/")
    if len(parts) >= 2 and len(parts[-2]) == 64:
        return parts[-2].lower()
    return ""


def get_storage_roots() -> Dict[str, Path]:
    return {
        "root": _STORAGE_ROOT,
        "whisper": _WHISPER_STORAGE_ROOT,
    }


def get_models_for_backend(backend: str) -> List[str]:
    safe_backend = str(backend or "").strip().lower()
    if safe_backend == "whisper":
        return list(_model_urls().keys())
    return []


def model_is_supported_by_backend(backend: str, model_id: str) -> bool:
    safe_model_id = str(model_id or "").strip().lower()
    return bool(safe_model_id and safe_model_id in set(get_models_for_backend(backend)))


def get_installed_variants(model_id: str) -> List[Dict]:
    safe_model_id = str(model_id or "").strip().lower()
    out: List[Dict] = []
    if not safe_model_id:
        return out

    entry = get_model_entry("whisper", safe_model_id)
    if entry and entry.get("installed"):
        out.append(
            {
                "backend": "whisper",
                "model_id": safe_model_id,
                "engine": str(entry.get("engine") or ""),
                "local_path": str(entry.get("local_path") or ""),
            }
        )
    return out


def build_whisper_model_entry(model_id: str) -> Optional[Dict]:
    safe_model_id = str(model_id or "").strip().lower()
    url = _model_urls().get(safe_model_id)
    if not url:
        return None

    filename = _target_filename(safe_model_id, url)
    local_path = _WHISPER_STORAGE_ROOT / filename
    return {
        "model_id": safe_model_id,
        "label": safe_model_id,
        "backend": "whisper",
        "engine": "openai-whisper",
        "source": "openai",
        "download_url": url,
        "expected_sha256": _expected_sha256(url),
        "local_path": str(local_path),
        "installed": local_path.exists(),
        "required_files": [filename],
    }


def get_model_entry(backend: str, model_id: str) -> Optional[Dict]:
    safe_backend = str(backend or "").strip().lower()
    if safe_backend == "whisper":
        return build_whisper_model_entry(model_id)
    return None


def list_transcription_models() -> List[Dict]:
    rows: List[Dict] = []
    for model_id in get_models_for_backend("whisper"):
        model = build_whisper_model_entry(model_id)
        if model:
            rows.append(model)
    return rows
