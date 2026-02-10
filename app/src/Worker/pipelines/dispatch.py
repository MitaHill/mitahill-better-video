import json
import logging

from app.src.Database import core as db

from .conversion import process_conversion_task
from .enhancement import process_enhancement_task
from .transcription import process_transcription_task

logger = logging.getLogger("PROCESSOR")


def process_task(task):
    task_id = task["task_id"]
    logger.info("=== Starting Task Processor: %s ===", task_id)

    try:
        db.update_task_status(task_id, "PROCESSING", 0, "Initializing...")
        params = json.loads(task["task_params"])
        category = (task.get("task_category") or params.get("task_category") or "enhance").lower()
        if category == "convert":
            logger.info("Task %s routed to conversion pipeline.", task_id)
            process_conversion_task(task)
            return
        if category == "transcribe":
            logger.info("Task %s routed to transcription pipeline.", task_id)
            process_transcription_task(task)
            return

        process_enhancement_task(task)
    except Exception as exc:
        logger.error("Task failed: %s", exc, exc_info=True)
        db.update_task_status(task_id, "FAILED", message=str(exc))
