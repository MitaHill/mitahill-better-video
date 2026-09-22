from pathlib import Path

from .http import ffprobe_info

# 链上的一步只接单个媒体文件，这里按用途分开，避免把字幕产物接回视频管线。
VIDEO_SUFFIXES = {
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".ts", ".m4v",
    ".mpg", ".mpeg", ".wmv",
}
AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


def describe_media_path(path):
    """把一个已经落盘的媒体文件描述成任务参数里通用的条目结构。"""
    file_path = Path(path)
    size_mb = file_path.stat().st_size / (1024 * 1024)
    return {
        "filename": file_path.name,
        "upload_path": str(file_path),
        "size_mb": round(size_mb, 2),
        **ffprobe_info(file_path),
    }


def apply_media_input(category, params, source_path):
    """把一个媒体文件写进任务参数，字段名跟各自管线读取的位置保持一致。

    建链时给第一步注入上传文件，链推进时给后续步骤注入上一步的产物，两边用
    同一份映射，避免字段名走偏。
    """
    item = describe_media_path(source_path)
    common = {
        "filename": item["filename"],
        "upload_path": item["upload_path"],
        "size_mb": item["size_mb"],
    }
    info = {key: value for key, value in item.items() if key not in common}

    if category == "convert":
        params["video_files"] = [item]
        video_info = {**common, "video_count": 1, **info}
    elif category == "transcribe":
        params["media_files"] = [item]
        video_info = {**common, "media_count": 1, **info}
    else:
        suffix = Path(item["filename"]).suffix.lower()
        params["filename"] = item["filename"]
        params["upload_path"] = item["upload_path"]
        params["input_type"] = "Image" if suffix in IMAGE_SUFFIXES else "Video"
        params["source_video_codec"] = item.get("video_codec")
        video_info = {**common, **info}
    return params, video_info
