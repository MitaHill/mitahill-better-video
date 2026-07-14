from app.src.Database import core as db
from .uploads import new_task_id
from .video_download import normalize_download_url, save_download_cookie_file, snapshot_download_cookie
from .batch_tasks import add_batch_item, create_batch


def create_download_task(client_ip, params, output_root):
    safe_params = dict(params or {})
    source_url = normalize_download_url(safe_params.get("source_url"))
    safe_params["source_url"] = source_url
    mode = str(safe_params.get("download_mode") or "video").strip().lower()
    if mode not in {"video", "audio", "subtitle_only"}:
        mode = "video"
    safe_params["download_mode"] = mode

    task_id = new_task_id(output_root=output_root)
    run_dir = output_root / f"run_{task_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    cookie_path = snapshot_download_cookie(run_dir)
    if cookie_path:
        safe_params["download_cookie_path"] = cookie_path

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


def create_download_tasks(client_ip, params, output_root, cookie_file=None):
    task_ids = []
    errors = []
    seen = set()
    cookie_saved = False
    batch_id = None
    urls = []
    for raw in str((params or {}).get("source_url", "") or "").splitlines():
        if not raw.strip() or raw.strip() in seen:
            continue
        seen.add(raw.strip())
        urls.append(raw.strip())
    if not urls:
        raise ValueError("url is required")
    for raw in urls:
        try:
            url = normalize_download_url(raw)
        except ValueError as exc:
            errors.append({"url": raw.strip(), "error": str(exc)})
            continue
        if cookie_file and not cookie_saved:
            save_download_cookie_file(cookie_file)
            cookie_saved = True
        task_params = dict(params or {})
        task_params["source_url"] = url
        task_id, err = create_download_task(client_ip, task_params, output_root)
        if err:
            errors.append({"url": url, "error": err})
            continue
        task_ids.append(task_id)
        if len(urls) > 1:
            if not batch_id:
                batch_id = create_batch("download")
            add_batch_item(batch_id, task_id, "download", url)
    return task_ids, errors, batch_id
