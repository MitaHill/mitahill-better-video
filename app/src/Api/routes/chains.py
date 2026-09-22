import json

from flask import Blueprint, current_app, jsonify, request

from ..constants import OUTPUT_ROOT, UPLOAD_ROOT
from ..services.chain_tasks import create_chain
from ..services.real_ip import resolve_request_client_ip

bp = Blueprint("api_chains", __name__)


@bp.post("/api/chains")
def create_task_chain():
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400
    upload = request.files["file"]
    if not upload.filename:
        return jsonify({"error": "filename is required"}), 400

    raw_steps = request.form.get("steps") or ""
    try:
        steps = json.loads(raw_steps)
    except json.JSONDecodeError:
        return jsonify({"error": "steps 必须是合法的 JSON 数组"}), 400

    chain_id, task_ids, err = create_chain(
        upload,
        steps,
        resolve_request_client_ip(request),
        OUTPUT_ROOT,
        UPLOAD_ROOT,
        current_app.logger,
    )
    if err:
        return jsonify({"error": err}), 400
    # 链就是一个批次，状态和结果走 /api/batches/<chain_id>
    return jsonify({"chain_id": chain_id, "task_ids": task_ids}), 201
