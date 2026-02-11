import subprocess
import json
import logging
from datetime import datetime
from pathlib import Path
import time

logger = logging.getLogger("FFMPEG")


def _write_ffmpeg_stderr(stderr_text):
    logs_dir = Path("/workspace/storage/logs/ffmpeg_stderr")
    logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = logs_dir / f"{stamp}.log"
    log_path.write_text(stderr_text or "", encoding="utf-8")
    return log_path


def _with_no_stdin(args):
    safe_args = list(args or [])
    if not safe_args:
        return safe_args
    if safe_args[0] != "ffmpeg":
        return safe_args
    if "-nostdin" in safe_args:
        return safe_args
    return [safe_args[0], "-nostdin", *safe_args[1:]]


def run_ffmpeg(args, fallback_args=None, timeout_sec=None):
    """Run ffmpeg and raise error on failure."""
    safe_args = _with_no_stdin(args)
    safe_fallback_args = _with_no_stdin(fallback_args) if fallback_args else None
    logger.info("Running: %s", " ".join(safe_args))
    started = time.time()
    try:
        proc = subprocess.run(
            safe_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        tail = str(exc.stderr or "").strip().splitlines()[-20:]
        tail_text = "\n".join(tail)
        raise RuntimeError(f"ffmpeg timeout after {timeout_sec}s: {tail_text}") from exc
    if proc.returncode != 0 and fallback_args:
        logger.warning("ffmpeg failed, retrying without HWAccel.")
        logger.info("Fallback: %s", " ".join(safe_fallback_args))
        started = time.time()
        try:
            proc = subprocess.run(
                safe_fallback_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_sec,
            )
        except subprocess.TimeoutExpired as exc:
            tail = str(exc.stderr or "").strip().splitlines()[-20:]
            tail_text = "\n".join(tail)
            raise RuntimeError(f"ffmpeg fallback timeout after {timeout_sec}s: {tail_text}") from exc
    if proc.returncode != 0:
        stderr_text = proc.stderr or ""
        log_path = _write_ffmpeg_stderr(stderr_text)
        tail_lines = stderr_text.strip().splitlines()[-20:]
        tail_text = "\n".join(tail_lines)
        logger.error("ffmpeg failed (last 20 lines):\n%s", tail_text)
        logger.error("Full ffmpeg stderr archived at %s", log_path)
        raise RuntimeError(f"ffmpeg failed: {tail_text}")
    logger.info("ffmpeg done in %.2fs", time.time() - started)

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
