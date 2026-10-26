from flask import Blueprint, jsonify, request

from ..constants import UPLOAD_ROOT
from ..services import probe_uploaded_media

bp = Blueprint("api_conversions", __name__)


@bp.post("/api/media/probe")
def probe_media():
    upload = request.files.get("file")
    info, err = probe_uploaded_media(upload, UPLOAD_ROOT)
    if err:
        return jsonify({"error": err}), 400
    return jsonify(info)
