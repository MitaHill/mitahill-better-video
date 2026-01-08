import logging
import signal
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import config
import db
from backend.api import create_app
from backend.worker_service import WorkerService

logger = logging.getLogger("MAIN")


def _build_worker_service():
    log_path = Path("/workspace/worker.log")
    return WorkerService(log_path)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    )
    init_info = config.initialize_context()
    db.init_db()
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
    app.run(host="0.0.0.0", port=8501, threaded=True)


if __name__ == "__main__":
    main()
