import logging
import subprocess
from datetime import datetime, timezone

from app.src.Database import core as db
from app.src.Notifications.events import send_event
from app.src.Utils.ffmpeg import get_gpu_utilization

from .common import parse_ffmpeg_time

logger = logging.getLogger("CONVERTER")


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
    unit_done_value = max(0, int(unit_done or 0))
    unit_total_value = max(0, int(unit_total or 0))
    db.update_task_status(task_id, "PROCESSING", progress_value, message)
    send_event(
        {
            "task_id": task_id,
            "task_category": "convert",
            "progress": progress_value,
            "message": message,
            "stage": str(stage or "").strip().lower(),
            "gpu_util": get_gpu_utilization(),
            "updated_at": _event_now_iso(),
            "item_index": item_index,
            "item_count": item_count,
            "item_label": "文件" if item_count else "",
            "unit_done": unit_done_value,
            "unit_total": unit_total_value,
            "unit_label": str(unit_label or "").strip(),
            "segment_index": item_index,
            "segment_count": item_count,
            "segment_frame": 0,
            "segment_total": 0,
            "total_frame": 0,
            "total_total": 0,
        }
    )


def run_ffmpeg_with_progress(
    args,
    *,
    task_id,
    duration_seconds,
    progress_start,
    progress_end,
    stage_message,
    file_index=0,
    file_count=0,
):
    logger.info("Running ffmpeg with progress: %s", " ".join(args))
    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    stderr_lines = []
    last_progress = -1
    for raw in proc.stderr:
        line = raw.rstrip("\n")
        stderr_lines.append(line)
        if duration_seconds <= 0:
            continue
        sec = parse_ffmpeg_time(line)
        if sec is None:
            continue
        ratio = min(1.0, max(0.0, sec / duration_seconds))
        progress = int(progress_start + (progress_end - progress_start) * ratio)
        if progress > last_progress:
            emit_progress(
                task_id,
                progress,
                stage_message,
                file_index=file_index,
                file_count=file_count,
                stage="encode",
                unit_done=int(sec or 0),
                unit_total=int(duration_seconds or 0),
                unit_label="秒",
            )
            last_progress = progress
    returncode = proc.wait()
    if returncode != 0:
        tail = "\n".join(stderr_lines[-20:])
        raise RuntimeError(f"ffmpeg failed: {tail}")
