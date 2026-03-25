import logging
from pathlib import Path
from typing import Dict, List, Optional

import requests

logger = logging.getLogger("ADMIN_MODEL_CATALOG")

_STORAGE_ROOT = Path("/workspace/storage/models/transcription")
_FASTER_STORAGE_ROOT = _STORAGE_ROOT / "faster-whisper"

_FASTER_MODELS = [
    {"id": "tiny", "repo": "Systran/faster-whisper-tiny"},
    {"id": "tiny.en", "repo": "Systran/faster-whisper-tiny.en"},
    {"id": "base", "repo": "Systran/faster-whisper-base"},
    {"id": "base.en", "repo": "Systran/faster-whisper-base.en"},
    {"id": "small", "repo": "Systran/faster-whisper-small"},
    {"id": "small.en", "repo": "Systran/faster-whisper-small.en"},
    {"id": "medium", "repo": "Systran/faster-whisper-medium"},
    {"id": "medium.en", "repo": "Systran/faster-whisper-medium.en"},
    {"id": "large-v1", "repo": "Systran/faster-whisper-large-v1"},
    {"id": "large-v2", "repo": "Systran/faster-whisper-large-v2"},
    {"id": "large-v3", "repo": "Systran/faster-whisper-large-v3"},
    {"id": "distil-large-v2", "repo": "Systran/faster-distil-whisper-large-v2"},
    {"id": "distil-large-v3", "repo": "Systran/faster-distil-whisper-large-v3"},
]
_FASTER_MODEL_IDS = [item["id"] for item in _FASTER_MODELS]

_FASTER_REQUIRED_FILES = [
    "config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.json",
    "preprocessor_config.json",
]

def get_storage_roots() -> Dict[str, Path]:
    return {
        "root": _STORAGE_ROOT,
        "faster": _FASTER_STORAGE_ROOT,
    }


def get_faster_required_files() -> List[str]:
    return list(_FASTER_REQUIRED_FILES)


def get_models_for_backend(backend: str) -> List[str]:
    safe_backend = str(backend or "").strip().lower()
    if safe_backend == "faster_whisper":
        return list(_FASTER_MODEL_IDS)
    return []


def model_is_supported_by_backend(backend: str, model_id: str) -> bool:
    safe_model_id = str(model_id or "").strip().lower()
    if not safe_model_id:
        return False
    return safe_model_id in set(get_models_for_backend(backend))


def get_installed_variants(model_id: str) -> List[Dict]:
    safe_model_id = str(model_id or "").strip().lower()
    out: List[Dict] = []
    if not safe_model_id:
        return out

    entry = get_model_entry("faster_whisper", safe_model_id)
    if entry and entry.get("installed"):
        out.append(
            {
                "backend": "faster_whisper",
                "model_id": safe_model_id,
                "engine": str(entry.get("engine") or ""),
                "local_path": str(entry.get("local_path") or ""),
            }
        )
    return out


def build_faster_model_entry(model_id: str) -> Optional[Dict]:
    meta = next((item for item in _FASTER_MODELS if item["id"] == model_id), None)
    if not meta:
        return None
    local_dir = _FASTER_STORAGE_ROOT / model_id
    model_bin = local_dir / "model.bin"
    return {
        "model_id": model_id,
        "label": model_id,
        "backend": "faster_whisper",
        "engine": "faster-whisper",
        "source": "huggingface",
        "repo_id": meta["repo"],
        "local_path": str(local_dir),
        "installed": model_bin.exists(),
        "required_files": get_faster_required_files(),
    }


def get_model_entry(backend: str, model_id: str) -> Optional[Dict]:
    backend = str(backend or "").strip().lower()
    model_id = str(model_id or "").strip()
    if backend == "faster_whisper":
        return build_faster_model_entry(model_id)
    return None


def list_transcription_models() -> List[Dict]:
    rows: List[Dict] = []
    for item in _FASTER_MODELS:
        model = build_faster_model_entry(item["id"])
        if model:
            rows.append(model)
    return rows


def fetch_hf_model_files(repo_id: str) -> Dict[str, Dict]:
    endpoint = f"https://huggingface.co/api/models/{repo_id}?blobs=true"
    response = requests.get(endpoint, timeout=20)
    response.raise_for_status()
    payload = response.json() or {}
    siblings = payload.get("siblings") or []
    out: Dict[str, Dict] = {}
    for item in siblings:
        name = str(item.get("rfilename") or "").strip()
        if not name:
            continue
        lfs = item.get("lfs") or {}
        blob_id = str(item.get("blobId") or "").strip().lower()
        sha256 = str((lfs.get("sha256") or lfs.get("oid") or "")).strip().lower()
        size = int((lfs.get("size") or item.get("size") or 0) or 0)
        out[name] = {
            "sha256": sha256,
            "blob_id": blob_id,
            "size": size,
            "url": f"https://huggingface.co/{repo_id}/resolve/main/{name}?download=true",
        }
    return out
