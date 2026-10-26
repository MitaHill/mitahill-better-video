import json
import logging
import math
import re
import subprocess
from pathlib import Path

from .ffmpeg import FFmpegError, run_ffmpeg

logger = logging.getLogger("FFMPEG")


def probe_media(path):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,codec_name,channels:format=duration,format_name",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode:
            raise ValueError(result.stderr.strip())
        info = json.loads(result.stdout)
        if not isinstance(info, dict) or not isinstance(info.get("streams"), list) or not info["streams"]:
            raise ValueError("未找到有效媒体流")
        return info
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"媒体探测失败 ({Path(path).name}): {exc}") from exc


def first_audio_stream(info):
    return next((stream for stream in info["streams"] if stream.get("codec_type") == "audio"), None)


def choose_audio_args(audio, container, *, force_encode=False):
    if audio is None:
        return []
    codec = audio.get("codec_name")
    channels = int(audio.get("channels") or 0)
    if container not in {"mp4", "mov", "mkv", "avi"}:
        raise ValueError(f"不支持的输出格式: {container}")
    if container == "avi":
        if channels > 2:
            raise RuntimeError("AVI 输出仅支持单声道或双声道音频，请选择 MP4 或 MKV")
        if codec == "mp3" and not force_encode:
            return ["-c:a", "copy"]
        return ["-c:a", "libmp3lame", "-b:a", "128k"]
    if not force_encode and (container == "mkv" or codec == "aac"):
        return ["-c:a", "copy"]
    return ["-c:a", "aac", "-b:a", "384k" if channels > 2 else "128k"]


def check_audio_encoder(args):
    if not args or args[1] == "copy":
        return
    encoder = args[1]
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True, text=True, timeout=10,
    )
    names = {parts[1] for line in result.stdout.splitlines() if len(parts := line.split()) >= 2}
    if result.returncode or encoder not in names:
        raise RuntimeError(f"FFmpeg 缺少所需音频编码器: {encoder}")


def mux_audio(encoded_video, original_media, output, audio, audio_args, on_transcode=None):
    def mux(args):
        cmd = ["ffmpeg", "-y", "-i", str(encoded_video)]
        if audio is not None:
            cmd += ["-i", str(original_media), "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", *args, "-shortest"]
        else:
            cmd += ["-map", "0:v:0", "-c:v", "copy", "-an"]
        run_ffmpeg([*cmd, str(output)])

    if audio_args and audio_args[1] != "copy" and on_transcode:
        on_transcode(audio_args[1])
    try:
        mux(audio_args)
    except FFmpegError as exc:
        # 输出只有视频 #0 和音轨 #1，不能把视频不兼容或损坏误判成音频兜底。
        codec = re.escape((audio or {}).get("codec_name") or "unknown")
        pattern = rf"Could not find tag for codec {codec} in stream #1, codec not currently supported in container"
        if audio is None or audio_args != ["-c:a", "copy"] or not re.search(pattern, exc.stderr):
            raise
        fallback = choose_audio_args(audio, Path(output).suffix.lstrip("."), force_encode=True)
        check_audio_encoder(fallback)
        logger.warning("音轨无法直接封装，改用 %s；首次日志: %s", fallback[1], exc.log_path)
        if on_transcode:
            on_transcode(fallback[1])
        mux(fallback)


def validate_media_output(path, *, expect_audio):
    info = probe_media(path)
    duration = float(info.get("format", {}).get("duration") or 0)
    if not any(stream.get("codec_type") == "video" for stream in info["streams"]):
        raise RuntimeError("转换结果缺少视频流")
    if not math.isfinite(duration) or duration <= 0:
        raise RuntimeError("转换结果时长无效")
    if expect_audio and first_audio_stream(info) is None:
        raise RuntimeError("转换结果缺少预期音轨")
