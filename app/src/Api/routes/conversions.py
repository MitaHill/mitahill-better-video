from flask import Blueprint, jsonify, request

from app.src.Config import settings as config
from app.src.Database import core as db
from app.src.Utils.client_ip import resolve_client_ip

from ..constants import OUTPUT_ROOT, UPLOAD_ROOT
from ..parsers import parse_conversion_task_params
from ..services import create_conversion_task, probe_uploaded_media

bp = Blueprint("api_conversions", __name__)


@bp.post("/api/conversions")
def create_conversion():
    client_ip = resolve_client_ip(request, config.REAL_IP_TRUSTED_PROXIES)
    params = parse_conversion_task_params(request.form)
    task_id, err = create_conversion_task(
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


@bp.post("/api/media/probe")
def probe_media():
    upload = request.files.get("file")
    info, err = probe_uploaded_media(upload, UPLOAD_ROOT, max(config.MAX_VIDEO_SIZE_MB, config.MAX_IMAGE_SIZE_MB))
    if err:
        return jsonify({"error": err}), 400
    return jsonify(info)
