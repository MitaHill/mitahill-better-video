import uuid
from pathlib import Path

from app.src.Utils.http import ffprobe_info, is_filename_safe, secure_filename


def new_task_dirs(output_root, upload_root):
    task_id = uuid.uuid4().hex
    run_dir = output_root / f"run_{task_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    upload_dir = upload_root / f"run_{task_id}"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return task_id, run_dir, upload_dir


def save_uploaded_files(files, root_dir, max_mb):
    saved = []
    for upload in files:
        if not upload or not upload.filename:
            continue
        if not is_filename_safe(upload.filename):
            return None, f"invalid filename: {upload.filename}"
        filename = secure_filename(upload.filename)
        path = root_dir / filename
        upload.save(path)
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > max_mb:
            path.unlink(missing_ok=True)
            return None, f"file exceeds limit ({max_mb} MB): {filename}"
        info = ffprobe_info(path)
        saved.append(
            {
                "filename": filename,
                "upload_path": str(path),
                "size_mb": round(size_mb, 2),
                **info,
            }
        )
    return saved, None


def classify_media(saved_files):
    videos = []
    audios = []
    unknown = []
    for item in saved_files:
        if item.get("has_video"):
            videos.append(item)
        elif item.get("has_audio"):
            audios.append(item)
        else:
            unknown.append(item)
    return videos, audios, unknown
