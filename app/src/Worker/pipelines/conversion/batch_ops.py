from app.src.Utils.ffmpeg import get_video_duration, run_ffmpeg

from .common import to_int
from .packaging import zip_paths
from .progress import emit_progress, run_ffmpeg_with_progress


def process_export_frames(task_id, video_paths, options, run_dir):
    results_root = run_dir / "results" / "frames"
    results_root.mkdir(parents=True, exist_ok=True)
    total = max(1, len(video_paths))
    extracted_dirs = []

    for idx, video in enumerate(video_paths, start=1):
        per_start = int(5 + (idx - 1) * (80 / total))
        per_end = int(5 + idx * (80 / total))
        out_dir = results_root / video.stem
        out_dir.mkdir(parents=True, exist_ok=True)

        fps = to_int(options.get("frame_export_fps"), 0, min_value=0, max_value=120)
        cmd = ["ffmpeg", "-y", "-i", str(video)]
        if fps > 0:
            cmd += ["-vf", f"fps={fps}"]
        cmd += ["-q:v", "2", str(out_dir / "frame_%06d.jpg")]

        run_ffmpeg_with_progress(
            cmd,
            task_id=task_id,
            duration_seconds=max(0.01, get_video_duration(video)),
            progress_start=per_start,
            progress_end=per_end,
            stage_message=f"导出帧 {idx}/{total}",
            file_index=idx,
            file_count=total,
        )
        extracted_dirs.append(out_dir)

    zip_path = run_dir / "results" / f"frames_{task_id}.zip"
    zip_paths(extracted_dirs, zip_path, run_dir / "results")
    return zip_path


def process_demux_streams(task_id, video_paths, run_dir):
    results_root = run_dir / "results" / "demux"
    results_root.mkdir(parents=True, exist_ok=True)
    total = max(1, len(video_paths))
    outputs = []

    for idx, video in enumerate(video_paths, start=1):
        per_end = int(5 + idx * (80 / total))
        stem = video.stem
        video_only = results_root / f"{stem}_video.mp4"
        audio_only = results_root / f"{stem}_audio.m4a"

        run_ffmpeg(["ffmpeg", "-y", "-i", str(video), "-map", "0:v:0", "-c", "copy", str(video_only)])
        try:
            run_ffmpeg(["ffmpeg", "-y", "-i", str(video), "-map", "0:a:0?", "-vn", "-c:a", "copy", str(audio_only)])
        except Exception:
            if audio_only.exists():
                audio_only.unlink(missing_ok=True)

        emit_progress(task_id, per_end, f"分离流 {idx}/{total}", file_index=idx, file_count=total)
        outputs.append(video_only)
        if audio_only.exists():
            outputs.append(audio_only)

    zip_path = run_dir / "results" / f"demux_{task_id}.zip"
    zip_paths(outputs, zip_path, run_dir / "results")
    return zip_path
