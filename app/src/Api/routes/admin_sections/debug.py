from flask import Blueprint, jsonify, request

from ...services.admin import run_transcription_model_test, run_translation_provider_test
from ...services.admin_auth import get_admin_session

bp = Blueprint("api_admin_debug", __name__)


@bp.post("/api/admin/debug/test-transcription-model")
def admin_test_transcription_model():
    _session, err = get_admin_session(request)
    if err:
        return jsonify({"error": err}), 401
    payload = request.get_json(silent=True) or {}
    mode = payload.get("mode")
    result = run_transcription_model_test(mode=mode)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@bp.post("/api/admin/debug/test-translation-provider")
def admin_test_translation_provider():
    _session, err = get_admin_session(request)
    if err:
        return jsonify({"error": err}), 401
    result = run_translation_provider_test()
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code
