import os
import subprocess
import sys
from pathlib import Path


class WorkerService:
    def __init__(self):
        self._proc = None

    def start(self):
        if self.is_running():
            return
        app_dir = Path(__file__).resolve().parents[2]
        worker_script = app_dir / "src/Worker/entrypoint.py"
        self._proc = subprocess.Popen(
            [sys.executable, "-u", str(worker_script)],
            stdout=None,
            stderr=None,
            cwd=str(app_dir),
            env=os.environ.copy(),
        )

    def stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def is_running(self):
        return self._proc is not None and self._proc.poll() is None

    def status(self):
        if self.is_running():
            return "running"
        return "stopped"
