#!/bin/bash

echo "--- Starting Real-ESRGAN Web Application Bundle ---"

# Ensure app modules are discoverable
export PYTHONPATH="/workspace/app:${PYTHONPATH}"

# Streamlit runs main.py; WorkerManager will start the worker process.
echo "Starting Streamlit..."
streamlit run /workspace/app/src_ui/main.py --server.port=8501 --server.address=0.0.0.0
