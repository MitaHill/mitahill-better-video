import subprocess
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("FFMPEG")


def _write_ffmpeg_stderr(stderr_text):
    logs_dir = Path("/workspace/storage/logs/ffmpeg_stderr")
    logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = logs_dir / f"{stamp}.log"
    log_path.write_text(stderr_text or "", encoding="utf-8")
    return log_path


def run_ffmpeg(args, fallback_args=None):
    """Run ffmpeg and raise error on failure."""
    logger.info("Running: %s", " ".join(args))
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0 and fallback_args:
        logger.warning("ffmpeg failed, retrying without HWAccel.")
        logger.info("Fallback: %s", " ".join(fallback_args))
        proc = subprocess.run(fallback_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        stderr_text = proc.stderr or ""
        log_path = _write_ffmpeg_stderr(stderr_text)
        tail_lines = stderr_text.strip().splitlines()[-20:]
        tail_text = "\n".join(tail_lines)
        logger.error("ffmpeg failed (last 20 lines):\n%s", tail_text)
        logger.error("Full ffmpeg stderr archived at %s", log_path)
        raise RuntimeError(f"ffmpeg failed: {tail_text}")

def get_video_codec(file_path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.stdout.strip().lower()

def get_video_duration(file_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 0.0

def get_video_fps(file_path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        raw = result.stdout.strip()
        if '/' in raw:
            num, den = raw.split('/')
            return float(num) / float(den)
        return float(raw)
    except:
        return 30.0

def get_video_total_frames(file_path):
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=nb_frames,avg_frame_rate:format=duration",
        "-of", "json", str(file_path)
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        payload = json.loads(result.stdout.strip() or "{}")
        stream = (payload.get("streams") or [{}])[0]
        nb_frames = stream.get("nb_frames")
        if nb_frames and str(nb_frames).isdigit():
            return int(nb_frames)
        avg_rate = stream.get("avg_frame_rate", "0/1")
        if "/" in avg_rate:
            num, den = avg_rate.split("/")
            fps = float(num) / float(den) if float(den) else 0.0
        else:
            fps = float(avg_rate)
        duration = float((payload.get("format") or {}).get("duration", 0.0))
        if fps > 0 and duration > 0:
            return max(1, int(round(fps * duration)))
    except Exception:
        pass
    return 0


def get_audio_channels(file_path):
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=channels",
        "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return int(result.stdout.strip())
    except Exception:
        return 0

def get_gpu_utilization():
    try:
        result = subprocess.run(
            ["nvidia-smi", "dmon", "-s", "u", "-c", "1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        lines = [ln for ln in result.stdout.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        if not lines:
            return None
        last = lines[-1].split()
        numeric = [int(n) for n in last if n.isdigit()]
        if len(numeric) >= 2:
            return max(numeric[1:4]) if len(numeric) >= 4 else max(numeric[1:])
    except Exception:
        pass
    return None


_CODEC_ENCODERS = {
    "h264": ("h264_nvenc", "libx264"),
    "h265": ("hevc_nvenc", "libx265"),
    "av1": ("av1_nvenc", "libaom-av1"),
}


_ENCODERS_CACHE = None
_ENCODER_USABLE_CACHE = {}


def reset_ffmpeg_encoders_cache():
    """清掉进程内的编码器探测缓存（供测试使用）。"""
    global _ENCODERS_CACHE
    _ENCODERS_CACHE = None
    _ENCODER_USABLE_CACHE.clear()


def get_ffmpeg_encoders():
    # 编码器在容器生命周期内不会变，但这个函数处在任务提交和合帧路径上，
    # 不缓存就会每次 fork 一个 ffmpeg。只缓存探测出编码器的结果：
    # 异常和空结果都算探测没成功，写进缓存会让一次瞬时失败把整个进程
    # 永久卡在"没有可用编码器"。
    global _ENCODERS_CACHE
    if _ENCODERS_CACHE:
        return _ENCODERS_CACHE
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except Exception:
        return frozenset()
    text = f"{result.stdout}\n{result.stderr}"
    known = {encoder for pair in _CODEC_ENCODERS.values() for encoder in pair}
    found = frozenset(
        name for name in {item for line in text.splitlines() for item in line.split()} if name in known
    )
    if not found:
        # ffmpeg 正常退出但一个已知编码器都没解析出来，多半是这次探测本身出了问题。
        return found
    _ENCODERS_CACHE = found
    return _ENCODERS_CACHE


def _can_use_encoder(encoder):
    # 和上面同一个道理：只缓存"能用"。编码器不可用既可能是真的不支持，
    # 也可能是 NVENC 会话被占满、驱动抖动这类瞬时失败，缓存下来就再也
    # 恢复不了，上层的 normalize_output_codec 会一直返回 None。
    cached = _ENCODER_USABLE_CACHE.get(encoder)
    if cached:
        return True
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=size=640x360:rate=1",
                "-frames:v", "1", "-c:v", encoder, "-f", "null", "-"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
    except Exception:
        return False
    if result.returncode != 0:
        logger.info("FFmpeg encoder unavailable: %s (%s)", encoder, (result.stderr or "").strip())
        return False
    _ENCODER_USABLE_CACHE[encoder] = True
    return True


def get_available_output_codecs():
    encoders = get_ffmpeg_encoders()
    return [
        codec
        for codec, (gpu_encoder, _cpu_encoder) in _CODEC_ENCODERS.items()
        if gpu_encoder in encoders and _can_use_encoder(gpu_encoder)
    ]


def normalize_output_codec(value):
    codec = (value or "h264").lower()
    if codec == "hevc":
        codec = "h265"
    available = get_available_output_codecs()
    if not available:
        return None
    return codec if codec in available else available[0]


def get_video_encoder(codec, prefer_gpu=True):
    normalized = "h265" if codec == "hevc" else (codec or "h264")
    gpu_encoder, cpu_encoder = _CODEC_ENCODERS.get(normalized, _CODEC_ENCODERS["h264"])
    return gpu_encoder if prefer_gpu else cpu_encoder
