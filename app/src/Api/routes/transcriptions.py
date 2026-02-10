from flask import Blueprint, jsonify, request

from app.src.Config import settings as config
from app.src.Database import core as db

from ..constants import OUTPUT_ROOT, UPLOAD_ROOT
from ..parsers import parse_transcription_task_params
from ..services import create_transcription_task
from ..services.form_constraints import apply_constraints_to_params
from ..services.real_ip import resolve_request_client_ip

bp = Blueprint("api_transcriptions", __name__)


@bp.post("/api/transcriptions")
def create_transcription():
    client_ip = resolve_request_client_ip(request)
    params = parse_transcription_task_params(request.form)
    params, err = apply_constraints_to_params("transcribe", params)
    if err:
        return jsonify({"error": err}), 400
    task_id, err = create_transcription_task(
        request,
        client_ip,
        params,
        OUTPUT_ROOT,
        UPLOAD_ROOT,
        config.MAX_VIDEO_SIZE_MB,
    )
    if err:
        if task_id:
            db.update_task_status(task_id, "FAILED", progress=0, message=err)
        return jsonify({"error": err, "task_id": task_id}), 400
    return jsonify({"task_id": task_id}), 201
