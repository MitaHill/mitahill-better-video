import logging
import subprocess

from app.src.Database import core as db
from app.src.Notifications.events import send_event

from .common import parse_ffmpeg_time

logger = logging.getLogger("CONVERTER")


def emit_progress(task_id, progress, message, *, file_index=0, file_count=0):
    db.update_task_status(task_id, "PROCESSING", int(progress), message)
    send_event(
        {
            "task_id": task_id,
            "progress": int(progress),
            "message": message,
            "segment_index": file_index,
            "segment_count": file_count,
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
            emit_progress(task_id, progress, stage_message, file_index=file_index, file_count=file_count)
            last_progress = progress
    returncode = proc.wait()
    if returncode != 0:
        tail = "\n".join(stderr_lines[-20:])
        raise RuntimeError(f"ffmpeg failed: {tail}")
