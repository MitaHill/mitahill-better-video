import subprocess
import os
import shutil
import json
from pathlib import Path

def run_ffmpeg(args):
    """Run ffmpeg and raise error on failure."""
    print(f"Running: {' '.join(args)}")
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr}")

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
