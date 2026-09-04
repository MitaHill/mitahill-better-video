from flask import Flask

from .routes import register_routes


def create_app(worker_service=None):
    app = Flask(__name__)
    app.extensions["worker_service"] = worker_service

    register_routes(app)
    return app
