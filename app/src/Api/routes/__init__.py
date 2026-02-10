from .admin import bp as admin_bp
from .conversions import bp as conversions_bp
from .events import bp as events_bp
from .frontend import bp as frontend_bp
from .health import bp as health_bp
from .tasks import bp as tasks_bp


def register_routes(app):
    app.register_blueprint(health_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(conversions_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(frontend_bp)
