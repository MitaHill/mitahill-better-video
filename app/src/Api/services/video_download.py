import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List


DOWNLOAD_ROOT = Path("/workspace/storage/downloads/manual")


def safe_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def safe_output_format(value: str, audio_only: bool) -> str:
    raw = str(value or "").strip().lower()
    if audio_only:
        allowed = {"mp3", "m4a", "wav", "flac"}
        return raw if raw in allowed else "mp3"
    allowed = {"mp4", "webm", "mkv"}
    return raw if raw in allowed else "mp4"


def normalize_download_url(value: str) -> str:
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


def ensure_yt_dlp_ready():
    if not shutil.which("yt-dlp"):
        raise RuntimeError("未找到 yt-dlp，请先在镜像中安装。")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("未找到 ffmpeg，请先在镜像中安装。")


def _run_probe_json(url: str) -> Dict:
    ensure_yt_dlp_ready()
    safe_url = normalize_download_url(url)
    cmd = [
        "yt-dlp",
        "--dump-single-json",
        "--skip-download",
        "--no-playlist",
        safe_url,
    ]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        timeout=120,
    )
    if proc.returncode != 0:
        detail = "\n".join((proc.stderr or proc.stdout or "").splitlines()[-50:])
        raise RuntimeError(f"解析视频信息失败: {detail or proc.returncode}")
    import json

    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"解析视频信息失败: {exc}") from exc


def _build_quality_options(formats: List[Dict]) -> tuple[list, str]:
    options = []
    seen = set()
    max_height = 0
    for item in formats or []:
        if not isinstance(item, dict):
            continue
        format_id = str(item.get("format_id") or "").strip()
        if not format_id:
            continue
        vcodec = str(item.get("vcodec") or "").strip().lower()
        if not vcodec or vcodec == "none":
            continue
        ext = str(item.get("ext") or "").strip().lower()
        if ext not in {"mp4", "webm", "mkv"}:
            continue
        height = int(item.get("height") or 0)
        fps = item.get("fps")
        tbr = item.get("tbr")
        acodec = str(item.get("acodec") or "").strip().lower()
        needs_audio_merge = acodec in {"", "none"}
        selector = f"{format_id}+bestaudio/best" if needs_audio_merge else format_id
        if selector in seen:
            continue
        seen.add(selector)
        if height > max_height:
            max_height = height
        label = f"{height or '?'}p | {ext.upper()} | {selector}"
        if fps:
            label += f" | {fps}fps"
        if tbr:
            try:
                label += f" | {float(tbr):.0f}kbps"
            except Exception:
                pass
        options.append(
            {
                "value": selector,
                "label": label,
                "height": height,
                "ext": ext,
                "format_id": format_id,
            }
        )
    options.sort(key=lambda item: (int(item.get("height") or 0), item.get("label") or ""), reverse=True)
    options.insert(
        0,
        {
            "value": "bestvideo*+bestaudio/best",
            "label": "当前可用最高（无需登录）",
            "height": max_height,
            "ext": "auto",
            "format_id": "best",
        },
    )
    max_quality = f"{max_height}p" if max_height else "未知"
    return options, max_quality


def _build_subtitle_languages(subtitles: Dict, automatic_captions: Dict) -> list:
    rows = {}
    for source_type, payload in (("manual", subtitles or {}), ("auto", automatic_captions or {})):
        if not isinstance(payload, dict):
            continue
        for code, entries in payload.items():
            safe_code = str(code or "").strip()
            if not safe_code:
                continue
            row = rows.get(safe_code) or {
                "code": safe_code,
                "label": safe_code,
                "has_manual": False,
                "has_auto": False,
            }
            row["has_manual"] = row["has_manual"] or source_type == "manual"
            row["has_auto"] = row["has_auto"] or source_type == "auto"
            if isinstance(entries, list) and entries:
                first = entries[0]
                if isinstance(first, dict):
                    name = str(first.get("name") or "").strip()
                    if name:
                        row["label"] = f"{safe_code} ({name})"
            rows[safe_code] = row
    out = sorted(rows.values(), key=lambda item: item.get("code", ""))
    return out


def probe_download_source(url: str) -> Dict:
    payload = _run_probe_json(url)
    quality_options, max_quality = _build_quality_options(payload.get("formats") or [])
    subtitle_languages = _build_subtitle_languages(
        payload.get("subtitles") or {},
        payload.get("automatic_captions") or {},
    )
    return {
        "ok": True,
        "url": normalize_download_url(url),
        "id": payload.get("id"),
        "title": payload.get("title") or "",
        "duration_sec": int(payload.get("duration") or 0),
        "uploader": payload.get("uploader") or "",
        "thumbnail": payload.get("thumbnail") or "",
        "webpage_url": payload.get("webpage_url") or "",
        "max_quality_label": max_quality,
        "quality_options": quality_options,
        "subtitle_languages": subtitle_languages,
    }


def run_direct_video_download(url: str, output_format: str = "mp4", audio_only=False):
    ensure_yt_dlp_ready()

    safe_url = normalize_download_url(url)
    only_audio = safe_bool(audio_only)
    safe_format = safe_output_format(output_format, only_audio)

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
