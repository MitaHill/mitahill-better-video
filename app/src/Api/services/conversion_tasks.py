from pathlib import Path

from app.src.Database import core as db
from app.src.Utils.http import ffprobe_info, is_filename_safe, secure_filename

from .uploads import classify_media, save_uploaded_files


def _collect_conversion_uploads(req):
    files = req.files.getlist("media_files")
    if files:
        return files
    files = req.files.getlist("files")
    if files:
        return files
    videos = req.files.getlist("videos") or req.files.getlist("video")
    audios = req.files.getlist("audios") or req.files.getlist("audio")
    return [*videos, *audios]


def _save_watermark_images(req, upload_dir):
    images = req.files.getlist("watermark_images")
    if not images:
        one = req.files.get("watermark_image")
        if one:
            images = [one]
    out = []
    for image in images:
        if not image or not image.filename:
            continue
        if not is_filename_safe(image.filename):
            return None, "invalid watermark image filename"
        wm_name = secure_filename(image.filename)
        wm_path = upload_dir / wm_name
        image.save(wm_path)
        out.append(str(wm_path))
    return out, None


def create_conversion_task(
    req,
    client_ip,
    params,
    output_root,
    upload_root,
    max_upload_mb,
):
    media_files = _collect_conversion_uploads(req)
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
    videos, audios, unknown = classify_media(saved)
    if unknown:
        return None, f"unsupported media files: {', '.join(item['filename'] for item in unknown)}"
    if not videos:
        return None, "at least one valid video file is required"

    watermark_images, err = _save_watermark_images(req, upload_dir)
    if err:
        return None, err

    params["video_files"] = videos
    params["audio_files"] = audios
    params["watermark_images"] = watermark_images

    first_video = Path(videos[0]["upload_path"])
    first_info = ffprobe_info(first_video)
    video_info = {
        "filename": videos[0]["filename"],
        "upload_path": videos[0]["upload_path"],
        "size_mb": videos[0]["size_mb"],
        "video_count": len(videos),
        "audio_count": len(audios),
        **first_info,
    }
    db.create_task(task_id, client_ip, params, video_info, task_category="convert")
    return task_id, None
