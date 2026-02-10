# Architecture (Flask + Vue)

## Overview
- Flask provides REST endpoints for task submission, status, previews, and download.
- Worker runs in a dedicated subprocess started by `app/main.py`.
- Vue (Vite) builds to static assets served by Flask from `app/WebUI/dist`.

## Service Flow
1. Frontend uploads file to `POST /api/tasks`.
2. Backend writes file into `/workspace/storage/upload/run_<task_id>/` and inserts task row.
3. Worker picks pending task, processes with Real-ESRGAN, updates progress.
4. Frontend polls `GET /api/tasks/<task_id>` and shows previews.
5. Finished output is downloaded from `/api/tasks/<task_id>/result`.

## Process Model
- **Main process**: Flask API server
- **Worker process**: long-running task processing loop

## WebUI Module Layout
- `app/WebUI/src/pages/WorkbenchPage.vue`: page shell only (layout + component assembly).
- `app/WebUI/src/components/workbench/WorkbenchHeader.vue`: theme selector + category switch entry.
- `app/WebUI/src/components/navigation/TopCategoryTabs.vue`: animated top menu (nonlinear slider + color transition).
- `app/WebUI/src/components/workbench/TaskCreatePanel.vue`: task creation panel shell.
- `app/WebUI/src/components/workbench/EnhanceTaskForm.vue`: enhance form module.
- `app/WebUI/src/components/workbench/ConvertTaskForm.vue`: conversion form module.
- `app/WebUI/src/components/workbench/WatermarkTimelineEditor.vue`: watermark timeline editor module.
- `app/WebUI/src/components/workbench/enhance/*`: enhance section modules.
- `app/WebUI/src/components/workbench/convert/*`: conversion section modules.
- `app/WebUI/src/components/workbench/TaskStatusPanel.vue`: status panel shell.
- `app/WebUI/src/components/workbench/status/StatusQueryHeader.vue`: status query row + task list.
- `app/WebUI/src/components/workbench/status/StatusProgressSummary.vue`: progress and file summary.
- `app/WebUI/src/components/workbench/status/StatusPreviewGrid.vue`: preview compare block.
- `app/WebUI/src/components/workbench/status/StatusParamTable.vue`: task parameter table.
- `app/WebUI/src/composables/useWorkbenchController.js`: workbench state orchestration and API interactions.
- `app/WebUI/src/composables/workbench/*`: atomic workbench logic units (theme/routing/forms/uploads/status/submission/builders).
- `app/WebUI/src/constants/workbench.js`: category path and menu constants.
- `app/WebUI/src/styles/navigation.css`: top menu animation/style module.

## Frontend Maintainability Rule
- Do not reintroduce large single-file page components.
- Keep page files focused on composition, move domain logic to composables, and move view sections to dedicated components.

## Storage
- SQLite: `/workspace/storage/data/tasks.db`
- Outputs: `/workspace/storage/output/sr_*`
- Run scratch: `/workspace/storage/output/run_<task_id>/`
- Uploads: `/workspace/storage/upload/run_<task_id>/`
