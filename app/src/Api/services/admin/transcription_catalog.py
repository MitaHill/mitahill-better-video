from pathlib import Path
from typing import Dict, List, Optional

from app.src.Data.transcription_models import WHISPER_MODELS, get_whisper_model

_STORAGE_ROOT = Path("/workspace/storage/models/transcription")
_WHISPER_STORAGE_ROOT = _STORAGE_ROOT / "whisper"


def get_storage_roots() -> Dict[str, Path]:
    return {
        "root": _STORAGE_ROOT,
        "whisper": _WHISPER_STORAGE_ROOT,
    }


def get_models_for_backend(backend: str) -> List[str]:
    return list(WHISPER_MODELS) if str(backend or "").strip().lower() == "whisper" else []


def model_is_supported_by_backend(backend: str, model_id: str) -> bool:
    return str(model_id or "").strip().lower() in set(get_models_for_backend(backend))


def get_installed_variants(model_id: str) -> List[Dict]:
    entry = get_model_entry("whisper", model_id)
    if not entry or not entry.get("installed"):
        return []
    return [
        {
            "backend": "whisper",
            "model_id": entry["model_id"],
            "engine": "faster-whisper",
            "local_path": str(entry["local_path"]),
        }
    ]


def build_whisper_model_entry(model_id: str) -> Optional[Dict]:
    safe_model_id = str(model_id or "").strip().lower()
    model = get_whisper_model(safe_model_id)
    if not model:
        return None

    local_path = _WHISPER_STORAGE_ROOT / safe_model_id
    required_files = ["model.bin", "config.json", "tokenizer.json", model["vocabulary"]]
    source = f"https://huggingface.co/{model['repository']}/resolve/main"
    return {
        "model_id": safe_model_id,
        "label": safe_model_id,
        "backend": "whisper",
        "engine": "faster-whisper",
        "source": "huggingface",
        "local_path": str(local_path),
        "download_files": [
            {"name": name, "url": f"{source}/{name}"}
            for name in required_files
        ],
        "required_files": required_files,
        "installed": all((local_path / name).is_file() for name in required_files),
    }


def get_model_entry(backend: str, model_id: str) -> Optional[Dict]:
    if str(backend or "").strip().lower() == "whisper":
        return build_whisper_model_entry(model_id)
    return None


def list_transcription_models() -> List[Dict]:
    return [build_whisper_model_entry(model_id) for model_id in WHISPER_MODELS]
