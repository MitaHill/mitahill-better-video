import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.src.Config.logging_setup import configure_logging
from app.src.Database import core as db
from app.src.Worker.pipelines.dispatch import process_task

logger = logging.getLogger("TASK_ENTRYPOINT")


def main(task_id: str):
    configure_logging(component=f"task-{task_id}")
    task = db.get_task(task_id)
    if not task:
        logger.warning("Task %s no longer exists, skip task process", task_id)
        raise RuntimeError(f"Task not found: {task_id}")
    if str(task.get("status") or "").upper() != "PROCESSING":
        logger.info("Task %s status is %s, skip task process", task_id, task.get("status"))
        return
    process_task(task)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: task_entrypoint.py <task_id>")
    main(sys.argv[1])
