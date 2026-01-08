import logging
import signal
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import config
import db
from backend.api import create_app

logger = logging.getLogger("MAIN")


def _start_worker():
    app_dir = Path(__file__).resolve().parents[1]
    worker_script = app_dir / "worker.py"
    log_path = Path("/workspace/worker.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "a", encoding="utf-8")
    return subprocess.Popen(
        [sys.executable, "-u", str(worker_script)],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=str(app_dir),
    )


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    )
    config.initialize_context()
    db.init_db()

    worker = _start_worker()
    logger.info("Worker started with PID %s", worker.pid)

    def shutdown_handler(*_args):
        logger.info("Shutting down services...")
        if worker.poll() is None:
            worker.terminate()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    app = create_app()
    app.run(host="0.0.0.0", port=8501, threaded=True)


if __name__ == "__main__":
    main()
