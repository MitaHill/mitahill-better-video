from flask import Blueprint, send_file, send_from_directory

from ..constants import FRONTEND_DIST_DIR

bp = Blueprint("frontend", __name__)


@bp.get("/")
def index():
    return _serve_frontend()


@bp.get("/assets/<path:filename>")
def assets(filename):
    assets_dir = FRONTEND_DIST_DIR / "assets"
    return send_from_directory(assets_dir, filename)


@bp.get("/<path:_path>")
def spa_fallback(_path):
    return _serve_frontend()


def _serve_frontend():
    index_path = FRONTEND_DIST_DIR / "index.html"
    if not index_path.exists():
        return "Frontend build not found.", 503
    return send_file(index_path)
