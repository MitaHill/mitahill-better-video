import os
import subprocess
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# --- Standardized Logging ---
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
logging.basicConfig(
    level=logging.DEBUG,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("CONFIG")

# --- Fail-Fast Configuration Loading ---
env_path = Path(".env")
if env_path.exists():
    logger.info(f"Loading configuration from {env_path.absolute()}")
    if not load_dotenv(dotenv_path=env_path, override=True):
        logger.critical("[FAILED] .env file found but could not be parsed.")
        sys.exit(1)
else:
    logger.warning(".env file not found. Relying on System Environment Variables.")

def get_env_bool(key, default):
    val = os.getenv(key, str(default)).lower()
    res = val in ("true", "1", "yes", "on")
    logger.debug(f"Config: {key} = {res} (from '{val}')")
    return res

def get_env_int(key, default):
    val = os.getenv(key)
    if val is None:
        logger.debug(f"Config: {key} using default {default}")
        return default
    try:
        res = int(val)
        logger.debug(f"Config: {key} = {res}")
        return res
    except ValueError:
        logger.critical(f"[FAILED] Invalid integer for {key}: '{val}'")
        sys.exit(1)

def get_env_float(key, default):
    val = os.getenv(key)
    if val is None:
        logger.debug(f"Config: {key} using default {default}")
        return default
    try:
        res = float(val)
        logger.debug(f"Config: {key} = {res}")
        return res
    except ValueError:
        logger.critical(f"[FAILED] Invalid float for {key}: '{val}'")
        sys.exit(1)

# --- Configuration Mapping ---
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
    logger.info("Configuration loaded successfully.")
except Exception as e:
    logger.critical(f"[FAILED] Critical error during config initialization: {e}")
    sys.exit(1)

def get_gpu_memory_gb():
    """Try to get GPU memory in GB using nvidia-smi."""
    logger.debug("Attempting GPU VRAM detection...")
    try:
        cmd = ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        mem_mb = float(result.stdout.strip().split('\n')[0])
        gb = mem_mb / 1024.0
        logger.info(f"GPU Detected: {gb:.2f} GB VRAM")
        return gb
    except Exception as e:
        logger.warning(f"nvidia-smi detection failed: {e}. Using fallback strategy.")
        return None

def get_smart_tile_size():
    env_tile = get_env_int("DEFAULT_TILE_SIZE", 0)
    if env_tile > 0:
        logger.info(f"Using manually forced Tile Size: {env_tile}")
        return env_tile

    vram = get_gpu_memory_gb()
    if vram is None:
        logger.warning(f"GPU VRAM unknown. Using fallback VRAM: {FALLBACK_VRAM_GB}GB")
        vram = FALLBACK_VRAM_GB
    
    if vram < 4: res = 128
    elif vram < 6: res = 256
    elif vram < 10: res = 400
    else: res = 512
    
    logger.info(f"Smart Tile Size calculated: {res} (based on {vram:.1f}GB VRAM)")
    return res

DEFAULT_SMART_TILE_SIZE = get_smart_tile_size()
