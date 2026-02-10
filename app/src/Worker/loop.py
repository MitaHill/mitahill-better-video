import time
import shutil
import json
import gc
import logging
from pathlib import Path
import sqlite3
import torch

from app.src.Database import core as db
from app.src.Config import settings as config
from app.src.Worker.pipelines.dispatch import process_task

logger = logging.getLogger("WORKER")

def recover_tasks():
    """Check for interrupted tasks on startup and reset or delete them."""
    logger.info("Scanning for interrupted tasks during startup...")
    tasks = db.get_unfinished_tasks()
    output_root = Path("/workspace/storage/output")
    upload_root = Path("/workspace/storage/upload")
    
    for task in tasks:
        task_id = task['task_id']
        try:
            params = json.loads(task['task_params'])
            video_info = json.loads(task.get('video_info') or "{}")
            filename = params.get('filename')
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
                logger.info(f"Task Recovery: Task {task_id} has source file. Resetting to PENDING.")
                db.update_task_status(task_id, "PENDING", 0, "Recovered from system restart.")
            else:
                logger.warning(f"Task Recovery: Task {task_id} source missing at {input_path}. Deleting task.")
                db.delete_task(task_id)
        except Exception as e:
            logger.error(f"Failed to recover task {task_id}: {e}")
            db.delete_task(task_id)

def worker_loop():
    try:
        logger.info("--- Worker Process Initiated ---")
        config.initialize_context()
        db.init_db()
        recover_tasks()
        
        logger.info(f"Daemon Loop Started (TTL: {config.TASK_TTL_HOURS}h, Segments: {config.SEGMENT_TIME_SECONDS}s)")
        
        while True:
            try:
                db.cleanup_old_tasks(config.TASK_TTL_HOURS)
                db.mark_stuck_tasks(config.TASK_TIMEOUT_SECONDS)
            except Exception as e:
                logger.error(f"Background cleanup failed: {e}")

            # Atomic pick and mark
            task = db.get_next_task_atomic()

            if task:
                try:
                    process_task(task)
                except Exception as e:
                    logger.error(f"Fatal error during task {task['task_id']}: {e}")
                    db.update_task_status(task['task_id'], "FAILED", message=str(e))
                finally:
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
            else:
                time.sleep(2)
    except Exception as fatal_e:
        logger.critical(f"WORKER CRASHED: {fatal_e}", exc_info=True)
        time.sleep(5) # Slow down restart loop
        raise fatal_e

if __name__ == "__main__":
    worker_loop()
