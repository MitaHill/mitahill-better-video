import ast
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger("ADMIN_MODEL_CATALOG")

_STORAGE_ROOT = Path("/workspace/storage/models/transcription")
_OPENAI_STORAGE_ROOT = _STORAGE_ROOT / "whisper-openai"
_FASTER_STORAGE_ROOT = _STORAGE_ROOT / "faster-whisper"

_OPENAI_REGISTRY_URL = "https://raw.githubusercontent.com/openai/whisper/main/whisper/__init__.py"
_OPENAI_REGISTRY_CACHE_SECONDS = 900

_OPENAI_FALLBACK_URLS = {
    "tiny": "https://openaipublic.azureedge.net/main/whisper/models/tiny.pt",
    "tiny.en": "https://openaipublic.azureedge.net/main/whisper/models/tiny.en.pt",
    "base": "https://openaipublic.azureedge.net/main/whisper/models/base.pt",
    "base.en": "https://openaipublic.azureedge.net/main/whisper/models/base.en.pt",
    "small": "https://openaipublic.azureedge.net/main/whisper/models/small.pt",
    "small.en": "https://openaipublic.azureedge.net/main/whisper/models/small.en.pt",
    "medium": "https://openaipublic.azureedge.net/main/whisper/models/medium.pt",
    "medium.en": "https://openaipublic.azureedge.net/main/whisper/models/medium.en.pt",
    "large-v1": "https://openaipublic.azureedge.net/main/whisper/models/large-v1.pt",
    "large-v2": "https://openaipublic.azureedge.net/main/whisper/models/large-v2.pt",
    "large-v3": "https://openaipublic.azureedge.net/main/whisper/models/large-v3.pt",
    "large": "https://openaipublic.azureedge.net/main/whisper/models/large-v2.pt",
    "turbo": "https://openaipublic.azureedge.net/main/whisper/models/turbo.pt",
    "large-v3-turbo": "https://openaipublic.azureedge.net/main/whisper/models/turbo.pt",
}

_OPENAI_MODEL_IDS = [
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
    "turbo",
    "large-v3-turbo",
]

_OPENAI_LOCAL_ALIASES = {
    "turbo": ["large-v3-turbo.pt"],
    "large-v3-turbo": ["turbo.pt"],
    "large": ["large-v2.pt"],
}

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

_openai_registry_cache = {"at": 0.0, "payload": {}}


def _extract_sha_from_url(url: str) -> str:
    parsed = urlparse(str(url or ""))
    segments = [seg for seg in parsed.path.split("/") if seg]
    # Expected format: .../models/<sha>/<filename>
    if len(segments) >= 2 and segments[-2] and len(segments[-2]) >= 32:
        return segments[-2]
    return ""


def _extract_filename(url: str, fallback: str) -> str:
    parsed = urlparse(str(url or ""))
    name = (Path(parsed.path).name or "").strip()
    if name:
        return name
    return fallback


def get_storage_roots() -> Dict[str, Path]:
    return {
        "root": _STORAGE_ROOT,
        "openai": _OPENAI_STORAGE_ROOT,
        "faster": _FASTER_STORAGE_ROOT,
    }


def get_faster_required_files() -> List[str]:
    return list(_FASTER_REQUIRED_FILES)


def get_models_for_backend(backend: str) -> List[str]:
    safe_backend = str(backend or "").strip().lower()
    if safe_backend == "whisper":
        return list(_OPENAI_MODEL_IDS)
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

    for backend in ("whisper", "faster_whisper"):
        entry = get_model_entry(backend, safe_model_id)
        if not entry or not entry.get("installed"):
            continue
        out.append(
            {
                "backend": backend,
                "model_id": safe_model_id,
                "engine": str(entry.get("engine") or ""),
                "local_path": str(entry.get("local_path") or ""),
            }
        )
    return out


def _fetch_openai_registry_remote() -> Dict[str, str]:
    try:
        response = requests.get(_OPENAI_REGISTRY_URL, timeout=12)
        response.raise_for_status()
    except Exception as exc:
        logger.warning("Failed to fetch whisper registry from upstream: %s", exc)
        return {}

    try:
        tree = ast.parse(response.text)
    except SyntaxError as exc:
        logger.warning("Failed to parse whisper registry python source: %s", exc)
        return {}

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not node.targets:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id != "_MODELS":
            continue
        try:
            payload = ast.literal_eval(node.value)
        except Exception as exc:
            logger.warning("Failed to parse _MODELS from whisper source: %s", exc)
            return {}
        if isinstance(payload, dict):
            return {str(k): str(v) for k, v in payload.items()}
    return {}


def get_openai_registry() -> Dict[str, str]:
    now = time.time()
    if now - float(_openai_registry_cache["at"] or 0.0) < _OPENAI_REGISTRY_CACHE_SECONDS:
        return dict(_openai_registry_cache["payload"] or {})

    remote = _fetch_openai_registry_remote()
    if remote:
        _openai_registry_cache["at"] = now
        _openai_registry_cache["payload"] = remote
        return dict(remote)

    if not _openai_registry_cache["payload"]:
        _openai_registry_cache["payload"] = dict(_OPENAI_FALLBACK_URLS)
        _openai_registry_cache["at"] = now
    return dict(_openai_registry_cache["payload"])


def build_openai_model_entry(model_id: str) -> Dict:
    registry = get_openai_registry()
    fallback = _OPENAI_FALLBACK_URLS.get(model_id, "")
    url = registry.get(model_id) or fallback
    filename = _extract_filename(url, f"{model_id}.pt")
    expected_sha = _extract_sha_from_url(url)
    candidate_names = [filename, f"{model_id}.pt", *(_OPENAI_LOCAL_ALIASES.get(model_id) or [])]
    dedup_names: List[str] = []
    for item in candidate_names:
        safe_name = str(item or "").strip()
        if safe_name and safe_name not in dedup_names:
            dedup_names.append(safe_name)
    candidate_paths = [_OPENAI_STORAGE_ROOT / item for item in dedup_names]
    local_path = next((path for path in candidate_paths if path.exists()), candidate_paths[0])
    return {
        "model_id": model_id,
        "label": model_id,
        "backend": "whisper",
        "engine": "openai-whisper",
        "source": "openai",
        "download_url": url,
        "expected_sha256": expected_sha,
        "local_path": str(local_path),
        "local_candidates": [str(path) for path in candidate_paths],
        "installed": any(path.exists() for path in candidate_paths),
        "required_files": [filename],
    }


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
    if backend == "whisper":
        return build_openai_model_entry(model_id)
    if backend == "faster_whisper":
        return build_faster_model_entry(model_id)
    return None


def list_transcription_models() -> List[Dict]:
    rows: List[Dict] = []
    for model_id in _OPENAI_MODEL_IDS:
        rows.append(build_openai_model_entry(model_id))
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
