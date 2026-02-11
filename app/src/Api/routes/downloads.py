from flask import Blueprint, jsonify, request

from ..services.video_download import run_direct_video_download

bp = Blueprint("api_downloads", __name__)


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
