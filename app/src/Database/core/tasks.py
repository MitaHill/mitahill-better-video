import datetime
import json
import shutil
import sqlite3
from pathlib import Path

from .common import get_connection, logger


def create_task(task_id, client_ip, task_params, video_info, task_category=None):
    logger.info("Creating new task: %s from %s", task_id, client_ip)
    category = task_category or task_params.get("task_category") or "enhance"
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO task_queue
                 (task_id, created_at, updated_at, client_ip, task_category, status, task_params, video_info, progress, message, result_path)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            task_id,
            datetime.datetime.now(),
            datetime.datetime.now(),
            client_ip,
            category,
            "PENDING",
            json.dumps(task_params),
            json.dumps(video_info),
            0,
            "Waiting to start",
            None,
        ),
    )
    c.execute("DELETE FROM task_control WHERE task_id = ?", (task_id,))
    conn.commit()
    conn.close()
    logger.debug("Task %s inserted into queue.", task_id)


def get_task(task_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM task_queue WHERE task_id = ?", (task_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_task_status(task_id, status, progress=None, message=None):
    logger.debug("Updating Task %s: %s (%s%%) - %s", task_id, status, progress, message)
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
    logger.warning("Deleting task and all associated files: %s", task_id)
    task = get_task(task_id)
    result_filename = None
    if task and task.get("task_params"):
        try:
            params = json.loads(task["task_params"])
            result_filename = f"sr_{params.get('filename')}"
        except Exception:
            pass

    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM task_queue WHERE task_id = ?", (task_id,))
    c.execute("DELETE FROM task_progress WHERE task_id = ?", (task_id,))
    c.execute("DELETE FROM segment_progress WHERE task_id = ?", (task_id,))
    c.execute("DELETE FROM task_control WHERE task_id = ?", (task_id,))
    c.execute("DELETE FROM transcription_media_state WHERE task_id = ?", (task_id,))
    c.execute("DELETE FROM transcription_translation_state WHERE task_id = ?", (task_id,))
    conn.commit()
    conn.close()

    output_root = Path("/workspace/storage/output")
    upload_root = Path("/workspace/storage/upload")
    run_dir = output_root / f"run_{task_id}"
    if run_dir.exists():
        logger.debug("Removing run dir: %s", run_dir)
        shutil.rmtree(run_dir, ignore_errors=True)
    upload_dir = upload_root / f"run_{task_id}"
    if upload_dir.exists():
        logger.debug("Removing upload dir: %s", upload_dir)
        shutil.rmtree(upload_dir, ignore_errors=True)

    if result_filename:
        stem = Path(result_filename).stem
        for path in output_root.glob(f"{stem}*"):
            if path.is_file():
                logger.debug("Removing result file: %s", path)
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
            task_id = row["task_id"]
            logger.info("Task %s picked by worker.", task_id)
            c.execute(
                "UPDATE task_queue SET status = 'PROCESSING', message = 'Initializing...', updated_at = ? WHERE task_id = ?",
                (datetime.datetime.now(), task_id),
            )
            conn.commit()
            return dict(row)
        conn.rollback()
        return None
    except Exception as exc:
        conn.rollback()
        logger.error("Atomic task pick failed: %s", exc)
        return None
    finally:
        conn.close()


def cleanup_old_tasks(hours_ttl):
    now = datetime.datetime.now()
    finished_cutoff = now - datetime.timedelta(hours=hours_ttl)
    stuck_cutoff = now - datetime.timedelta(hours=48)

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT task_id FROM task_queue
                 WHERE (status IN ('COMPLETED', 'FAILED') AND COALESCE(updated_at, created_at) < ?)
                 OR (COALESCE(updated_at, created_at) < ?)""",
        (finished_cutoff, stuck_cutoff),
    )
    rows = c.fetchall()
    conn.close()

    if rows:
        logger.info("Starting cleanup of %s tasks...", len(rows))
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
        logger.warning("Marking %s stuck tasks as FAILED...", len(rows))
        for row in rows:
            update_task_status(row[0], "FAILED", message="Task timed out")


def get_unfinished_tasks():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM task_queue WHERE status NOT IN ('COMPLETED', 'FAILED')")
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
