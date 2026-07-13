from flask import Blueprint, jsonify, request

from ..constants import OUTPUT_ROOT
from ..parsers import parse_download_task_params
from ..services import create_download_tasks
from ..services.real_ip import resolve_request_client_ip
from ..services.video_download import (
    get_download_cookie_path,
    probe_download_source,
    run_direct_video_download,
    save_download_cookie_file,
    split_download_urls,
)

bp = Blueprint("api_downloads", __name__)


@bp.post("/api/downloads/probe")
def probe_download():
    payload = request.get_json(silent=True) or {}
    if not payload:
        payload = request.form or {}
    url = payload.get("url") or payload.get("source_url")
    try:
        first_url = split_download_urls(url)[0]
        cookie_path = save_download_cookie_file(request.files.get("cookie_file")) or get_download_cookie_path()
        result = probe_download_source(url=first_url, cookie_path=cookie_path)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(result), 200


@bp.post("/api/downloads/tasks")
def create_download_task_route():
    payload = request.get_json(silent=True) or {}
    params = parse_download_task_params(request.form if request.form else payload)
    client_ip = resolve_request_client_ip(request)
    try:
        task_ids, errors = create_download_tasks(
            client_ip,
            params,
            OUTPUT_ROOT,
            cookie_file=request.files.get("cookie_file"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not task_ids:
        detail = errors[0]["error"] if errors else "下载任务失败"
        return jsonify({"error": detail, "errors": errors}), 400
    payload = {"task_id": task_ids[0], "task_ids": task_ids}
    if errors:
        payload["errors"] = errors
    return jsonify(payload), 201


@bp.post("/api/downloads/direct")
def download_video_direct():
    payload = request.get_json(silent=True) or {}
    if not payload:
        payload = request.form or {}
    url = payload.get("url")
    output_format = payload.get("output_format", "mp4")
    audio_only = payload.get("audio_only", False)
    try:
        result = run_direct_video_download(url=url, output_format=output_format, audio_only=audio_only)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(result), 200
