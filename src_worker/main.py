import time
import shutil
import json
import gc
from pathlib import Path
import sqlite3
import torch

import db
import config
from .processor import process_single_task

def recover_tasks():
    """Check for interrupted tasks on startup and reset or delete them."""
    print("Checking for interrupted tasks...")
    tasks = db.get_unfinished_tasks()
    output_root = Path("/workspace/output")
    
    for task in tasks:
        task_id = task['task_id']
        try:
            params = json.loads(task['task_params'])
            filename = params.get('filename')
            run_dir = output_root / f"run_{task_id}"
            input_path = run_dir / filename
            
            if input_path.exists():
                print(f"Recovering task {task_id}: Source exists, resetting to PENDING.")
                db.update_task_status(task_id, "PENDING", 0, "Recovered. Waiting to restart...")
            else:
                print(f"Cleaning task {task_id}: Source missing, deleting.")
                db.delete_task(task_id)
                if run_dir.exists():
                    shutil.rmtree(run_dir, ignore_errors=True)
        except Exception as e:
            print(f"Error recovering task {task_id}: {e}")
            db.delete_task(task_id)

def worker_loop():
    recover_tasks()
    print("Worker daemon started. Waiting for tasks...")
    while True:
        try:
            db.cleanup_old_tasks(config.TASK_TTL_HOURS)
        except Exception as e:
            print(f"Cleanup error: {e}")

        # Atomic pick and mark
        task = db.get_next_task_atomic()

        if task:
            process_single_task(task)
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        else:
            time.sleep(2)

if __name__ == "__main__":
    worker_loop()
