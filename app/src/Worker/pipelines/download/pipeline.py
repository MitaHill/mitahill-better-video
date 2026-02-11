import json
import logging
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from app.src.Database import core as db
from app.src.Notifications.events import send_event
from app.src.Utils.http import ffprobe_info

logger = logging.getLogger("DOWNLOAD")

_PROGRESS_RE = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")


def _emit_progress(task_id: str, progress: int, message: str):
    value = max(0, min(100, int(progress)))
    db.update_task_status(task_id, "PROCESSING", value, message)
    send_event({"task_id": task_id, "progress": value, "message": message})


def _is_cancelled(task_id: str) -> bool:
    return db.is_task_cancel_requested(task_id)


def _normalize_mode(params: dict) -> str:
    mode = str(params.get("download_mode") or "video").strip().lower()
    if mode in {"video", "audio", "subtitle_only"}:
        return mode
    return "video"


def _normalize_video_format(params: dict) -> str:
    value = str(params.get("video_output_format") or "mp4").strip().lower()
    return value if value in {"mp4", "webm", "mkv"} else "mp4"


def _normalize_audio_format(params: dict) -> str:
    value = str(params.get("audio_output_format") or "mp3").strip().lower()
    return value if value in {"mp3", "m4a", "wav", "flac"} else "mp3"


def _normalize_subtitle_format(params: dict) -> str:
    value = str(params.get("subtitle_output_format") or "srt").strip().lower()
    return value if value in {"srt", "vtt"} else "srt"


def _normalize_subtitle_languages(params: dict) -> list[str]:
    raw = params.get("subtitle_languages") or []
    values = []
    if isinstance(raw, list):
        values = raw
    elif isinstance(raw, str):
        values = [item.strip() for item in raw.split(",")]
    out = []
    for item in values:
        safe = str(item or "").strip()
        if not safe:
            continue
        if safe.lower() == "all":
            return ["all"]
        out.append(safe)
    return out if out else ["all"]


def _run_yt_dlp(task_id: str, cmd: list[str], stage: str = "下载中") -> None:
    logger.info("Task %s running yt-dlp: %s", task_id, " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    tail = []
    last_progress = -1
    while True:
        if _is_cancelled(task_id):
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
            raise RuntimeError("任务已取消")

        line = proc.stdout.readline() if proc.stdout else ""
        if not line:
            if proc.poll() is not None:
                break
            continue

        text = line.strip()
        if text:
            tail.append(text)
            if len(tail) > 80:
                tail = tail[-80:]

        match = _PROGRESS_RE.search(text)
        if match:
            pct = float(match.group(1))
            progress = int(5 + pct * 0.9)
            progress = max(5, min(95, progress))
            if progress != last_progress:
                last_progress = progress
                _emit_progress(task_id, progress, f"{stage} {pct:.1f}%")
            continue
        if "[Merger]" in text or "[ExtractAudio]" in text:
            _emit_progress(task_id, 97, "封装处理中...")

    code = proc.wait()
    if code != 0:
        detail = "\n".join(tail[-25:]) if tail else f"yt-dlp exited with {code}"
        raise RuntimeError(f"yt-dlp 执行失败: {detail}")


def _pick_output_file(results_dir: Path, allowed_exts: set[str]) -> Path:
    files = []
    for path in results_dir.glob("*"):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext not in allowed_exts:
            continue
        files.append(path)
    if not files:
        raise RuntimeError("未找到下载结果文件")
    files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return files[0]


def _zip_subtitles(task_id: str, subtitle_files: list[Path], results_dir: Path) -> Path:
    zip_path = results_dir / f"subtitles_{task_id}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for item in subtitle_files:
            zf.write(item, arcname=item.name)
    return zip_path


def _run_video_download(task_id: str, source_url: str, params: dict, results_dir: Path) -> Path:
    quality = str(params.get("quality_selector") or "bestvideo*+bestaudio/best").strip()
    output_format = _normalize_video_format(params)
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--restrict-filenames",
        "-P",
        str(results_dir),
        "-o",
        "%(title).200B [%(id)s].%(ext)s",
        "--merge-output-format",
        output_format,
        "-f",
        quality,
        source_url,
    ]
    _run_yt_dlp(task_id, cmd, stage="视频下载中")
    return _pick_output_file(results_dir, {".mp4", ".webm", ".mkv"})


def _run_audio_download(task_id: str, source_url: str, params: dict, results_dir: Path) -> Path:
    output_format = _normalize_audio_format(params)
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--restrict-filenames",
        "-P",
        str(results_dir),
        "-o",
        "%(title).200B [%(id)s].%(ext)s",
        "-x",
        "--audio-format",
        output_format,
        source_url,
    ]
    _run_yt_dlp(task_id, cmd, stage="音频下载中")
    return _pick_output_file(results_dir, {".mp3", ".m4a", ".wav", ".flac"})


def _run_subtitle_download(task_id: str, source_url: str, params: dict, results_dir: Path) -> Path:
    subtitle_format = _normalize_subtitle_format(params)
    languages = _normalize_subtitle_languages(params)
    include_auto = str(params.get("subtitle_include_auto", True)).strip().lower() in {"1", "true", "yes", "on"}
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--skip-download",
        "--restrict-filenames",
        "-P",
        str(results_dir),
        "-o",
        "%(title).200B [%(id)s].%(ext)s",
        "--write-subs",
    ]
    if include_auto:
        cmd.append("--write-auto-subs")
    cmd.extend(
        [
            "--sub-langs",
            ",".join(languages),
            "--convert-subs",
            subtitle_format,
            source_url,
        ]
    )
    _run_yt_dlp(task_id, cmd, stage="字幕下载中")
    subtitle_files = sorted(
        [p for p in results_dir.glob(f"*.{subtitle_format}") if p.is_file()],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not subtitle_files:
        raise RuntimeError("未检测到可用字幕文件")
    if len(subtitle_files) == 1:
        return subtitle_files[0]
    return _zip_subtitles(task_id, subtitle_files, results_dir)


def process_download_task(task):
    task_id = task["task_id"]
    params = json.loads(task.get("task_params") or "{}")
    source_url = str(params.get("source_url") or "").strip()
    if not source_url:
        raise RuntimeError("下载任务缺少 source_url")
    if not shutil.which("yt-dlp"):
        raise RuntimeError("未找到 yt-dlp，请先在镜像安装")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("未找到 ffmpeg，请先在镜像安装")

    run_dir = Path("/workspace/storage/output") / f"run_{task_id}"
    results_dir = run_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    _emit_progress(task_id, 2, "下载任务初始化中...")
    mode = _normalize_mode(params)
    if mode == "audio":
        result_path = _run_audio_download(task_id, source_url, params, results_dir)
    elif mode == "subtitle_only":
        result_path = _run_subtitle_download(task_id, source_url, params, results_dir)
    else:
        result_path = _run_video_download(task_id, source_url, params, results_dir)

    if _is_cancelled(task_id):
        raise RuntimeError("任务已取消")

    result_file = Path(result_path)
    previous_info = {}
    try:
        previous_info = json.loads(task.get("video_info") or "{}")
    except Exception:
        previous_info = {}

    probe = ffprobe_info(result_file)
    size_mb = round((result_file.stat().st_size / (1024 * 1024)), 2)
    resolved_duration = float(probe.get("duration") or 0)
    if resolved_duration <= 0:
        resolved_duration = float(previous_info.get("duration") or 0)

    merged_info = {
        **previous_info,
        "filename": result_file.name,
        "upload_path": source_url,
        "result_path": str(result_file),
        "size_mb": size_mb,
        "duration": round(resolved_duration, 2),
        "fps": float(probe.get("fps") or 0),
        "width": int(probe.get("width") or 0),
        "height": int(probe.get("height") or 0),
        "video_codec": probe.get("video_codec"),
        "audio_codec": probe.get("audio_codec"),
        "video_bitrate": int(probe.get("video_bitrate") or 0),
        "audio_bitrate": int(probe.get("audio_bitrate") or 0),
        "audio_sample_rate": int(probe.get("audio_sample_rate") or 0),
        "audio_channels": int(probe.get("audio_channels") or 0),
        "has_video": bool(probe.get("has_video")),
        "has_audio": bool(probe.get("has_audio")),
        "stream_types": probe.get("stream_types") or [],
    }
    db.update_task_video_info(task_id, merged_info)
    db.update_task_result(task_id, result_path)
    db.update_task_status(task_id, "COMPLETED", 100, f"Completed: {Path(result_path).name}")
    send_event({"task_id": task_id, "progress": 100, "message": "下载任务已完成"})
