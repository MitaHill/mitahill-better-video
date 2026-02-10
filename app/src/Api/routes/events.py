from flask import Blueprint, current_app, jsonify, request

from app.src.Config import settings as config
from app.src.Utils.client_ip import describe_ip, resolve_client_ip

bp = Blueprint("api_events", __name__)


@bp.post("/api/events")
def ingest_events():
    token = request.headers.get("X-Event-Token", "").strip()
    if config.EVENTS_SHARED_TOKEN:
        if token != config.EVENTS_SHARED_TOKEN:
            return jsonify({"error": "forbidden"}), 403
    else:
        client_ip = resolve_client_ip(request, config.REAL_IP_TRUSTED_PROXIES)
        ip_info = describe_ip(client_ip)
        if ip_info.get("scope") not in {"loopback", "lan"}:
            return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    task_id = payload.get("task_id")
    if not task_id:
        return jsonify({"error": "task_id required"}), 400
    socketio = current_app.extensions.get("socketio")
    if socketio is not None:
        socketio.emit("frame", payload, to=task_id)
    return jsonify({"ok": True})
