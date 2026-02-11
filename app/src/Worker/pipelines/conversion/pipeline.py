import json
from pathlib import Path

from app.src.Database import core as db
from app.src.Notifications.events import send_event

from .batch_ops import process_demux_streams, process_export_frames
from .packaging import zip_paths
from .progress import emit_progress
from .transcode import render_single_video


def process_conversion_task(task):
    task_id = task["task_id"]
    params = json.loads(task.get("task_params") or "{}")
    run_dir = Path("/workspace/storage/output") / f"run_{task_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    video_files = params.get("video_files") or []
    audio_files = params.get("audio_files") or []
    mode = (params.get("convert_mode") or "transcode").lower()

    video_paths = [Path(item.get("upload_path")) for item in video_files if item.get("upload_path")]
    audio_paths = [Path(item.get("upload_path")) for item in audio_files if item.get("upload_path")]
    video_paths = [p for p in video_paths if p.exists()]
    audio_paths = [p for p in audio_paths if p.exists()]

    if not video_paths:
        raise RuntimeError("No uploaded videos for conversion.")

    emit_progress(task_id, 2, "转换任务初始化中...")
    if mode == "export_frames":
        result_path = process_export_frames(task_id, video_paths, params, run_dir)
    elif mode == "demux_streams":
        result_path = process_demux_streams(task_id, video_paths, run_dir)
    else:
        outputs = []
        total = max(1, len(video_paths))
        for idx, video_path in enumerate(video_paths, start=1):
            outputs.append(render_single_video(task_id, video_path, audio_paths, params, run_dir, idx, total))
        if len(outputs) == 1:
            result_path = outputs[0]
        else:
            result_path = run_dir / "results" / f"convert_{task_id}.zip"
            zip_paths(outputs, result_path, run_dir / "results")

    db.update_task_result(task_id, result_path)
    db.update_task_status(task_id, "COMPLETED", 100, f"Completed: {Path(result_path).name}")
    send_event({"task_id": task_id, "progress": 100, "message": "转换任务已完成"})
