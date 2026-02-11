import datetime

from .common import get_connection


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
