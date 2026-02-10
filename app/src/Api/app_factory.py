from flask import Flask
from werkzeug.exceptions import RequestEntityTooLarge

from app.src.Config import settings as config

from .routes import register_routes


def create_app(worker_service=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = (
        max(config.MAX_VIDEO_SIZE_MB, config.MAX_IMAGE_SIZE_MB) * 1024 * 1024
    )
    app.extensions["worker_service"] = worker_service

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(_err):
        limit_mb = max(config.MAX_VIDEO_SIZE_MB, config.MAX_IMAGE_SIZE_MB)
        return {"error": f"file exceeds limit ({limit_mb} MB)"}, 413

    register_routes(app)
    return app
