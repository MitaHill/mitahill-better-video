from flask import Blueprint, jsonify, request

from ..constants import OUTPUT_ROOT
from ..parsers import parse_download_task_params
from ..services import create_download_task
from ..services.form_constraints import apply_constraints_to_params
from ..services.real_ip import resolve_request_client_ip
from ..services.video_download import probe_download_source, run_direct_video_download

bp = Blueprint("api_downloads", __name__)


@bp.post("/api/downloads/probe")
def probe_download():
    payload = request.get_json(silent=True) or {}
    if not payload:
        payload = request.form or {}
    url = payload.get("url") or payload.get("source_url")
    try:
        result = probe_download_source(url=url)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(result), 200


@bp.post("/api/downloads/tasks")
def create_download_task_route():
    payload = request.get_json(silent=True) or {}
    params = parse_download_task_params(request.form if request.form else payload)
    params, err = apply_constraints_to_params("download", params)
    if err:
        return jsonify({"error": err}), 400
    client_ip = resolve_request_client_ip(request)
    task_id, err = create_download_task(client_ip, params, OUTPUT_ROOT)
    if err:
        return jsonify({"error": err}), 400
    return jsonify({"task_id": task_id}), 201


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
