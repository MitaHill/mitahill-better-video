#!/bin/bash

echo "--- Starting Real-ESRGAN Web Application Bundle ---"

# Ensure app modules are discoverable
export PYTHONPATH="/workspace/app:${PYTHONPATH}"

# Start worker in background, unbuffered output
# 2>&1 | tee ... helps us see it in docker logs AND file
python3 -u /workspace/app/worker.py 2>&1 | tee /workspace/worker.log &
WORKER_PID=$!
echo "Worker started with PID $WORKER_PID"

# Start Streamlit in foreground
echo "Starting Streamlit..."
streamlit run /workspace/app/streamlit_app.py --server.port=8501 --server.address=0.0.0.0
