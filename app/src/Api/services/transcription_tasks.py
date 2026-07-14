from pathlib import Path

from app.src.Database import core as db
from app.src.Utils.http import ffprobe_info

from .uploads import new_task_dirs, save_uploaded_files
from .batch_tasks import add_batch_item, create_batch


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


def _create_transcription_task_from_files(media_files, client_ip, params, output_root, upload_root, max_upload_mb):
    if not media_files:
        return None, "at least one audio/video media file is required"

    task_id, run_dir, upload_dir = new_task_dirs(output_root, upload_root)
    media_dir = upload_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    saved, err = save_uploaded_files(media_files, media_dir, max_upload_mb)
    if err:
        return None, err
    if not saved:
        return None, "no valid media files"

    task_params = dict(params)
    task_params["media_files"] = saved
    first_media = Path(saved[0]["upload_path"])
    first_info = ffprobe_info(first_media)
    video_info = {
        "filename": saved[0]["filename"],
        "upload_path": saved[0]["upload_path"],
        "size_mb": saved[0]["size_mb"],
        "media_count": len(saved),
        **first_info,
    }
    db.create_task(task_id, client_ip, task_params, video_info, task_category="transcribe")
    return task_id, None


def create_transcription_task(req, client_ip, params, output_root, upload_root, max_upload_mb):
    media_files = _collect_transcription_uploads(req)
    return _create_transcription_task_from_files(
        media_files,
        client_ip,
        params,
        output_root,
        upload_root,
        max_upload_mb,
    )


def create_transcription_tasks(req, client_ip, params, output_root, upload_root, max_upload_mb):
    media_files = _collect_transcription_uploads(req)
    if not media_files:
        return None, [], [{"error": "at least one audio/video media file is required"}]
    if len(media_files) == 1:
        task_id, err = _create_transcription_task_from_files(
            media_files,
            client_ip,
            params,
            output_root,
            upload_root,
            max_upload_mb,
        )
        errors = [{"filename": media_files[0].filename, "error": err, "task_id": task_id}] if err else []
        return None, [task_id] if task_id else [], errors

    batch_id = None
    task_ids = []
    errors = []
    for upload in media_files:
        task_id, err = _create_transcription_task_from_files(
            [upload],
            client_ip,
            params,
            output_root,
            upload_root,
            max_upload_mb,
        )
        if task_id:
            if not batch_id:
                batch_id = create_batch("transcribe")
            task_ids.append(task_id)
            add_batch_item(batch_id, task_id, "transcribe", upload.filename or task_id)
        if err:
            errors.append({"filename": upload.filename, "error": err, "task_id": task_id})
    return batch_id, task_ids, errors
