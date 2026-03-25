from datetime import datetime, timezone

from app.src.Database import core as db
from app.src.Notifications.events import send_event
from app.src.Utils.ffmpeg import get_gpu_utilization


def _event_now_iso():
    return datetime.now(timezone.utc).isoformat()


def emit_progress(
    task_id,
    progress,
    message,
    *,
    file_index=0,
    file_count=0,
    stage="",
    unit_done=0,
    unit_total=0,
    unit_label="",
):
    progress_value = int(max(0, min(100, progress)))
    item_index = max(0, int(file_index or 0))
    item_count = max(0, int(file_count or 0))
    db.update_task_status(task_id, "PROCESSING", progress_value, message)
    send_event(
        {
            "task_id": task_id,
            "task_category": "transcribe",
            "progress": progress_value,
            "message": message,
            "stage": str(stage or "").strip().lower(),
            "gpu_util": get_gpu_utilization(),
            "updated_at": _event_now_iso(),
            "item_index": item_index,
            "item_count": item_count,
            "item_label": "文件" if item_count else "",
            "unit_done": max(0, int(unit_done or 0)),
            "unit_total": max(0, int(unit_total or 0)),
            "unit_label": str(unit_label or "").strip(),
            "segment_index": item_index,
            "segment_count": item_count,
            "segment_frame": max(0, int(unit_done or 0)),
            "segment_total": max(0, int(unit_total or 0)),
            "total_frame": 0,
            "total_total": 0,
        }
    )
