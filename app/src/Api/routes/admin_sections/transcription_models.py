from flask import Blueprint, jsonify, request

from ...services.admin import (
    cancel_download_job,
    delete_download_job,
    get_download_job,
    list_download_jobs,
    list_transcription_models,
    start_model_download,
)
from ...services.admin_auth import get_admin_session

bp = Blueprint("api_admin_transcription_models", __name__)


@bp.get("/api/admin/transcription/models")
def admin_list_transcription_models():
    _session, err = get_admin_session(request)
    if err:
        return jsonify({"error": err}), 401
    return jsonify({"models": list_transcription_models()})


@bp.post("/api/admin/transcription/models/download")
def admin_start_model_download():
    _session, err = get_admin_session(request)
    if err:
        return jsonify({"error": err}), 401
    payload = request.get_json(silent=True) or {}
    model_id = str(payload.get("model_id") or "").strip().lower()
    backend = str(payload.get("backend") or "").strip().lower()
    if not model_id or not backend:
        return jsonify({"error": "model_id and backend are required"}), 400
    try:
        job = start_model_download(model_id=model_id, backend=backend, request_payload=payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "job": job})


@bp.get("/api/admin/transcription/models/downloads")
def admin_list_model_downloads():
    _session, err = get_admin_session(request)
    if err:
        return jsonify({"error": err}), 401
    limit = request.args.get("limit", type=int) or 50
    return jsonify({"jobs": list_download_jobs(limit=limit)})


@bp.get("/api/admin/transcription/models/downloads/<job_id>")
def admin_get_model_download(job_id: str):
    _session, err = get_admin_session(request)
    if err:
        return jsonify({"error": err}), 401
    payload = get_download_job(job_id)
    if not payload:
        return jsonify({"error": "job not found"}), 404
    return jsonify({"job": payload})


@bp.post("/api/admin/transcription/models/downloads/<job_id>/cancel")
def admin_cancel_model_download(job_id: str):
    _session, err = get_admin_session(request)
    if err:
        return jsonify({"error": err}), 401
    try:
        payload = cancel_download_job(job_id)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "job": payload})


@bp.delete("/api/admin/transcription/models/downloads/<job_id>")
def admin_delete_model_download(job_id: str):
    _session, err = get_admin_session(request)
    if err:
        return jsonify({"error": err}), 401
    try:
        deleted = delete_download_job(job_id)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": bool(deleted), "job_id": job_id})
