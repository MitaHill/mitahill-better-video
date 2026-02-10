from .debug import bp as admin_debug_bp
from .logs import bp as admin_logs_bp
from .transcription_config import bp as admin_transcription_config_bp
from .transcription_models import bp as admin_transcription_models_bp

__all__ = [
    "admin_debug_bp",
    "admin_logs_bp",
    "admin_transcription_config_bp",
    "admin_transcription_models_bp",
]
