import sqlite3
import json
import datetime
from pathlib import Path

DB_PATH = Path("/workspace/output/tasks.db")

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Create table with new schema
    c.execute('''CREATE TABLE IF NOT EXISTS task_queue
                 (task_id TEXT PRIMARY KEY, 
                  created_at DATETIME,
                  client_ip TEXT, 
                  status TEXT, 
                  task_params TEXT,
                  video_info TEXT,
                  progress INTEGER,
                  message TEXT)''')
    conn.commit()
    conn.close()

def create_task(task_id, client_ip, task_params, video_info):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO task_queue 
                 (task_id, created_at, client_ip, status, task_params, video_info, progress, message) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
              (task_id, datetime.datetime.now(), client_ip, "PENDING", 
               json.dumps(task_params), json.dumps(video_info), 0, "Waiting to start"))
    conn.commit()
    conn.close()

def get_task(task_id):
    conn = sqlite3.connect(DB_PATH)
    # Return row as dict-like
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM task_queue WHERE task_id = ?", (task_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def update_task_status(task_id, status, progress=None, message=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    updates = ["status = ?"]
    params = [status]
    
    if progress is not None:
        updates.append("progress = ?")
        params.append(progress)
    
    if message is not None:
        updates.append("message = ?")
        params.append(message)
    
    params.append(task_id)
    
    sql = f"UPDATE task_queue SET {', '.join(updates)} WHERE task_id = ?"
    c.execute(sql, params)
    conn.commit()
    conn.close()

def delete_task(task_id):
    """Delete task from DB and remove associated files (run dir and result file)."""
    # 1. Get task info before deleting to find result file
    task = get_task(task_id)
    result_filename = None
    if task and task.get('task_params'):
        try:
            params = json.loads(task['task_params'])
            result_filename = f"sr_{params.get('filename')}"
        except:
            pass

    # 2. Delete from DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM task_queue WHERE task_id = ?", (task_id,))
    conn.commit()
    conn.close()
    
    # 3. Remove run directory
    output_root = Path("/workspace/output")
    run_dir = output_root / f"run_{task_id}"
    import shutil
    if run_dir.exists():
        try:
            shutil.rmtree(run_dir)
        except Exception as e:
            print(f"Failed to delete run dir {run_dir}: {e}")
            
    # 4. Remove final result file if exists
    if result_filename:
        # Check for original extension and .mp4 (since we often convert to mp4)
        stem = Path(result_filename).stem
        for p in output_root.glob(f"{stem}*"):
            if p.is_file():
                try:
                    p.unlink()
                except:
                    pass

def get_next_task_atomic():
    """Pick next pending task and mark it as PROCESSING atomically."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        # Atomic selection and update using a transaction
        c.execute("BEGIN IMMEDIATE")
        c.execute("SELECT * FROM task_queue WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT 1")
        row = c.fetchone()
        if row:
            task_id = row['task_id']
            c.execute("UPDATE task_queue SET status = 'PROCESSING', message = 'Initializing...' WHERE task_id = ?", (task_id,))
            conn.commit()
            return dict(row)
        else:
            conn.rollback()
            return None
    except Exception as e:
        conn.rollback()
        print(f"DB Error picking next task: {e}")
        return None
    finally:
        conn.close()

def cleanup_old_tasks(hours_ttl):
    """Remove finished tasks older than hours_ttl, or stuck tasks older than 48h."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    now = datetime.datetime.now()
    finished_cutoff = now - datetime.timedelta(hours=hours_ttl)
    stuck_cutoff = now - datetime.timedelta(hours=48)
    
    # Target finished tasks older than TTL OR any task older than 48 hours
    c.execute("""SELECT task_id FROM task_queue 
                 WHERE (status IN ('COMPLETED', 'FAILED') AND created_at < ?)
                 OR (created_at < ?)""", (finished_cutoff, stuck_cutoff))
    rows = c.fetchall()
    conn.close()
    
    count = 0
    for row in rows:
        delete_task(row[0])
        count += 1
    
    if count > 0:
        print(f"Cleaned up {count} tasks from history.")

def get_unfinished_tasks():
    """Get all tasks that are stuck in PROCESSING or PENDING (e.g. after restart)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # PENDING is normal, but if we just restarted, we might want to verify them too.
    # PROCESSING means it was interrupted.
    c.execute("SELECT * FROM task_queue WHERE status NOT IN ('COMPLETED', 'FAILED')")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]
