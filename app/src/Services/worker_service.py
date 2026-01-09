import subprocess
import sys
from pathlib import Path


class WorkerService:
    def __init__(self, log_path: Path):
        self._proc = None
        self._log_path = log_path

    def start(self):
        if self.is_running():
            return
        app_dir = Path(__file__).resolve().parents[2]
        worker_script = app_dir / "src/Worker/entrypoint.py"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(self._log_path, "a", encoding="utf-8")
        self._proc = subprocess.Popen(
            [sys.executable, "-u", str(worker_script)],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(app_dir),
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
