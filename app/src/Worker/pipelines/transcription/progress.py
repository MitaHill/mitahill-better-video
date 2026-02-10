from app.src.Database import core as db
from app.src.Notifications.events import send_event


def emit_progress(task_id, progress, message, *, file_index=0, file_count=0):
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
