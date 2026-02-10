import logging
import os
import sys
from datetime import datetime
from pathlib import Path

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
LOG_LEVELS = set(logging._nameToLevel.keys())


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
    logs_dir = Path("/workspace/storage/logs/server")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{stamp}.log"
    os.environ["LOG_FILE"] = str(log_path)
    return log_path


def configure_logging(component="app"):
    level = _resolve_log_level()
    log_path = _resolve_log_file()
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_path, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        handlers=handlers,
    )
    logging.getLogger("LOGGING").info(
        "Logging initialized (level=%s, file=%s, component=%s)",
        logging.getLevelName(level),
        log_path,
        component,
    )
