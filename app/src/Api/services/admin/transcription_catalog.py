from pathlib import Path
from typing import Dict, List, Optional

_STORAGE_ROOT = Path("/workspace/storage/models/transcription")
_WHISPER_STORAGE_ROOT = _STORAGE_ROOT / "whisper"
_MODEL_ID = "large-v3"
_MODEL_SOURCE = "https://huggingface.co/Systran/faster-whisper-large-v3/resolve/main"
_MODEL_FILES = ("model.bin", "config.json", "tokenizer.json", "vocabulary.json")


def get_storage_roots() -> Dict[str, Path]:
    return {
        "root": _STORAGE_ROOT,
        "whisper": _WHISPER_STORAGE_ROOT,
    }


def get_models_for_backend(backend: str) -> List[str]:
    return [_MODEL_ID] if str(backend or "").strip().lower() == "whisper" else []


def model_is_supported_by_backend(backend: str, model_id: str) -> bool:
    return str(model_id or "").strip().lower() in set(get_models_for_backend(backend))


def get_installed_variants(model_id: str) -> List[Dict]:
    entry = get_model_entry("whisper", model_id)
    if not entry or not entry.get("installed"):
        return []
    return [
        {
            "backend": "whisper",
            "model_id": _MODEL_ID,
            "engine": "faster-whisper",
            "local_path": str(entry["local_path"]),
        }
    ]


def build_whisper_model_entry(model_id: str) -> Optional[Dict]:
    if str(model_id or "").strip().lower() != _MODEL_ID:
        return None

    local_path = _WHISPER_STORAGE_ROOT / _MODEL_ID
    required_files = list(_MODEL_FILES)
    return {
        "model_id": _MODEL_ID,
        "label": _MODEL_ID,
        "backend": "whisper",
        "engine": "faster-whisper",
        "source": "huggingface",
        "local_path": str(local_path),
        "download_files": [
            {"name": name, "url": f"{_MODEL_SOURCE}/{name}"}
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
    model = build_whisper_model_entry(_MODEL_ID)
    return [model] if model else []
