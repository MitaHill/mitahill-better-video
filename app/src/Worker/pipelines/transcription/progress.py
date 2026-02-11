from app.src.Database import core as db
from app.src.Notifications.events import send_event


class TaskCancelledError(RuntimeError):
    pass


def ensure_not_cancelled(task_id):
    if db.is_task_cancel_requested(task_id):
        db.update_task_status(task_id, "FAILED", message="已取消（管理员操作）")
        raise TaskCancelledError("任务已取消")


def emit_progress(task_id, progress, message, *, file_index=0, file_count=0):
    ensure_not_cancelled(task_id)
    progress_value = int(max(0, min(100, progress)))
    db.update_task_status(task_id, "PROCESSING", progress_value, message)
    send_event(
        {
            "task_id": task_id,
            "progress": progress_value,
            "message": message,
            "segment_index": file_index,
            "segment_count": file_count,
            "segment_frame": 0,
            "segment_total": 0,
            "total_frame": 0,
            "total_total": 0,
        }
    )
