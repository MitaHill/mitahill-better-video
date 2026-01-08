"""
Worker entrypoint for the Real-ESRGAN pipeline.

Flow:
- Initializes config + database context in src_worker.main
- Pulls pending tasks, processes frames, writes previews and outputs
- Reports progress back to SQLite for UI polling
"""

from src_worker.main import worker_loop

if __name__ == "__main__":
    worker_loop()
