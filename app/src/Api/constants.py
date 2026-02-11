from pathlib import Path

STORAGE_ROOT = Path("/workspace/storage")
OUTPUT_ROOT = STORAGE_ROOT / "output"
UPLOAD_ROOT = STORAGE_ROOT / "upload"
FRONTEND_DIST_DIR = Path(__file__).resolve().parents[3] / "app/WebUI/dist"
