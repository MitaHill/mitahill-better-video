from .admin import bp as admin_bp
from .admin_sections import (
    admin_debug_bp,
    admin_logs_bp,
    admin_transcription_config_bp,
    admin_transcription_models_bp,
)
from .conversions import bp as conversions_bp
from .downloads import bp as downloads_bp
from .events import bp as events_bp
from .form_constraints import bp as form_constraints_bp
from .frontend import bp as frontend_bp
from .health import bp as health_bp
from .tasks import bp as tasks_bp
from .transcriptions import bp as transcriptions_bp


def register_routes(app):
    app.register_blueprint(health_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_transcription_config_bp)
    app.register_blueprint(admin_transcription_models_bp)
    app.register_blueprint(admin_debug_bp)
    app.register_blueprint(admin_logs_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(conversions_bp)
    app.register_blueprint(downloads_bp)
    app.register_blueprint(transcriptions_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(form_constraints_bp)
    app.register_blueprint(frontend_bp)
