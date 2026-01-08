# Architecture (Flask + Vue)

## Overview
- Flask provides REST endpoints for task submission, status, previews, and download.
- Worker runs in a dedicated subprocess started by `app/backend/main.py`.
- Vue (Vite) builds to static assets served by Flask from `app/frontend/dist`.

## Service Flow
1. Frontend uploads file to `POST /api/tasks`.
2. Backend writes file into `/workspace/output/run_<task_id>/` and inserts task row.
3. Worker picks pending task, processes with Real-ESRGAN, updates progress.
4. Frontend polls `GET /api/tasks/<task_id>` and shows previews.
5. Finished output is downloaded from `/api/tasks/<task_id>/result`.

## Process Model
- **Main process**: Flask API server
- **Worker process**: long-running task processing loop

## Storage
- SQLite: `/workspace/output/tasks.db`
- Outputs: `/workspace/output/sr_*`
- Run scratch: `/workspace/output/run_<task_id>/`
