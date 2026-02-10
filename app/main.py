import eventlet
eventlet.monkey_patch()

import logging
import signal
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.src.Config.logging_setup import configure_logging
from app.src.Services.worker_service import WorkerService
from flask_socketio import SocketIO, join_room
from app.src.Api.services.form_constraints import ensure_form_constraints_config

logger = logging.getLogger("MAIN")


def _build_worker_service():
    return WorkerService()


def main():
    configure_logging(component="server")
    from app.src.Config import settings as config
    from app.src.Database import core as db
    from app.src.Database import admin as db_admin
    from app.src.Api.http import create_app
    init_info = config.initialize_context()
    db.init_db()
    db_admin.ensure_admin_password(config.ADMIN_INITIAL_PASSWORD)
    db_admin.ensure_real_ip_trusted_proxies(config.REAL_IP_TRUSTED_PROXIES_RAW)
    ensure_form_constraints_config()
    logger.info("Init recommendations: %s", init_info)

    worker_service = _build_worker_service()
    worker_service.start()
    logger.info("Worker status: %s", worker_service.status())

    def shutdown_handler(*_args):
        logger.info("Shutting down services...")
        worker_service.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    app = create_app(worker_service)
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")
    app.extensions["socketio"] = socketio

    @socketio.on("join")
    def on_join(data):
        task_id = (data or {}).get("task_id")
        if task_id:
            join_room(task_id)

    socketio.run(app, host="0.0.0.0", port=8501)


if __name__ == "__main__":
    main()
