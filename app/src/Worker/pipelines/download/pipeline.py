import json
import logging
import re
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from app.src.Database import core as db
from app.src.Notifications.events import send_event
from app.src.Utils.http import ffprobe_info
from app.src.Utils.ffmpeg import get_gpu_utilization

logger = logging.getLogger("DOWNLOAD")

_PROGRESS_RE = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")


def _event_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit_progress(task_id: str, progress: int, message: str, *, stage: str = "download"):
    value = max(0, min(100, int(progress)))
    db.update_task_status(task_id, "PROCESSING", value, message)
    send_event(
        {
            "task_id": task_id,
            "task_category": "download",
            "progress": value,
            "message": message,
            "stage": str(stage or "").strip().lower(),
            "gpu_util": get_gpu_utilization(),
            "updated_at": _event_now_iso(),
        }
    )


def _update_download_video_info(task, result_path: Path, mode: str) -> None:
    current = json.loads(task.get("video_info") or "{}")
    info = ffprobe_info(result_path) if result_path.exists() else {}
    stat_size_mb = round((result_path.stat().st_size / (1024 * 1024)), 2) if result_path.exists() else 0
    # 下载任务分两阶段维护 video_info：
    # 1. 创建任务时先写 probe 元数据，让状态页立刻有分辨率/大小
    # 2. 真正下载完成后再用结果文件覆盖，拿到更准确的最终值
    video_info = {
        **current,
        "filename": result_path.name,
        "result_path": str(result_path),
        "size_mb": stat_size_mb or round(float(current.get("size_mb") or 0), 2),
        "duration": float(info.get("duration") or current.get("duration") or 0),
        "width": int(info.get("width") or current.get("width") or 0),
        "height": int(info.get("height") or current.get("height") or 0),
        "fps": float(info.get("fps") or current.get("fps") or 0),
        "has_video": bool(info.get("has_video", mode == "video")),
        "has_audio": bool(info.get("has_audio", mode in {"video", "audio"})),
        "download_mode": mode,
    }
    db.update_task_video_info(task["task_id"], video_info)


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
            # 把 yt-dlp 的 0-100% 压缩到任务整体进度的中段。
            # 头尾留给初始化、封装、结果回填这些不在 yt-dlp 百分比里的步骤。
            progress = int(5 + pct * 0.9)
            progress = max(5, min(95, progress))
            if progress != last_progress:
                last_progress = progress
                _emit_progress(task_id, progress, f"{stage} {pct:.1f}%", stage="download")
            continue
        if "[Merger]" in text or "[ExtractAudio]" in text:
            # yt-dlp 进入合并/抽音轨时，原始下载百分比通常已经不再变化。
            # 这里手动把状态切到 package，前端看起来就不会像是“卡住 95%”。
            _emit_progress(task_id, 97, "封装处理中...", stage="package")

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
    # 单字幕直接返回文件，多个语言时再打包。
    # 这样用户选一种语言时不会多绕一层 zip。
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

    _emit_progress(task_id, 2, "下载任务初始化中...", stage="prepare")
    mode = _normalize_mode(params)
    if mode == "audio":
        result_path = _run_audio_download(task_id, source_url, params, results_dir)
    elif mode == "subtitle_only":
        result_path = _run_subtitle_download(task_id, source_url, params, results_dir)
    else:
        result_path = _run_video_download(task_id, source_url, params, results_dir)

    if _is_cancelled(task_id):
        raise RuntimeError("任务已取消")

    _update_download_video_info(task, result_path, mode)
    db.update_task_result(task_id, result_path)
    db.update_task_status(task_id, "COMPLETED", 100, f"Completed: {Path(result_path).name}")
    send_event(
        {
            "task_id": task_id,
            "task_category": "download",
            "progress": 100,
            "message": "下载任务已完成",
            "stage": "completed",
            "gpu_util": get_gpu_utilization(),
            "updated_at": _event_now_iso(),
        }
    )
