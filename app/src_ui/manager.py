import streamlit as st
from pathlib import Path
import subprocess
import sys

@st.cache_resource
class WorkerManager:
    """
    Manager class for worker process.
    Starts a single worker process and keeps it alive across UI refreshes.
    """
    def __init__(self):
        self._proc = None
        self._worker_cmd = self._build_worker_cmd()
        self._log_path = self._resolve_log_path()

    def ensure_worker_running(self):
        if self._proc and self._proc.poll() is None:
            return
        self._proc = self._start_worker()

    def _build_worker_cmd(self):
        app_dir = Path(__file__).resolve().parents[1]
        worker_script = app_dir / "worker.py"
        return [sys.executable, "-u", str(worker_script)]

    def _resolve_log_path(self):
        workspace_log = Path("/workspace/worker.log")
        if workspace_log.parent.exists():
            return workspace_log
        return Path(__file__).resolve().parents[1] / "worker.log"

    def _start_worker(self):
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(self._log_path, "a", encoding="utf-8")
        return subprocess.Popen(
            self._worker_cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
