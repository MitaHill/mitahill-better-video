import sqlite3
import json
import datetime
import logging
import os
from pathlib import Path


logger = logging.getLogger("DB")
DB_PATH = Path(os.getenv("DB_PATH", "/workspace/storage/data/tasks.db"))

def _apply_pragmas(conn):
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=30000;")

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    _apply_pragmas(conn)
    return conn

def init_db():
    logger.debug(f"Initializing database at {DB_PATH}")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS task_queue
                     (task_id TEXT PRIMARY KEY,
                      created_at DATETIME,
                      updated_at DATETIME,
                      client_ip TEXT,
                      task_category TEXT,
                      status TEXT,
                      task_params TEXT,
                      video_info TEXT,
                      progress INTEGER,
                      message TEXT,
                      result_path TEXT)''')
        _ensure_columns(conn)
        c.execute("""CREATE TABLE IF NOT EXISTS task_progress
                     (task_id TEXT PRIMARY KEY,
                      total_frames INTEGER,
                      total_segments INTEGER,
                      updated_at DATETIME)""")
        c.execute("""CREATE TABLE IF NOT EXISTS segment_progress
                     (task_id TEXT,
                      segment_key TEXT,
                      segment_index INTEGER,
                      start_frame INTEGER,
                      end_frame INTEGER,
                      total_frames INTEGER,
                      last_done_frame INTEGER,
                      updated_at DATETIME,
                      PRIMARY KEY (task_id, segment_key))""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_task_status ON task_queue(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_task_created ON task_queue(created_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_task_updated ON task_queue(updated_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_task_progress_updated ON task_progress(updated_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_segment_progress_task ON segment_progress(task_id)")
        c.execute(
            """CREATE TABLE IF NOT EXISTS app_settings
               (key TEXT PRIMARY KEY,
                value TEXT,
                updated_at DATETIME)"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS admin_sessions
               (session_id TEXT PRIMARY KEY,
                token_hash TEXT UNIQUE,
                created_at DATETIME,
                expires_at DATETIME,
                client_ip TEXT,
                user_agent TEXT)"""
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_admin_sessions_exp ON admin_sessions(expires_at)")
        c.execute(
            """CREATE TABLE IF NOT EXISTS app_logs
               (id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at DATETIME,
                level TEXT,
                logger_name TEXT,
                message TEXT,
                extra_json TEXT)"""
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_app_logs_created ON app_logs(created_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_app_logs_level ON app_logs(level)")
        c.execute(
            """CREATE TABLE IF NOT EXISTS model_download_jobs
               (job_id TEXT PRIMARY KEY,
                model_id TEXT,
                backend TEXT,
                status TEXT,
                progress REAL,
                downloaded_bytes INTEGER,
                total_bytes INTEGER,
                message TEXT,
                result_json TEXT,
                error TEXT,
                request_json TEXT,
                created_at DATETIME,
                updated_at DATETIME)"""
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_model_download_jobs_status ON model_download_jobs(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_model_download_jobs_created ON model_download_jobs(created_at)")
        c.execute(
            """CREATE TABLE IF NOT EXISTS task_control
               (task_id TEXT PRIMARY KEY,
                cancel_requested INTEGER DEFAULT 0,
                cancel_reason TEXT,
                updated_at DATETIME)"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS gpu_usage_samples
               (id INTEGER PRIMARY KEY AUTOINCREMENT,
                collected_at DATETIME,
                gpu_index INTEGER,
                gpu_name TEXT,
                utilization_gpu REAL,
                utilization_mem REAL,
                memory_used_mb REAL,
                memory_total_mb REAL,
                temperature_c REAL)"""
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_gpu_usage_samples_collected ON gpu_usage_samples(collected_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_gpu_usage_samples_gpu ON gpu_usage_samples(gpu_index)")
        conn.commit()
        conn.close()
        logger.debug("Database initialized successfully.")
    except Exception as e:
        logger.critical(f"[FAILED] Failed to initialize database: {e}")
        import sys
        sys.exit(1)

def create_task(task_id, client_ip, task_params, video_info, task_category=None):
    logger.info(f"Creating new task: {task_id} from {client_ip}")
    category = task_category or task_params.get("task_category") or "enhance"
    conn = get_connection()
    c = conn.cursor()
    c.execute("""INSERT INTO task_queue 
                 (task_id, created_at, updated_at, client_ip, task_category, status, task_params, video_info, progress, message, result_path) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (task_id, datetime.datetime.now(), datetime.datetime.now(), client_ip, category, "PENDING", 
               json.dumps(task_params), json.dumps(video_info), 0, "Waiting to start", None))
    c.execute("DELETE FROM task_control WHERE task_id = ?", (task_id,))
    conn.commit()
    conn.close()
    logger.debug(f"Task {task_id} inserted into queue.")

def get_task(task_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM task_queue WHERE task_id = ?", (task_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def update_task_status(task_id, status, progress=None, message=None):
    logger.debug(f"Updating Task {task_id}: {status} ({progress}%) - {message}")
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT cancel_requested, COALESCE(cancel_reason, '') FROM task_control WHERE task_id = ?",
        (task_id,),
    )
    ctrl = c.fetchone()
    cancel_requested = bool(ctrl[0]) if ctrl else False
    cancel_reason = str(ctrl[1]).strip() if ctrl else ""
    normalized_status = str(status or "").strip().upper()
    if cancel_requested:
        if normalized_status != "FAILED":
            status = "FAILED"
        message = cancel_reason or "已取消（管理员操作）"
        progress = None
    updates = ["status = ?", "updated_at = ?"]
    params = [status, datetime.datetime.now()]
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

def update_task_result(task_id, result_path):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT cancel_requested FROM task_control WHERE task_id = ?", (task_id,))
    row = c.fetchone()
    if row and int(row[0] or 0) == 1:
        conn.close()
        return
    c.execute(
        "UPDATE task_queue SET result_path = ?, updated_at = ? WHERE task_id = ?",
        (str(result_path), datetime.datetime.now(), task_id),
    )
    conn.commit()
    conn.close()

def delete_task(task_id):
    logger.warning(f"Deleting task and all associated files: {task_id}")
    task = get_task(task_id)
    result_filename = None
    if task and task.get('task_params'):
        try:
            params = json.loads(task['task_params'])
            result_filename = f"sr_{params.get('filename')}"
        except: pass

    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM task_queue WHERE task_id = ?", (task_id,))
    c.execute("DELETE FROM task_progress WHERE task_id = ?", (task_id,))
    c.execute("DELETE FROM segment_progress WHERE task_id = ?", (task_id,))
    c.execute("DELETE FROM task_control WHERE task_id = ?", (task_id,))
    conn.commit()
    conn.close()
    
    output_root = Path("/workspace/storage/output")
    upload_root = Path("/workspace/storage/upload")
    run_dir = output_root / f"run_{task_id}"
    import shutil
    if run_dir.exists():
        logger.debug(f"Removing run dir: {run_dir}")
        shutil.rmtree(run_dir, ignore_errors=True)
    upload_dir = upload_root / f"run_{task_id}"
    if upload_dir.exists():
        logger.debug(f"Removing upload dir: {upload_dir}")
        shutil.rmtree(upload_dir, ignore_errors=True)
            
    if result_filename:
        stem = Path(result_filename).stem
        for p in output_root.glob(f"{stem}*"):
            if p.is_file():
                logger.debug(f"Removing result file: {p}")
                try: p.unlink()
                except: pass

def get_next_task_atomic():
    logger.debug("Checking for next pending task...")
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        c.execute("BEGIN IMMEDIATE")
        c.execute("SELECT * FROM task_queue WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT 1")
        row = c.fetchone()
        if row:
            task_id = row['task_id']
            logger.info(f"Task {task_id} picked by worker.")
            c.execute(
                "UPDATE task_queue SET status = 'PROCESSING', message = 'Initializing...', updated_at = ? WHERE task_id = ?",
                (datetime.datetime.now(), task_id),
            )
            conn.commit()
            return dict(row)
        else:
            conn.rollback()
            return None
    except Exception as e:
        conn.rollback()
        logger.error(f"Atomic task pick failed: {e}")
        return None
    finally:
        conn.close()

def cleanup_old_tasks(hours_ttl):
    now = datetime.datetime.now()
    finished_cutoff = now - datetime.timedelta(hours=hours_ttl)
    stuck_cutoff = now - datetime.timedelta(hours=48)
    
    conn = get_connection()
    c = conn.cursor()
    c.execute("""SELECT task_id FROM task_queue 
                 WHERE (status IN ('COMPLETED', 'FAILED') AND COALESCE(updated_at, created_at) < ?)
                 OR (COALESCE(updated_at, created_at) < ?)""", (finished_cutoff, stuck_cutoff))
    rows = c.fetchall()
    conn.close()
    
    if rows:
        logger.info(f"Starting cleanup of {len(rows)} tasks...")
        for row in rows:
            delete_task(row[0])

def mark_stuck_tasks(timeout_seconds):
    cutoff = datetime.datetime.now() - datetime.timedelta(seconds=timeout_seconds)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT task_id FROM task_queue WHERE status = 'PROCESSING' AND COALESCE(updated_at, created_at) < ?",
        (cutoff,),
    )
    rows = c.fetchall()
    conn.close()
    if rows:
        logger.warning(f"Marking {len(rows)} stuck tasks as FAILED...")
        for row in rows:
            update_task_status(row[0], "FAILED", message="Task timed out")

def upsert_task_progress(task_id, total_frames, total_segments):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO task_progress (task_id, total_frames, total_segments, updated_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(task_id) DO UPDATE SET
             total_frames = excluded.total_frames,
             total_segments = excluded.total_segments,
             updated_at = excluded.updated_at""",
        (task_id, total_frames, total_segments, datetime.datetime.now()),
    )
    conn.commit()
    conn.close()

def get_task_progress(task_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM task_progress WHERE task_id = ?", (task_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def upsert_segment(task_id, segment_key, segment_index, start_frame, end_frame, total_frames):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO segment_progress
           (task_id, segment_key, segment_index, start_frame, end_frame, total_frames, last_done_frame, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(task_id, segment_key) DO UPDATE SET
             segment_index = excluded.segment_index,
             start_frame = excluded.start_frame,
             end_frame = excluded.end_frame,
             total_frames = excluded.total_frames""",
        (task_id, segment_key, segment_index, start_frame, end_frame, total_frames, 0, datetime.datetime.now()),
    )
    conn.commit()
    conn.close()

def update_segment_progress(task_id, segment_key, last_done_frame):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """UPDATE segment_progress
           SET last_done_frame = ?, updated_at = ?
           WHERE task_id = ? AND segment_key = ?""",
        (last_done_frame, datetime.datetime.now(), task_id, segment_key),
    )
    conn.commit()
    conn.close()

def get_segment_progress(task_id, segment_key):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT * FROM segment_progress WHERE task_id = ? AND segment_key = ?",
        (task_id, segment_key),
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_latest_segment_progress(task_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT * FROM segment_progress
           WHERE task_id = ?
           ORDER BY (start_frame + COALESCE(last_done_frame, 0)) DESC, updated_at DESC
           LIMIT 1""",
        (task_id,),
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def _ensure_columns(conn):
    c = conn.cursor()
    c.execute("PRAGMA table_info(task_queue)")
    columns = {row[1] for row in c.fetchall()}
    if "updated_at" not in columns:
        c.execute("ALTER TABLE task_queue ADD COLUMN updated_at DATETIME")
    if "task_category" not in columns:
        c.execute("ALTER TABLE task_queue ADD COLUMN task_category TEXT DEFAULT 'enhance'")
    if "result_path" not in columns:
        c.execute("ALTER TABLE task_queue ADD COLUMN result_path TEXT")
    conn.commit()

def get_unfinished_tasks():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM task_queue WHERE status NOT IN ('COMPLETED', 'FAILED')")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def request_task_cancel(task_id, reason="已取消（管理员操作）"):
    safe_reason = str(reason or "已取消（管理员操作）").strip() or "已取消（管理员操作）"
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO task_control (task_id, cancel_requested, cancel_reason, updated_at)
           VALUES (?, 1, ?, ?)
           ON CONFLICT(task_id) DO UPDATE SET
             cancel_requested = excluded.cancel_requested,
             cancel_reason = excluded.cancel_reason,
             updated_at = excluded.updated_at""",
        (task_id, safe_reason, datetime.datetime.now()),
    )
    conn.commit()
    conn.close()


def clear_task_cancel_request(task_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM task_control WHERE task_id = ?", (task_id,))
    conn.commit()
    conn.close()


def is_task_cancel_requested(task_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT cancel_requested FROM task_control WHERE task_id = ?", (task_id,))
    row = c.fetchone()
    conn.close()
    return bool(row and int(row[0] or 0) == 1)
