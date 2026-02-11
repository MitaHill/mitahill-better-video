import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


DOWNLOAD_ROOT = Path("/workspace/storage/downloads/manual")


def _safe_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _safe_format(value: str, audio_only: bool) -> str:
    raw = str(value or "").strip().lower()
    if audio_only:
        allowed = {"mp3", "m4a", "wav", "flac"}
        return raw if raw in allowed else "mp3"
    allowed = {"mp4", "webm", "mkv"}
    return raw if raw in allowed else "mp4"


def _safe_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("url is required")
    if not (raw.startswith("http://") or raw.startswith("https://")):
        raise ValueError("url must start with http:// or https://")
    return raw


def _collect_files(root: Path):
    rows = []
    if not root.exists():
        return rows
    for path in sorted(root.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        stat = path.stat()
        rows.append(
            {
                "name": path.name,
                "path": str(path),
                "size_bytes": int(stat.st_size),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            }
        )
    return rows


def run_direct_video_download(url: str, output_format: str = "mp4", audio_only=False):
    if not shutil.which("yt-dlp"):
        raise RuntimeError("未找到 yt-dlp，请先在镜像中安装。")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("未找到 ffmpeg，请先在镜像中安装。")

    safe_url = _safe_url(url)
    only_audio = _safe_bool(audio_only)
    safe_format = _safe_format(output_format, only_audio)

    DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in DOWNLOAD_ROOT.glob("*") if p.is_file()}

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--restrict-filenames",
        "-P",
        str(DOWNLOAD_ROOT),
        "-o",
        "%(title).200B [%(id)s].%(ext)s",
    ]
    if only_audio:
        cmd.extend(["-x", "--audio-format", safe_format])
    else:
        cmd.extend(["--merge-output-format", safe_format])
    cmd.append(safe_url)

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        timeout=3600,
    )

    if proc.returncode != 0:
        stderr_tail = "\n".join((proc.stderr or "").splitlines()[-50:])
        stdout_tail = "\n".join((proc.stdout or "").splitlines()[-50:])
        detail = stderr_tail or stdout_tail or f"yt-dlp exit code {proc.returncode}"
        raise RuntimeError(f"yt-dlp 下载失败: {detail}")

    after = _collect_files(DOWNLOAD_ROOT)
    new_files = [item for item in after if item["name"] not in before]
    return {
        "ok": True,
        "url": safe_url,
        "audio_only": only_audio,
        "output_format": safe_format,
        "output_dir": str(DOWNLOAD_ROOT),
        "files": new_files if new_files else after[:5],
        "message": "下载完成",
    }
