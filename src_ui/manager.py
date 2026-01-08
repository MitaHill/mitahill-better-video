import sys
import subprocess
import streamlit as st

@st.cache_resource
class WorkerManager:
    def __init__(self):
        self.process = None

    def ensure_worker_running(self):
        if self.process is None or self.process.poll() is not None:
            print("WorkerManager: Starting worker process...")
            self.process = subprocess.Popen(
                [sys.executable, "worker.py"],
                cwd="/workspace",
                # stdout/stderr defaults to None, which inherits from parent (Streamlit -> Docker logs)
            )
