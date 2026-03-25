from app.src.Database import core as db
from .uploads import new_task_id
from .video_download import normalize_download_url


def create_download_task(client_ip, params, output_root):
    safe_params = dict(params or {})
    safe_params["source_url"] = normalize_download_url(safe_params.get("source_url", ""))
    mode = str(safe_params.get("download_mode") or "video").strip().lower()
    if mode not in {"video", "audio", "subtitle_only"}:
        mode = "video"
    safe_params["download_mode"] = mode

    task_id = new_task_id(output_root=output_root)
    run_dir = output_root / f"run_{task_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    title = str(safe_params.get("source_title") or "").strip()
    video_info = {
        "filename": title or "remote_source",
        "upload_path": str(safe_params.get("source_url") or ""),
        "size_mb": round(float(safe_params.get("source_size_mb") or 0), 2),
        "duration": int(safe_params.get("source_duration_sec") or 0),
        "width": int(safe_params.get("source_width") or 0),
        "height": int(safe_params.get("source_height") or 0),
        "fps": float(safe_params.get("source_fps") or 0),
    }
    db.create_task(task_id, client_ip, safe_params, video_info, task_category="download")
    return task_id, None
