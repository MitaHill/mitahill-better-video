import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# --- Fail-Fast Configuration Loading ---
# We use standard python-dotenv. If it's missing or .env is corrupt, the app should fail.
env_path = Path(".env")
if not load_dotenv(dotenv_path=env_path, override=True):
    # We do not fallback to empty values silently if .env is expected but missing.
    # Note: In some Docker setups, vars are passed via ENV, so we check if key vars exist.
    print(f"Warning: .env file not found at {env_path.absolute()} or empty. Relying on System ENV.")

def get_env_bool(key, default):
    val = os.getenv(key, str(default)).lower()
    return val in ("true", "1", "yes", "on")

def get_env_int(key, default):
    val = os.getenv(key)
    if val is None:
        return default
    return int(val)

def get_env_float(key, default):
    val = os.getenv(key)
    if val is None:
        return default
    return float(val)

# --- Configuration (Raise AttributeError if critical config fails) ---
try:
    TASK_TTL_HOURS = get_env_float("TASK_TTL_HOURS", 12.0)
    DEFAULT_UPSCALE_FACTOR = get_env_int("DEFAULT_UPSCALE_FACTOR", 2)
    DEFAULT_MODEL_NAME = os.getenv("DEFAULT_MODEL_NAME", "realesrgan-x4plus")
    DEFAULT_TILE_PADDING = get_env_int("DEFAULT_TILE_PADDING", 10)
    DEFAULT_FP16 = get_env_bool("DEFAULT_FP16", True)
    DEFAULT_CRF = get_env_int("DEFAULT_CRF", 18)
    DEFAULT_KEEP_AUDIO = get_env_bool("DEFAULT_KEEP_AUDIO", True)
    MAX_VIDEO_SIZE_MB = get_env_int("MAX_VIDEO_SIZE_MB", 1024)
    MAX_IMAGE_SIZE_MB = get_env_int("MAX_IMAGE_SIZE_MB", 1024)
    SEGMENT_TIME_SECONDS = get_env_int("SEGMENT_TIME_SECONDS", 300)
    FALLBACK_VRAM_GB = get_env_float("FALLBACK_VRAM_GB", 4.0)
except Exception as e:
    print(f"CRITICAL: Failed to parse configuration: {e}")
    raise

def get_gpu_memory_gb():
    """Try to get GPU memory in GB using nvidia-smi."""
    try:
        cmd = ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        mem_mb = float(result.stdout.strip().split('\n')[0])
        return mem_mb / 1024.0
    except Exception as e:
        # Instead of silent fallback, we log the failure
        print(f"GPU Detection Failed: {e}")
        return None

def get_smart_tile_size():
    env_tile = get_env_int("DEFAULT_TILE_SIZE", 0)
    if env_tile > 0:
        return env_tile

    vram = get_gpu_memory_gb()
    if vram is None:
        print(f"Using fallback VRAM: {FALLBACK_VRAM_GB}GB")
        vram = FALLBACK_VRAM_GB
    
    if vram < 4: return 128
    elif vram < 6: return 256
    elif vram < 10: return 400
    else: return 512

DEFAULT_SMART_TILE_SIZE = get_smart_tile_size()