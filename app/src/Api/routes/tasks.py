import io
import json
import shutil
from pathlib import Path

from flask import Blueprint, after_this_request, current_app, jsonify, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge

from app.src.Config import settings as config
from app.src.Database import core as db
from app.src.Database import gpu_metrics as db_gpu
from app.src.Utils.preview_cache import get_preview as get_cached_preview

from ..constants import OUTPUT_ROOT, UPLOAD_ROOT
from ..parsers import parse_enhance_task_params
from ..services.real_ip import resolve_request_client_ip
from ..services import create_enhance_task, find_result_file

bp = Blueprint("api_tasks", __name__)
_TASK_PARAM_SENSITIVE_KEYS = {"translator_api_key"}


def _sanitize_task_params(payload):
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    for key in _TASK_PARAM_SENSITIVE_KEYS:
        if key in out and str(out.get(key) or "").strip():
            out[key] = "********"
    return out


def _normalize_utc_timestamp(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace(" ", "T", 1) if "T" not in text and " " in text else text
    if normalized.endswith("Z") or "+" in normalized[-6:] or "-" in normalized[-6:]:
        return normalized
    return f"{normalized}+00:00"


@bp.errorhandler(RequestEntityTooLarge)
def handle_request_too_large(_err):
    limit_mb = max(config.MAX_VIDEO_SIZE_MB, config.MAX_IMAGE_SIZE_MB)
    return jsonify({"error": f"file exceeds limit ({limit_mb} MB)"}), 413


@bp.post("/api/tasks")
def create_task():
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400
    upload = request.files["file"]
    if not upload.filename:
        return jsonify({"error": "filename is required"}), 400
    params = parse_enhance_task_params(request.form)
    client_ip = resolve_request_client_ip(request)
    task_id, err = create_enhance_task(
        upload,
        params,
        client_ip,
        OUTPUT_ROOT,
        UPLOAD_ROOT,
        config.MAX_VIDEO_SIZE_MB,
        config.MAX_IMAGE_SIZE_MB,
        current_app.logger,
    )
    if err:
        return jsonify({"error": err, "task_id": task_id}), 400
    return jsonify({"task_id": task_id}), 201


@bp.post("/api/tasks/batch")
def create_tasks_batch():
    uploads = request.files.getlist("files")
    if not uploads:
        uploads = request.files.getlist("file")
    if not uploads:
        return jsonify({"error": "files are required"}), 400

    params = parse_enhance_task_params(request.form)
    client_ip = resolve_request_client_ip(request)

    task_ids = []
    errors = []
    logger = current_app.logger
    for upload in uploads:
        task_id, err = create_enhance_task(
            upload,
            params,
            client_ip,
            OUTPUT_ROOT,
            UPLOAD_ROOT,
            config.MAX_VIDEO_SIZE_MB,
            config.MAX_IMAGE_SIZE_MB,
            logger,
        )
        if task_id:
            task_ids.append(task_id)
        if err:
            errors.append({"filename": upload.filename, "error": err, "task_id": task_id})
    return jsonify({"task_ids": task_ids, "errors": errors}), 201


@bp.get("/api/tasks/<task_id>")
def get_task(task_id):
    task = db.get_task(task_id)
    if not task:
        return jsonify(
            {
                "error": "未找到该任务。",
                "error_code": "task_not_found",
                "hint": "请确认输入的是正确的 4 位任务 ID，或者该任务已经被系统清理。",
            }
        ), 404
    task["created_at"] = _normalize_utc_timestamp(task.get("created_at"))
    task["updated_at"] = _normalize_utc_timestamp(task.get("updated_at"))
    task["task_params"] = _sanitize_task_params(json.loads(task.get("task_params", "{}")))
    task["video_info"] = json.loads(task.get("video_info", "{}"))
    task["task_progress"] = db.get_task_progress(task_id)
    task["segment_progress"] = db.get_latest_segment_progress(task_id)
    task["gpu_live"] = db_gpu.get_current_gpu_usage()
    return jsonify(task)


@bp.get("/api/tasks/<task_id>/preview/<kind>")
def get_preview(task_id, kind):
    run_dir = OUTPUT_ROOT / f"run_{task_id}"
    if kind == "original":
        path = run_dir / "preview_original.jpg"
    elif kind == "upscaled":
        path = run_dir / "preview_upscaled.jpg"
    else:
        return jsonify({"error": "invalid preview type"}), 400
    payload, _frame = get_cached_preview(task_id, kind)
    if payload:
        resp = send_file(io.BytesIO(payload), mimetype="image/jpeg")
    elif path.exists():
        resp = send_file(path, mimetype="image/jpeg")
    else:
        return jsonify({"error": "preview not ready"}), 404
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


@bp.get("/api/tasks/<task_id>/result")
def download_result(task_id):
    task = db.get_task(task_id)
    if not task or task.get("status") != "COMPLETED":
        return jsonify({"error": "result not available"}), 404
    path = find_result_file(task, OUTPUT_ROOT)
    if not path:
        return jsonify({"error": "output missing"}), 404
    category = str(task.get("task_category") or "").strip().lower()

    if category == "download":
        @after_this_request
        def _cleanup_download_result(response):
            try:
                if path.exists():
                    path.unlink(missing_ok=True)
            except Exception:
                pass
            try:
                run_dir = OUTPUT_ROOT / f"run_{task_id}"
                if run_dir.exists():
                    shutil.rmtree(run_dir, ignore_errors=True)
            except Exception:
                pass
            try:
                db.update_task_result(task_id, "")
                db.update_task_status(task_id, "COMPLETED", progress=100, message="已下载，临时文件已清理")
            except Exception:
                pass
            return response

    return send_file(path, as_attachment=True, download_name=Path(path).name)
