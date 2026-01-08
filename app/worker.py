"""
Worker entrypoint for the Real-ESRGAN pipeline.

Flow:
- Initializes config + database context in src_worker.main
- Polls SQLite for pending tasks with an atomic pick
- Processes frames (segmenting videos when needed), writes previews and outputs
- Reports progress back to SQLite for API/UI polling
"""

from src_worker.main import worker_loop

if __name__ == "__main__":
    worker_loop()
