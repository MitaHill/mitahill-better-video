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


def emit_stream_event(
    task_id,
    *,
    channel,
    mode,
    text="",
    file_index=0,
    file_count=0,
    segment_index=0,
    line_key="",
    meta=None,
):
    payload = db.append_task_stream_event(
        task_id,
        channel=channel,
        mode=mode,
        text=text,
        file_index=file_index,
        file_count=file_count,
        segment_index=segment_index,
        line_key=line_key,
        meta=meta or {},
    )
    send_event(
        {
            "task_id": task_id,
            "event_type": "task_stream",
            "stream_event_id": payload.get("id"),
            "stream_channel": payload.get("channel"),
            "stream_mode": payload.get("mode"),
            "stream_text": payload.get("text"),
            "stream_line_key": payload.get("line_key"),
            "stream_created_at": payload.get("created_at"),
            "segment_index": payload.get("segment_index", 0),
            "segment_count": file_count,
            "file_index": payload.get("file_index", 0),
            "file_count": payload.get("file_count", 0),
            "stream_meta": payload.get("meta", {}),
        }
    )
