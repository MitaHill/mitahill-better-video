"""
Worker entrypoint for the Real-ESRGAN pipeline.

Flow:
- Initializes config + database context in worker loop
- Polls SQLite for pending tasks with an atomic pick
- Processes frames (segmenting videos when needed), writes previews and outputs
- Reports progress back to SQLite for API/UI polling
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.src.Config.logging_setup import configure_logging

if __name__ == "__main__":
    configure_logging(component="worker")
    from app.src.Worker.loop import worker_loop

    worker_loop()
