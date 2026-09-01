import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from app.src.Database import app_logs as db_logs

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
LOG_LEVELS = set(logging._nameToLevel.keys())
LOGS_DIR = Path("/workspace/storage/logs/server")


def _resolve_log_level():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    if level not in LOG_LEVELS:
        raise ValueError(f"Invalid LOG_LEVEL: {level}")
    return logging._nameToLevel[level]


def _resolve_log_file():
    existing = os.getenv("LOG_FILE")
    if existing:
        return Path(existing)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"{stamp}.log"
    os.environ["LOG_FILE"] = str(log_path)
    return log_path


def _purge_expired_log_files():
    if not LOGS_DIR.exists():
        return
    cutoff = datetime.now().timestamp() - app_logs.LOG_RETENTION_DAYS * 24 * 60 * 60
    for log_path in LOGS_DIR.glob("*.log"):
        try:
            if log_path.stat().st_mtime < cutoff:
                log_path.unlink()
        except OSError:
            pass


class DatabaseLogHandler(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.INFO)

    def emit(self, record: logging.LogRecord):
        # Prevent recursive failures from bubbling back into logging.
        try:
            message = self.format(record)
            db_logs.insert_log(
                level=record.levelname,
                logger_name=record.name,
                message=message,
                extra={
                    "pathname": record.pathname,
                    "lineno": record.lineno,
                    "funcName": record.funcName,
                },
            )
        except Exception:
            pass


def configure_logging(component="app"):
    level = _resolve_log_level()
    _purge_expired_log_files()
    log_path = _resolve_log_file()
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_path, encoding="utf-8"),
        DatabaseLogHandler(),
    ]
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        handlers=handlers,
        force=True,
    )
    logging.captureWarnings(True)
    logging.getLogger("LOGGING").info(
        "Logging initialized (level=%s, file=%s, component=%s)",
        logging.getLevelName(level),
        log_path,
        component,
    )
