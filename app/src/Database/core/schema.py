import sys

from .common import DB_PATH, get_connection, logger


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


def init_db():
    logger.debug("Initializing database at %s", DB_PATH)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS task_queue
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
                      result_path TEXT)"""
        )
        _ensure_columns(conn)
        c.execute(
            """CREATE TABLE IF NOT EXISTS task_progress
                     (task_id TEXT PRIMARY KEY,
                      total_frames INTEGER,
                      total_segments INTEGER,
                      updated_at DATETIME)"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS segment_progress
                     (task_id TEXT,
                      segment_key TEXT,
                      segment_index INTEGER,
                      start_frame INTEGER,
                      end_frame INTEGER,
                      total_frames INTEGER,
                      last_done_frame INTEGER,
                      updated_at DATETIME,
                      PRIMARY KEY (task_id, segment_key))"""
        )
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
            """CREATE TABLE IF NOT EXISTS transcription_media_state
               (task_id TEXT,
                media_key TEXT,
                source_path TEXT,
                media_signature TEXT,
                asr_signature TEXT,
                translation_signature TEXT,
                phase TEXT,
                source_segments_json TEXT,
                translated_segments_json TEXT,
                updated_at DATETIME,
                PRIMARY KEY (task_id, media_key))"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS transcription_translation_state
               (task_id TEXT,
                media_key TEXT,
                segment_index INTEGER,
                source_text_hash TEXT,
                translated_text TEXT,
                status TEXT,
                message TEXT,
                updated_at DATETIME,
                PRIMARY KEY (task_id, media_key, segment_index))"""
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_transcription_media_state_task ON transcription_media_state(task_id)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_transcription_translation_state_task ON transcription_translation_state(task_id)"
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
    except Exception as exc:
        logger.critical("[FAILED] Failed to initialize database: %s", exc)
        sys.exit(1)
