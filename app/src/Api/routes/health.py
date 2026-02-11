from flask import Blueprint, current_app, jsonify

from app.src.Config import settings as config
from app.src.Database import core as db

bp = Blueprint("api_health", __name__)


@bp.get("/api/health")
def health():
    db_status = "ok"
    try:
        conn = db.get_connection()
        conn.execute("SELECT 1")
        conn.close()
    except Exception:
        db_status = "error"
    worker_status = "unknown"
    worker_service = current_app.extensions.get("worker_service")
    if worker_service is not None:
        worker_status = worker_service.status()
    return jsonify({"status": "ok", "db": db_status, "worker": worker_status})


@bp.get("/api/config/recommendations")
def config_recommendations():
    return jsonify(config.get_init_info())
