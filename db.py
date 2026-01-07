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
    """Delete task from DB and remove associated files."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM task_queue WHERE task_id = ?", (task_id,))
    conn.commit()
    conn.close()
    
    # Remove files
    output_root = Path("/workspace/output")
    run_dir = output_root / f"run_{task_id}"
    import shutil
    if run_dir.exists():
        try:
            shutil.rmtree(run_dir)
        except Exception as e:
            print(f"Failed to delete run dir {run_dir}: {e}")
            
    # Also clean up potential result files in output root if named systematically
    # (Current worker saves sr_xxx to output root, we might need to track output path in DB to clean perfectly)
    # For now, we only clean the run_dir which holds the bulk.

def cleanup_old_tasks(hours_ttl):
    """Remove tasks older than hours_ttl."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    cutoff = datetime.datetime.now() - datetime.timedelta(hours=hours_ttl)
    c.execute("SELECT task_id FROM task_queue WHERE created_at < ?", (cutoff,))
    rows = c.fetchall()
    conn.close()
    
    count = 0
    for row in rows:
        delete_task(row[0])
        count += 1
    
    if count > 0:
        print(f"Cleaned up {count} old tasks.")

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
