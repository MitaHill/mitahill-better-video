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


@bp.get("/favicon.ico")
def favicon():
    ico_path = FRONTEND_DIST_DIR / "favicon.ico"
    if ico_path.is_file():
        return send_file(ico_path)
    png_path = FRONTEND_DIST_DIR / "favicon.png"
    if png_path.is_file():
        return send_file(png_path)
    return ("", 204)


@bp.get("/<path:_path>")
def spa_fallback(_path):
    static_candidate = FRONTEND_DIST_DIR / _path
    if static_candidate.is_file():
        return send_from_directory(FRONTEND_DIST_DIR, _path)
    return _serve_frontend()


def _serve_frontend():
    index_path = FRONTEND_DIST_DIR / "index.html"
    if not index_path.exists():
        return "Frontend build not found.", 503
    return send_file(index_path)
