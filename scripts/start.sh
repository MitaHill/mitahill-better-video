#!/bin/bash

echo "--- Starting Real-ESRGAN Web Application Bundle ---"

# Ensure app modules are discoverable
export PYTHONPATH="/workspace/app:${PYTHONPATH}"

# Flask main entrypoint starts API + worker.
echo "Starting Flask backend..."
python3 app/main.py
