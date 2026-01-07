import os
import shutil
import subprocess
from pathlib import Path

# Try to load dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def get_env_bool(key, default):
    val = os.getenv(key, str(default)).lower()
    return val in ("true", "1", "yes", "on")

def get_env_int(key, default):
    try:
        return int(os.getenv(key, default))
    except:
        return default

def get_env_float(key, default):
    try:
        return float(os.getenv(key, default))
    except:
        return default

# --- Configuration ---
TASK_TTL_HOURS = get_env_float("TASK_TTL_HOURS", 12.0)

DEFAULT_UPSCALE_FACTOR = get_env_int("DEFAULT_UPSCALE_FACTOR", 2)
DEFAULT_MODEL_NAME = os.getenv("DEFAULT_MODEL_NAME", "realesrgan-x4plus")
DEFAULT_TILE_PADDING = get_env_int("DEFAULT_TILE_PADDING", 10)
DEFAULT_FP16 = get_env_bool("DEFAULT_FP16", True)
DEFAULT_CRF = get_env_int("DEFAULT_CRF", 18)
DEFAULT_KEEP_AUDIO = get_env_bool("DEFAULT_KEEP_AUDIO", True)

# Upload Limits
MAX_VIDEO_SIZE_MB = get_env_int("MAX_VIDEO_SIZE_MB", 1024)
MAX_IMAGE_SIZE_MB = get_env_int("MAX_IMAGE_SIZE_MB", 1024)

# Video Segmentation
SEGMENT_TIME_SECONDS = get_env_int("SEGMENT_TIME_SECONDS", 300)

# Fallback VRAM in GB (used if nvidia-smi fails)
FALLBACK_VRAM_GB = get_env_float("FALLBACK_VRAM_GB", 4.0)

def get_gpu_memory_gb():
    """Try to get GPU memory in GB using nvidia-smi."""
    try:
        cmd = ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            mem_mb = float(result.stdout.strip().split('\n')[0])
            return mem_mb / 1024.0
    except:
        pass
    return None

def get_smart_tile_size():
    """Calculate default tile size based on VRAM."""
    # 1. Check if user forced a specific default in .env (if not 0)
    env_tile = get_env_int("DEFAULT_TILE_SIZE", 0)
    if env_tile > 0:
        return env_tile

    # 2. Detect VRAM
    vram = get_gpu_memory_gb()
    if vram is None:
        vram = FALLBACK_VRAM_GB
    
    # 3. Heuristic
    # Very conservative estimates for x4 upscaling in FP16
    if vram < 4:
        return 128
    elif vram < 6:
        return 256
    elif vram < 10:
        return 400
    else:
        # > 10GB VRAM usually can handle 512 or even no-tiling for 720p/1080p
        # But return 512 as a safe large default
        return 512

DEFAULT_SMART_TILE_SIZE = get_smart_tile_size()
