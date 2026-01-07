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
    # Note: For simplicity in this update, we might just create a new table or rely on the user manually clearing old DB if schema conflicts.
    # In production, we'd use migration tools like Alembic.
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
