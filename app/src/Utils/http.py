import json
import subprocess
from pathlib import Path


def ffprobe_info(file_path: Path):
    try:
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate,duration",
            "-of",
            "json",
            str(file_path),
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=False)
        data = json.loads(res.stdout or "{}")
        stream = data.get("streams", [{}])[0]

        width = int(stream.get("width", 0) or 0)
        height = int(stream.get("height", 0) or 0)
        duration = float(stream.get("duration", 0) or 0)

        fps_raw = stream.get("r_frame_rate", "30/1")
        if "/" in fps_raw:
            n, d = fps_raw.split("/")
            fps = float(n) / float(d) if float(d) != 0 else 30.0
        else:
            fps = float(fps_raw)

        return {"duration": duration, "fps": round(fps, 2), "width": width, "height": height}
    except Exception:
        return {"duration": 0.0, "fps": 30.0, "width": 0, "height": 0}


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
