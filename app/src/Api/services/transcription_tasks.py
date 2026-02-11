from pathlib import Path

from app.src.Database import core as db
from app.src.Utils.http import ffprobe_info

from .uploads import save_uploaded_files


def _collect_transcription_uploads(req):
    files = req.files.getlist("media_files")
    if files:
        return files
    files = req.files.getlist("files")
    if files:
        return files
    one = req.files.get("file")
    if one:
        return [one]
    videos = req.files.getlist("videos") or req.files.getlist("video")
    audios = req.files.getlist("audios") or req.files.getlist("audio")
    return [*videos, *audios]


def create_transcription_task(req, client_ip, params, output_root, upload_root, max_upload_mb):
    media_files = _collect_transcription_uploads(req)
    if not media_files:
        return None, "at least one audio/video media file is required"

    import uuid

    task_id = uuid.uuid4().hex
    run_dir = output_root / f"run_{task_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    upload_dir = upload_root / f"run_{task_id}"
    upload_dir.mkdir(parents=True, exist_ok=True)
    media_dir = upload_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    saved, err = save_uploaded_files(media_files, media_dir, max_upload_mb)
    if err:
        return None, err
    if not saved:
        return None, "no valid media files"

    params["media_files"] = saved
    first_media = Path(saved[0]["upload_path"])
    first_info = ffprobe_info(first_media)
    video_info = {
        "filename": saved[0]["filename"],
        "upload_path": saved[0]["upload_path"],
        "size_mb": saved[0]["size_mb"],
        "media_count": len(saved),
        **first_info,
    }
    db.create_task(task_id, client_ip, params, video_info, task_category="transcribe")
    return task_id, None
