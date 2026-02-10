from flask import Blueprint, jsonify, request

from app.src.Config import settings as config
from app.src.Database import admin as db_admin

from ..services.admin_auth import (
    change_password,
    get_admin_session,
    login,
    parse_admin_token,
)
from ..services.admin_stats import build_overview
from ..services.real_ip import (
    get_trusted_proxies_raw,
    resolve_request_client_ip,
    update_trusted_proxies_raw,
)

bp = Blueprint("api_admin", __name__)


@bp.post("/api/admin/login")
def admin_login():
    payload = request.get_json(silent=True) or {}
    password = payload.get("password", "")
    if not password:
        return jsonify({"error": "password is required"}), 400
    client_ip = resolve_request_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    session, err = login(password, client_ip, user_agent)
    if err:
        return jsonify({"error": err}), 401
    return jsonify(
        {
            "token": session["token"],
            "session_id": session["session_id"],
            "expires_at": session["expires_at"],
        }
    )


@bp.get("/api/admin/session")
def admin_session():
    session, err = get_admin_session(request)
    if err:
        return jsonify({"error": err}), 401
    return jsonify(
        {
            "ok": True,
            "session_id": session.get("session_id"),
            "expires_at": session.get("expires_at"),
            "client_ip": session.get("client_ip"),
        }
    )


@bp.post("/api/admin/logout")
def admin_logout():
    token = parse_admin_token(request)
    if not token:
        return jsonify({"error": "missing admin token"}), 401
    db_admin.delete_session_by_token(token)
    return jsonify({"ok": True})


@bp.post("/api/admin/password")
def admin_change_password():
    _session, err = get_admin_session(request)
    if err:
        return jsonify({"error": err}), 401
    payload = request.get_json(silent=True) or {}
    old_password = payload.get("old_password", "")
    new_password = payload.get("new_password", "")
    if not old_password or not new_password:
        return jsonify({"error": "old_password and new_password are required"}), 400
    err = change_password(old_password, new_password)
    if err:
        return jsonify({"error": err}), 400
    return jsonify({"ok": True, "message": "password updated, please login again"})


@bp.get("/api/admin/overview")
def admin_overview():
    _session, err = get_admin_session(request)
    if err:
        return jsonify({"error": err}), 401
    limit = request.args.get("limit", type=int) or 200
    offset = request.args.get("offset", type=int) or 0
    status = request.args.get("status", type=str) or ""
    payload = build_overview(limit=limit, offset=offset, status=status)
    payload["real_ip_config"] = {
        "trusted_proxies": get_trusted_proxies_raw(),
        "resolved_client_ip": resolve_request_client_ip(request),
    }
    return jsonify(payload)


@bp.get("/api/admin/config/real-ip")
def admin_get_real_ip_config():
    _session, err = get_admin_session(request)
    if err:
        return jsonify({"error": err}), 401
    return jsonify(
        {
            "trusted_proxies": get_trusted_proxies_raw(),
            "resolved_client_ip": resolve_request_client_ip(request),
            "from_env_default": config.REAL_IP_TRUSTED_PROXIES_RAW,
        }
    )


@bp.put("/api/admin/config/real-ip")
def admin_update_real_ip_config():
    _session, err = get_admin_session(request)
    if err:
        return jsonify({"error": err}), 401
    payload = request.get_json(silent=True) or {}
    trusted_proxies = payload.get("trusted_proxies", "")
    try:
        saved = update_trusted_proxies_raw(trusted_proxies)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "trusted_proxies": saved})
