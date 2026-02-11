from flask import Blueprint, jsonify, request

from ..services.real_ip import resolve_request_client_ip
from .transcriptions_handlers import build_transcription_runtime_payload, submit_transcription_request

bp = Blueprint("api_transcriptions", __name__)


@bp.post("/api/transcriptions")
def create_transcription():
    client_ip = resolve_request_client_ip(request)
    payload, status = submit_transcription_request(request, client_ip)
    return jsonify(payload), status


@bp.get("/api/transcriptions/runtime-config")
def get_transcription_runtime_config():
    return jsonify(build_transcription_runtime_payload())
