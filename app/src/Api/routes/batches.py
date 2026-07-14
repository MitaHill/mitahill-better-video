from pathlib import Path

from flask import Blueprint, after_this_request, jsonify, send_file

from ..constants import OUTPUT_ROOT
from ..services.batch_tasks import get_batch_status, make_batch_result_zip

bp = Blueprint("api_batches", __name__)


@bp.get("/api/batches/<batch_id>")
def get_batch(batch_id):
    batch = get_batch_status(batch_id)
    if not batch:
        return jsonify({"error": "未找到该批次。", "error_code": "batch_not_found"}), 404
    return jsonify(batch)


@bp.get("/api/batches/<batch_id>/result")
def download_batch_result(batch_id):
    path, err = make_batch_result_zip(batch_id, OUTPUT_ROOT)
    if err:
        return jsonify({"error": err}), 400

    @after_this_request
    def _cleanup(response):
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass
        return response

    return send_file(path, as_attachment=True, download_name=f"batch_{batch_id}.zip")
