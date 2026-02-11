import logging
import shutil
import subprocess
import threading
import time
from typing import Dict, List

from app.src.Database import gpu_metrics as db_gpu

logger = logging.getLogger("GPU_METRICS")


class GpuSamplerService:
    def __init__(self, interval_sec: float = 1.0, retention_hours: int = 24):
        self._interval_sec = max(float(interval_sec or 1.0), 0.5)
        self._retention_hours = max(int(retention_hours or 24), 1)
        self._thread = None
        self._stop_event = threading.Event()
        self._sample_count = 0

    def start(self):
        if self.is_running():
            return
        if not shutil.which("nvidia-smi"):
            logger.warning("nvidia-smi not found; GPU metrics sampler disabled.")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="gpu-sampler", daemon=True)
        self._thread.start()
        logger.info("GPU metrics sampler started (interval=%.1fs)", self._interval_sec)

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            try:
                self._thread.join(timeout=2.0)
            except AssertionError:
                # eventlet monkey patch can raise "Cannot switch to MAINLOOP from MAINLOOP"
                # while joining a native thread from signal shutdown context.
                logger.warning("GPU sampler join skipped due eventlet shutdown context.")
        self._thread = None
        logger.info("GPU metrics sampler stopped")

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def status(self):
        return "running" if self.is_running() else "stopped"

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                rows = self._read_gpu_rows()
                if rows:
                    db_gpu.insert_gpu_samples(rows)
                    self._sample_count += 1
                    if self._sample_count % 60 == 0:
                        db_gpu.prune_old_samples(self._retention_hours)
            except Exception as exc:
                logger.warning("GPU sample failed: %s", exc)
            self._stop_event.wait(self._interval_sec)

    def _read_gpu_rows(self) -> List[Dict]:
        cmd = [
            "nvidia-smi",
            "--query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu",
            "--format=csv,noheader,nounits",
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2.5)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or f"nvidia-smi failed: {proc.returncode}")

        rows = []
        for line in (proc.stdout or "").splitlines():
            raw = [part.strip() for part in line.split(",")]
            if len(raw) < 7:
                continue
            rows.append(
                {
                    "gpu_index": _safe_int(raw[0]),
                    "gpu_name": raw[1],
                    "utilization_gpu": _safe_float(raw[2]),
                    "utilization_mem": _safe_float(raw[3]),
                    "memory_used_mb": _safe_float(raw[4]),
                    "memory_total_mb": _safe_float(raw[5]),
                    "temperature_c": _safe_float(raw[6]),
                }
            )
        return rows


def _safe_int(value, default=0):
    try:
        return int(str(value).strip())
    except Exception:
        return int(default)


def _safe_float(value, default=0.0):
    try:
        return float(str(value).strip())
    except Exception:
        return float(default)
