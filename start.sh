#!/bin/bash
set -e

# Start worker in background and log to a file
python /workspace/worker.py > /workspace/output/worker.log 2>&1 &
WORKER_PID=$!
echo "Worker started with PID $WORKER_PID"

# Start Streamlit in foreground
echo "Starting Streamlit..."
streamlit run /workspace/streamlit_app.py --server.port=8501 --server.address=0.0.0.0 &
STREAMLIT_PID=$!

# Wait for any process to exit
wait -n

# Exit with status of process that exited first
exit $?
