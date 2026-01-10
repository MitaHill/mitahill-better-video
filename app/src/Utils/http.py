import json
import subprocess
from pathlib import Path


def ffprobe_info(file_path: Path):
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration",
            "-of",
            "json",
            str(file_path),
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        data = json.loads(res.stdout or "{}")
        streams = data.get("streams", []) or []

        video_codec = None
        audio_codec = None
        width = 0
        height = 0
        fps_raw = "30/1"

        for s in streams:
            stype = s.get("codec_type")
            if stype == "video" and video_codec is None:
                video_codec = (s.get("codec_name") or "").lower() or None
                width = int(s.get("width", 0) or 0)
                height = int(s.get("height", 0) or 0)
                fps_raw = s.get("r_frame_rate", fps_raw)
            elif stype == "audio" and audio_codec is None:
                audio_codec = (s.get("codec_name") or "").lower() or None

        duration = float((data.get("format") or {}).get("duration", 0) or 0)
        if "/" in fps_raw:
            n, d = fps_raw.split("/")
            fps = float(n) / float(d) if float(d) != 0 else 30.0
        else:
            fps = float(fps_raw)

        return {
            "duration": duration,
            "fps": round(fps, 2),
            "width": width,
            "height": height,
            "video_codec": video_codec,
            "audio_codec": audio_codec,
        }
    except Exception:
        return {
            "duration": 0.0,
            "fps": 30.0,
            "width": 0,
            "height": 0,
            "video_codec": None,
            "audio_codec": None,
        }


def secure_filename(name: str) -> str:
    safe = name.replace("/", "_").replace("\\", "_").strip()
    return safe or "upload.bin"

def is_filename_safe(name: str, max_len: int = 180) -> bool:
    if not name or len(name) > max_len:
        return False
    for ch in name:
        if ord(ch) < 32 or ord(ch) == 127:
            return False
    if "/" in name or "\\" in name:
        return False
    return True
