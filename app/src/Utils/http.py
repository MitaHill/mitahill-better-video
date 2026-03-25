import json
import subprocess
from pathlib import Path

from .text_safety import validate_filename_text


def ffprobe_info(file_path: Path):
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels,bit_rate:format=duration,bit_rate,format_name",
            "-of",
            "json",
            str(file_path),
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        data = json.loads(res.stdout or "{}")
        streams = data.get("streams", []) or []
        fmt = data.get("format", {}) or {}

        video_stream = None
        audio_stream = None

        for s in streams:
            stype = s.get("codec_type")
            if stype == "video" and video_stream is None:
                video_stream = s
            elif stype == "audio" and audio_stream is None:
                audio_stream = s

        duration = float(fmt.get("duration", 0) or 0)
        width = int((video_stream or {}).get("width", 0) or 0)
        height = int((video_stream or {}).get("height", 0) or 0)
        video_codec = ((video_stream or {}).get("codec_name") or "").lower() or None
        audio_codec = ((audio_stream or {}).get("codec_name") or "").lower() or None

        fps_raw = (video_stream or {}).get("r_frame_rate", "0/1")
        if "/" in fps_raw:
            n, d = fps_raw.split("/")
            fps = float(n) / float(d) if float(d) != 0 else 0.0
        else:
            fps = float(fps_raw or 0)

        audio_sample_rate = int((audio_stream or {}).get("sample_rate", 0) or 0)
        audio_channels = int((audio_stream or {}).get("channels", 0) or 0)
        audio_bitrate = int((audio_stream or {}).get("bit_rate", 0) or 0)
        video_bitrate = int((video_stream or {}).get("bit_rate", 0) or 0)
        format_bitrate = int(fmt.get("bit_rate", 0) or 0)
        stream_types = sorted({(s.get("codec_type") or "").lower() for s in streams if s.get("codec_type")})

        return {
            "duration": duration,
            "fps": round(fps, 2),
            "width": width,
            "height": height,
            "video_codec": video_codec,
            "audio_codec": audio_codec,
            "video_bitrate": video_bitrate,
            "audio_bitrate": audio_bitrate,
            "audio_sample_rate": audio_sample_rate,
            "audio_channels": audio_channels,
            "format_bitrate": format_bitrate,
            "format_name": fmt.get("format_name"),
            "has_video": video_stream is not None,
            "has_audio": audio_stream is not None,
            "stream_types": stream_types,
        }
    except Exception:
        return {
            "duration": 0.0,
            "fps": 0.0,
            "width": 0,
            "height": 0,
            "video_codec": None,
            "audio_codec": None,
            "video_bitrate": 0,
            "audio_bitrate": 0,
            "audio_sample_rate": 0,
            "audio_channels": 0,
            "format_bitrate": 0,
            "format_name": None,
            "has_video": False,
            "has_audio": False,
            "stream_types": [],
        }


def secure_filename(name: str) -> str:
    safe = name.replace("/", "_").replace("\\", "_").strip()
    safe = safe.replace("..", "_")
    for ch in '<>:"|?*':
        safe = safe.replace(ch, "_")
    safe = safe.rstrip(" .")
    return safe or "upload.bin"

def is_filename_safe(name: str, max_len: int = 180) -> bool:
    return validate_filename_text(name, max_len=max_len) is None
