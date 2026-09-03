import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.src.Config import settings as config
from app.src.Database import admin as db_admin
from app.src.Database import core as db
from app.src.Notifications.events import send_event

logger = logging.getLogger("WORKER")
TASK_PROCESS_POLL_SECONDS = 1
_active_process = None


def recover_tasks():
    """Check for interrupted tasks on startup and reset or delete them."""
    logger.info("Scanning for interrupted tasks during startup...")
    tasks = db.get_unfinished_tasks()
    output_root = Path("/workspace/storage/output")
    upload_root = Path("/workspace/storage/upload")

    for task in tasks:
        task_id = task["task_id"]
        try:
            params = json.loads(task["task_params"])
            video_info = json.loads(task.get("video_info") or "{}")
            filename = params.get("filename")
            run_dir = output_root / f"run_{task_id}"
            upload_path = params.get("upload_path")
            if upload_path:
                input_path = Path(upload_path)
            else:
                input_path = Path(video_info.get("upload_path") or (run_dir / filename))
            if not input_path.exists():
                candidate = upload_root / f"run_{task_id}" / filename
                if candidate.exists():
                    input_path = candidate

            if input_path.exists():
                logger.info("Task Recovery: Task %s has source file. Resetting to PENDING.", task_id)
                db.update_task_status(task_id, "PENDING", 0, "Recovered from system restart.")
            else:
                logger.warning("Task Recovery: Task %s source missing at %s. Deleting task.", task_id, input_path)
                db.delete_task(task_id)
        except Exception as exc:
            logger.error("Failed to recover task %s: %s", task_id, exc)
            db.delete_task(task_id)


def _terminate_process(process, task_id: str, reason: str):
    if process is None or process.poll() is not None:
        return
    logger.warning("Stopping task process %s for task %s: %s", process.pid, task_id, reason)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    process.wait(timeout=5)


def _mark_process_exit(task_id: str, returncode: int):
    task = db.get_task(task_id) or {}
    if str(task.get("status") or "").upper() in {"COMPLETED", "FAILED"}:
        return

    message = f"Task process exited unexpectedly (code {returncode})."
    db.update_task_status(task_id, "FAILED", progress=task.get("progress") or 0, message=message)
    send_event(
        {
            "task_id": task_id,
            "task_category": task.get("task_category"),
            "status": "FAILED",
            "progress": task.get("progress") or 0,
            "message": message,
            "stage": "failed",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def _run_task_process(task_id: str):
    global _active_process

    task_script = Path(__file__).with_name("task_entrypoint.py")
    _active_process = subprocess.Popen(
        [sys.executable, "-u", str(task_script), task_id],
        cwd=str(task_script.parents[2]),
        env=os.environ.copy(),
        start_new_session=True,
    )
    logger.info("Task %s started in process %s.", task_id, _active_process.pid)

    try:
        while True:
            returncode = _active_process.poll()
            current = db.get_task(task_id) or {}
            status = str(current.get("status") or "").upper()

            if status in {"COMPLETED", "FAILED"}:
                _terminate_process(_active_process, task_id, f"task status is {status}")
                return
            if returncode is not None:
                _mark_process_exit(task_id, returncode)
                return
            time.sleep(TASK_PROCESS_POLL_SECONDS)
    finally:
        _terminate_process(_active_process, task_id, "Worker cleanup")
        _active_process = None


def _shutdown_handler(_signum, _frame):
    if _active_process is not None:
        _terminate_process(_active_process, "-", "Worker is stopping")
    raise SystemExit(0)


def worker_loop():
    logger.info("--- Worker Process Initiated ---")
    config.initialize_context()
    db.init_db()
    recover_tasks()
    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)
    logger.info(
        "Daemon Loop Started (TTL: %sh, Segments: %ss)",
        config.TASK_TTL_HOURS,
        config.SEGMENT_TIME_SECONDS,
    )

    while True:
        try:
            # Automatic TTL deletion is temporarily disabled.
            db.mark_stuck_tasks(config.TASK_TIMEOUT_SECONDS)
        except Exception as exc:
            logger.error("Background cleanup failed: %s", exc)

        if db_admin.get_worker_maintenance_mode(default=False):
            time.sleep(1)
            continue

        task = db.get_next_task_atomic()
        if task:
            _run_task_process(task["task_id"])
        else:
            time.sleep(2)


if __name__ == "__main__":
    worker_loop()
