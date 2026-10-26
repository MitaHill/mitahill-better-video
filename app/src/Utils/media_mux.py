import json
import subprocess
from pathlib import Path


def probe_media(path):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams",
             "-show_chapters", "-show_data_hash", "sha256", "-of", "json", str(path)],
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
