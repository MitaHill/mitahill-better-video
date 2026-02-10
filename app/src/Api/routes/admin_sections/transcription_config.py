from flask import Blueprint, jsonify, request

from ...services.admin import get_transcription_config, update_transcription_config
from ...services.admin_auth import get_admin_session

bp = Blueprint("api_admin_transcription_config", __name__)


@bp.get("/api/admin/config/transcription-sources")
def admin_get_transcription_sources_config():
    _session, err = get_admin_session(request)
    if err:
        return jsonify({"error": err}), 401
    return jsonify(get_transcription_config())


@bp.put("/api/admin/config/transcription-sources")
def admin_update_transcription_sources_config():
    _session, err = get_admin_session(request)
    if err:
        return jsonify({"error": err}), 401
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid request payload"}), 400
    try:
        updated = update_transcription_config(payload)
    except Exception as exc:
        return jsonify({"error": f"failed to update config: {exc}"}), 400
    return jsonify({"ok": True, "config": updated})
