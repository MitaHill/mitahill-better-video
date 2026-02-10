from flask import Blueprint, jsonify, request

from app.src.Database import app_logs as db_logs

from ...services.admin_auth import get_admin_session

bp = Blueprint("api_admin_logs", __name__)


@bp.get("/api/admin/logs")
def admin_get_logs():
    _session, err = get_admin_session(request)
    if err:
        return jsonify({"error": err}), 401

    min_level = request.args.get("min_level", type=str) or "WARNING"
    limit = request.args.get("limit", type=int) or 200
    offset = request.args.get("offset", type=int) or 0
    logger_name = request.args.get("logger", type=str) or ""
    keyword = request.args.get("q", type=str) or ""
    rows = db_logs.list_logs(
        min_level=min_level,
        limit=limit,
        offset=offset,
        logger_name=logger_name,
        keyword=keyword,
    )
    return jsonify({"logs": rows})
