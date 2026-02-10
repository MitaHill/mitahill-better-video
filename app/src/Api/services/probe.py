import uuid
from pathlib import Path

from app.src.Utils.http import ffprobe_info, is_filename_safe, secure_filename


def probe_uploaded_media(upload, upload_root, max_mb):
    if not upload or not upload.filename:
        return None, "file is required"
    if not is_filename_safe(upload.filename):
        return None, "invalid filename"

    probe_dir = upload_root / "_probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    filename = secure_filename(upload.filename)
    path = probe_dir / f"{token}_{filename}"
    upload.save(path)
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_mb:
        path.unlink(missing_ok=True)
        return None, f"file exceeds limit ({max_mb} MB)"
    try:
        info = ffprobe_info(path)
        info["filename"] = filename
        info["size_mb"] = round(size_mb, 2)
        return info, None
    finally:
        path.unlink(missing_ok=True)
