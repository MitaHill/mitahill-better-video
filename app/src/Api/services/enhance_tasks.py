from pathlib import Path

from app.src.Database import core as db
from app.src.Utils.http import ffprobe_info, is_filename_safe, secure_filename


def create_enhance_task(upload, params, client_ip, output_root, upload_root, max_video_mb, max_image_mb, logger):
    if not upload.filename or not is_filename_safe(upload.filename):
        return None, "invalid filename"

    import uuid

    task_id = uuid.uuid4().hex
    run_dir = output_root / f"run_{task_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    upload_dir = upload_root / f"run_{task_id}"
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = secure_filename(upload.filename)
    input_path = upload_dir / filename
    upload.save(input_path)

    input_type = params["input_type"]
    size_mb = input_path.stat().st_size / (1024 * 1024)
    max_mb = max_video_mb if input_type == "Video" else max_image_mb
    if size_mb > max_mb:
        input_path.unlink(missing_ok=True)
        db.create_task(
            task_id,
            client_ip,
            {**params, "filename": filename, "upload_path": str(input_path)},
            {},
            task_category="enhance",
        )
        db.update_task_status(task_id, "FAILED", progress=0, message=f"file exceeds limit ({max_mb} MB)")
        return task_id, f"file exceeds limit ({max_mb} MB)"

    if input_type == "Video":
        info = ffprobe_info(input_path)
    else:
        info = {"width": 0, "height": 0, "fps": 0, "duration": 0, "video_codec": None, "audio_codec": None}

    video_info = {
        "size_mb": round(size_mb, 2),
        "filename": filename,
        "upload_path": str(input_path),
        **info,
    }

    if input_type == "Video":
        video_codec = (video_info.get("video_codec") or "").lower()
        audio_codec = (video_info.get("audio_codec") or "").lower()
        if video_codec == "mpeg2video" and not params.get("deinterlace"):
            params["deinterlace"] = True
            params["mpeg2_adapted"] = True
        else:
            params["mpeg2_adapted"] = False
        if video_codec == "mpeg2video" and audio_codec == "mp2":
            logger.info("MPEG2 + MP2 detected for task %s; allowing non-AAC audio.", task_id)

    task_params = {
        **params,
        "filename": filename,
        "upload_path": str(input_path),
        "source_video_codec": video_info.get("video_codec"),
    }

    db.create_task(task_id, client_ip, task_params, video_info, task_category="enhance")

    if input_type == "Video":
        video_codec = (video_info.get("video_codec") or "").lower()
        allowed_video = {"h264", "hevc", "h265", "mpeg2video"}
        if not video_codec or video_codec not in allowed_video:
            reject_reason = "仅支持 H.264/H.265/MPEG2 视频编码（拒绝 AV1/VP9 等非主流编码）。"
            db.update_task_status(task_id, "FAILED", progress=0, message=reject_reason)
            return task_id, reject_reason

    return task_id, None


def find_result_file(task, output_root):
    result_path = task.get("result_path")
    if result_path:
        path = Path(result_path)
        if path.exists():
            return path

    import json

    params = json.loads(task.get("task_params", "{}"))
    filename = params.get("filename")
    if not filename:
        run_results = output_root / f"run_{task['task_id']}" / "results"
        zipped = sorted(run_results.glob("*.zip")) if run_results.exists() else []
        return zipped[0] if zipped else None
    stem = Path(filename).stem
    results = list(output_root.glob(f"sr_{stem}.*"))
    return results[0] if results else None
