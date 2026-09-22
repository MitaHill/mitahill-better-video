import sqlite3
import json
import datetime
import logging
import os
from pathlib import Path


logger = logging.getLogger("DB")
DB_PATH = Path(os.getenv("DB_PATH", "/workspace/storage/data/tasks.db"))

DEFAULT_BUSY_TIMEOUT_MS = 30000
# 日志、GPU 采样这类“可丢”的写入用短超时：主进程跑在 eventlet 上，
# sqlite 的等锁是 C 层阻塞，等满 30s 会把整个事件循环连同 Web 服务一起冻住。
BEST_EFFORT_BUSY_TIMEOUT_MS = 2000

def _apply_pragmas(conn, busy_timeout_ms=DEFAULT_BUSY_TIMEOUT_MS):
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)};")

def get_connection(busy_timeout_ms=DEFAULT_BUSY_TIMEOUT_MS):
    timeout_ms = max(int(busy_timeout_ms), 0)
    conn = sqlite3.connect(DB_PATH, timeout=timeout_ms / 1000, check_same_thread=False)
    _apply_pragmas(conn, timeout_ms)
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
        c.execute(
            """CREATE TABLE IF NOT EXISTS task_batches
               (batch_id TEXT PRIMARY KEY,
                batch_category TEXT,
                created_at DATETIME,
                updated_at DATETIME)"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS task_batch_items
               (batch_id TEXT,
                task_id TEXT,
                task_category TEXT,
                item_label TEXT,
                created_at DATETIME,
                PRIMARY KEY (batch_id, task_id))"""
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_task_batch_items_batch ON task_batch_items(batch_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_task_batch_items_task ON task_batch_items(task_id)")
        conn.commit()
        conn.close()
        from . import app_logs
        app_logs.purge_expired_logs()
        logger.debug("Database initialized successfully.")
    except Exception as e:
        logger.critical(f"[FAILED] Failed to initialize database: {e}")
        import sys
        sys.exit(1)

def create_task(
    task_id,
    client_ip,
    task_params,
    video_info,
    task_category=None,
    status="PENDING",
    chain_step=None,
    chain_next_task_id=None,
):
    logger.info(f"Creating new task: {task_id} from {client_ip}")
    category = task_category or task_params.get("task_category") or "enhance"
    initial_status = str(status or "PENDING").strip().upper()
    initial_message = "Waiting for previous step" if initial_status == "WAITING" else "Waiting to start"
    conn = get_connection()
    c = conn.cursor()
    c.execute("""INSERT INTO task_queue 
                 (task_id, created_at, updated_at, client_ip, task_category, status, task_params, video_info, progress, message, result_path, chain_step, chain_next_task_id) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (task_id, datetime.datetime.now(), datetime.datetime.now(), client_ip, category, initial_status, 
               json.dumps(task_params), json.dumps(video_info), 0, initial_message, None, chain_step, chain_next_task_id))
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


def get_batch(batch_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM task_batches WHERE batch_id = ?", (batch_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def _batch_id_available(batch_id):
    if get_task(batch_id):
        return False
    if get_batch(batch_id):
        return False
    return True


def new_batch_id():
    # 9500-9999 留给批次任务，普通任务只使用前面的号码段
    for index in range(9_500, 10_000):
        batch_id = f"{index:04d}"
        if _batch_id_available(batch_id):
            return batch_id
    raise RuntimeError("failed to allocate a unique 4-digit batch id")


def create_batch(batch_category):
    batch_id = new_batch_id()
    now = datetime.datetime.now()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO task_batches (batch_id, batch_category, created_at, updated_at)
           VALUES (?, ?, ?, ?)""",
        (batch_id, batch_category, now, now),
    )
    conn.commit()
    conn.close()
    return batch_id


def add_batch_item(batch_id, task_id, task_category, item_label=""):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.datetime.now()
    c.execute(
        """INSERT OR REPLACE INTO task_batch_items
           (batch_id, task_id, task_category, item_label, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (batch_id, task_id, task_category, item_label, now),
    )
    c.execute("UPDATE task_batches SET updated_at = ? WHERE batch_id = ?", (now, batch_id))
    conn.commit()
    conn.close()


def list_batch_items(batch_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT bi.batch_id, bi.task_id, bi.task_category, bi.item_label, bi.created_at,
                  tq.status, tq.progress, tq.message, tq.result_path, tq.updated_at
           FROM task_batch_items bi
           LEFT JOIN task_queue tq ON tq.task_id = bi.task_id
           WHERE bi.batch_id = ?
           ORDER BY COALESCE(tq.chain_step, 999999) ASC, bi.created_at ASC, bi.task_id ASC""",
        (batch_id,),
    )
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_task_batch_id(task_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT batch_id FROM task_batch_items WHERE task_id = ? LIMIT 1", (task_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def delete_batch(batch_id):
    conn = get_connection()
    c = conn.cursor()
    # 只删除批次关系，子任务和文件由上层批量删除流程处理
    c.execute("DELETE FROM task_batch_items WHERE batch_id = ?", (batch_id,))
    c.execute("DELETE FROM task_batches WHERE batch_id = ?", (batch_id,))
    conn.commit()
    conn.close()

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


def update_task_params(task_id, task_params):
    if task_params is None:
        return
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE task_queue SET task_params = ?, updated_at = ? WHERE task_id = ?",
        (json.dumps(task_params, ensure_ascii=False), datetime.datetime.now(), task_id),
    )
    conn.commit()
    conn.close()


def update_task_video_info(task_id, video_info):
    if video_info is None:
        return
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE task_queue SET video_info = ?, updated_at = ? WHERE task_id = ?",
        (json.dumps(video_info, ensure_ascii=False), datetime.datetime.now(), task_id),
    )
    conn.commit()
    conn.close()

def delete_task(task_id):
    logger.info(f"Deleting task and all associated files: {task_id}")
    task = get_task(task_id)
    result_paths = []
    if task and task.get("result_path"):
        result_paths.append(Path(task["result_path"]))
    if task and task.get('task_params'):
        try:
            params = json.loads(task['task_params'])
            filename = params.get("filename")
            if filename:
                output_root = Path("/workspace/storage/output")
                result_paths.extend(output_root.glob(f"sr_{Path(filename).stem}.*"))
        except: pass

    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM task_queue WHERE task_id = ?", (task_id,))
    c.execute("DELETE FROM task_progress WHERE task_id = ?", (task_id,))
    c.execute("DELETE FROM segment_progress WHERE task_id = ?", (task_id,))
    c.execute("DELETE FROM task_control WHERE task_id = ?", (task_id,))
    c.execute("DELETE FROM task_batch_items WHERE task_id = ?", (task_id,))
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
            
    for path in set(result_paths):
        if path.is_file():
            logger.debug(f"Removing result file: {path}")
            try: path.unlink()
            except: pass


def delete_tasks(task_ids):
    safe_ids = [str(task_id).strip() for task_id in task_ids if str(task_id).strip()]
    if not safe_ids:
        return

    logger.warning(f"Deleting {len(safe_ids)} tasks and associated files")
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    tasks = []
    for start in range(0, len(safe_ids), 500):
        chunk = safe_ids[start:start + 500]
        placeholders = ",".join("?" for _ in chunk)
        c.execute(f"SELECT * FROM task_queue WHERE task_id IN ({placeholders})", chunk)
        tasks.extend(dict(row) for row in c.fetchall())
        for table in ("task_queue", "task_progress", "segment_progress", "task_control", "task_batch_items"):
            c.execute(f"DELETE FROM {table} WHERE task_id IN ({placeholders})", chunk)
    conn.commit()
    conn.close()

    output_root = Path("/workspace/storage/output")
    upload_root = Path("/workspace/storage/upload")
    import shutil
    result_paths = []
    for task in tasks:
        task_id = task.get("task_id")
        if task.get("result_path"):
            result_paths.append(Path(task["result_path"]))
        if task.get("task_params"):
            try:
                params = json.loads(task["task_params"])
                filename = params.get("filename")
                if filename:
                    result_paths.extend(output_root.glob(f"sr_{Path(filename).stem}.*"))
            except Exception:
                pass
        for root in (output_root, upload_root):
            run_dir = root / f"run_{task_id}"
            if run_dir.exists():
                shutil.rmtree(run_dir, ignore_errors=True)
    for path in set(result_paths):
        if path.is_file():
            try:
                path.unlink()
            except Exception:
                pass

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
            c.execute(
                "UPDATE task_queue SET status = 'PROCESSING', message = 'Initializing...', updated_at = ? WHERE task_id = ?",
                (datetime.datetime.now(), task_id),
            )
            conn.commit()
            # 日志必须在 commit 之后写：DatabaseLogHandler 会另开一条连接写同一个库，
            # 放在 BEGIN IMMEDIATE 事务里就是跟自己的写锁互锁，要等满 busy_timeout 才继续。
            logger.info(f"Task {task_id} picked by worker.")
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
    # 任务链：chain_step 为空表示普通任务，链上的步骤按 chain_step 排序、按
    # chain_next_task_id 单向推进。
    if "chain_step" not in columns:
        c.execute("ALTER TABLE task_queue ADD COLUMN chain_step INTEGER")
    if "chain_next_task_id" not in columns:
        c.execute("ALTER TABLE task_queue ADD COLUMN chain_next_task_id TEXT")
    conn.commit()

def get_unfinished_tasks():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # WAITING 是链上还没轮到的步骤，输入文件本来就不存在，交给恢复流程只会被当成
    # 源文件丢失删掉。它不占队列，等上游完成时自然会被推进。
    c.execute("SELECT * FROM task_queue WHERE status NOT IN ('COMPLETED', 'FAILED', 'WAITING')")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def list_chain_tasks_to_advance():
    """已结束但下游可能还没推进的链步骤，供 Worker 启动时补一次推进。"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT * FROM task_queue
           WHERE chain_step IS NOT NULL
             AND chain_next_task_id IS NOT NULL
             AND status IN ('COMPLETED', 'FAILED')"""
    )
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def count_processing_tasks(exclude_task_id=None):
    conn = get_connection()
    c = conn.cursor()
    safe_exclude = str(exclude_task_id or "").strip()
    if safe_exclude:
        c.execute(
            "SELECT COUNT(1) FROM task_queue WHERE status = 'PROCESSING' AND task_id != ?",
            (safe_exclude,),
        )
    else:
        c.execute("SELECT COUNT(1) FROM task_queue WHERE status = 'PROCESSING'")
    row = c.fetchone()
    conn.close()
    return int((row or [0])[0] or 0)


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
