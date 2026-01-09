import os
import subprocess
import sys
import logging
import platform
import hashlib
import yaml
from pathlib import Path

# --- Standardized Logging ---
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("CONFIG")

# --- Native .env Parser (No Dependencies) ---
def load_env_file(env_path):
    """Parses .env file and injects into os.environ"""
    path = Path(env_path)
    if not path.exists():
        logger.warning(f"No .env file found at {path}")
        return

    logger.info(f"Loading configuration from {path}")
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    
                    if key and key not in os.environ:
                        os.environ[key] = value
    except Exception as e:
        logger.error(f"Failed to parse .env file: {e}")

# Load environment immediately (repo root)
ROOT_DIR = Path(__file__).resolve().parents[1]
load_env_file(str(ROOT_DIR / "config/.env"))

# --- System Information Collection (DEBUG) ---
def log_system_info():
    logger.debug("-" * 60)
    logger.debug("SYSTEM INFORMATION GATHERING")
    logger.debug(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
    logger.debug(f"Architecture: {platform.machine()}")
    logger.debug(f"Hostname: {platform.node()}")
    logger.debug(f"Python Version: {sys.version}")
    
    # CPU Info
    try:
        if platform.system() == "Linux":
            cpu_info = subprocess.check_output("cat /proc/cpuinfo | grep 'model name' | uniq", shell=True).decode().strip()
            logger.debug(f"CPU: {cpu_info}")
        logger.debug(f"CPU Cores: {os.cpu_count()}")
    except: pass

    # Memory Info
    try:
        if platform.system() == "Linux":
            mem_info = subprocess.check_output("free -h", shell=True).decode()
            logger.debug(f"Memory Status:\n{mem_info}")
    except: pass

    # GPU Info (Detailed)
    try:
        gpu_info = subprocess.check_output(["nvidia-smi", "--query-gpu=name,driver_version,pcie.link.gen.max,vbios_version", "--format=csv,noheader"]).decode().strip()
        logger.debug(f"GPU Details: {gpu_info}")
    except:
        logger.debug("GPU Details: nvidia-smi failed to retrieve extended info.")
    logger.debug("-" * 60)

# --- Model SHA256 Verification ---
def verify_models():
    sha_file = Path(__file__).resolve().parent / "data/models_sha256.yaml"
    weights_dir = Path("/workspace/weights")
    
    if not sha_file.exists():
        logger.critical(f"[FAILED] SHA256 verification file missing: {sha_file}")
        sys.exit(1)
        
    try:
        with open(sha_file, "r") as f:
            data = yaml.safe_load(f)
            expected_hashes = data.get("models", {})
    except Exception as e:
        logger.critical(f"[FAILED] Failed to read SHA256 YAML: {e}")
        sys.exit(1)

    logger.info("Starting mandatory model integrity check...")
    for model_name, expected_sha in expected_hashes.items():
        model_path = weights_dir / model_name
        if not model_path.exists():
            logger.critical(f"[FAILED] Model file missing: {model_path}")
            sys.exit(1)
            
        logger.debug(f"Verifying {model_name}...")
        sha256_hash = hashlib.sha256()
        with open(model_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        actual_sha = sha256_hash.hexdigest()
        if actual_sha != expected_sha:
            logger.critical(f"[FAILED] SHA256 mismatch for {model_name}!")
            logger.critical(f"Expected: {expected_sha}")
            logger.critical(f"Actual:   {actual_sha}")
            sys.exit(1)
    
    logger.info("[SUCCESS] All model files verified (SHA256 matched).")

# --- Fail-Fast Configuration Loading ---

def get_env_bool(key, default):
    val = os.getenv(key, str(default)).lower()
    return val in ("true", "1", "yes", "on")

def get_env_int(key, default):
    val = os.getenv(key)
    if val is None: return default
    try: return int(val)
    except ValueError:
        logger.critical(f"[FAILED] Invalid integer for {key}: '{val}'")
        sys.exit(1)

def get_env_float(key, default):
    val = os.getenv(key)
    if val is None: return default
    try: return float(val)
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
    TASK_TIMEOUT_SECONDS = get_env_int("TASK_TIMEOUT_SECONDS", 21600)
    PROGRESS_FLUSH_SECONDS = get_env_float("PROGRESS_FLUSH_SECONDS", 3.0)
    EVENTS_ENDPOINT = os.getenv("EVENTS_ENDPOINT", "http://127.0.0.1:8501/api/events")
    FALLBACK_VRAM_GB = get_env_float("FALLBACK_VRAM_GB", 4.0)
except Exception as e:
    logger.critical(f"[FAILED] Configuration error: {e}")
    sys.exit(1)

def get_gpu_memory_gb():
    try:
        cmd = ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        mem_mb = float(result.stdout.strip().split('\n')[0])
        gb = mem_mb / 1024.0
        return gb
    except Exception as e:
        logger.error("-" * 60)
        logger.critical("[FAILED] NVIDIA GPU NOT DETECTED OR DRIVER ERROR!")
        logger.critical(f"Detailed Error: {e}")
        logger.error("-" * 60)
        sys.exit(1)

def get_smart_tile_size():
    vram = get_gpu_memory_gb()
    if vram < 4:
        res = 128
    elif vram < 6:
        res = 256
    elif vram < 10:
        res = 400
    else:
        res = 512
    return res, vram

def resolve_default_tile_size():
    env_tile = get_env_int("DEFAULT_TILE_SIZE", 0)
    if env_tile > 0:
        return env_tile, None
    smart_tile, vram = get_smart_tile_size()
    return smart_tile, vram

# --- Execution Lifecycle ---
_initialized = False
_init_info = None
DEFAULT_SMART_TILE_SIZE = 512

def initialize_context():
    global _initialized, DEFAULT_SMART_TILE_SIZE, _init_info
    if _initialized: return
    
    log_system_info()
    # Fail-fast GPU checks
    try:
        import torch
    except Exception as e:
        logger.critical(f"[FAILED] PyTorch not available for CUDA checks: {e}")
        sys.exit(1)
    if not torch.cuda.is_available():
        logger.critical("[FAILED] CUDA not available. NVIDIA GPU required.")
        sys.exit(1)
    try:
        subprocess.run(["nvidia-smi", "-L"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception as e:
        logger.critical(f"[FAILED] NVIDIA GPU not detected via nvidia-smi: {e}")
        sys.exit(1)
    try:
        gpu_name = torch.cuda.get_device_name(0)
        logger.info(f"NVIDIA GPU detected: {gpu_name}")
    except Exception as e:
        logger.critical(f"[FAILED] Unable to query NVIDIA GPU: {e}")
        sys.exit(1)
    verify_models()
    DEFAULT_SMART_TILE_SIZE, vram = resolve_default_tile_size()
    if vram is None:
        logger.info("Tile Size: %s (env override)", DEFAULT_SMART_TILE_SIZE)
        source = "env"
    else:
        logger.info("Tile Size: %s (auto by VRAM %.2f GB)", DEFAULT_SMART_TILE_SIZE, vram)
        source = "auto"
    logger.info(f"Application context initialized. Smart Tile Size: {DEFAULT_SMART_TILE_SIZE}")
    _initialized = True
    _init_info = {"tile_size": DEFAULT_SMART_TILE_SIZE, "vram_gb": vram, "source": source}
    return _init_info

def get_init_info():
    return _init_info or {"tile_size": DEFAULT_SMART_TILE_SIZE, "vram_gb": None, "source": "unknown"}

if __name__ == "__main__":
    initialize_context()
