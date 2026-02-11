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

## Runtime Baseline
- Standard runtime entry is `pre-run/` (`docker compose up -d`).
- Persistent mount must target `pre-run/storage/` to avoid cross-environment state confusion.

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
- `app/WebUI/src/components/workbench/TranscribeTaskForm.vue`: transcription form module.
- `app/WebUI/src/components/workbench/WatermarkTimelineEditor.vue`: watermark timeline editor module.
- `app/WebUI/src/components/workbench/enhance/*`: enhance section modules.
- `app/WebUI/src/components/workbench/convert/*`: conversion section modules.
- `app/WebUI/src/components/workbench/transcribe/*`: transcription section modules.
- `app/src/Worker/pipelines/transcription/translation/*`: 转录翻译提供器与分段翻译子模块（Ollama/OpenAI兼容）。
- `app/src/Worker/pipelines/transcription/whisper_engine.py`: 转录执行器（支持 `whisper` / `faster_whisper` 双后端，按任务参数选择）。
- `app/src/Api/task_parsers/*`: 后端任务参数解析按类别原子化拆分（enhance/convert/transcribe/download）；`app/src/Api/parsers.py` 仅保留兼容导出层。
- `app/src/Api/routes/transcriptions_handlers/*`: 转录路由子处理器（参数应用、提交处理、运行时配置载荷）原子化拆分。
- `app/src/Api/services/form_constraints.py`: 三大任务类别统一参数约束引擎（固定锁/范围锁/不约束，前后端同源）。
- `app/WebUI/src/components/workbench/TaskStatusPanel.vue`: status panel shell.
- `app/WebUI/src/components/workbench/status/StatusQueryHeader.vue`: status query row + task list.
- `app/WebUI/src/components/workbench/status/StatusProgressSummary.vue`: progress and file summary.
- `app/WebUI/src/components/workbench/status/StatusPreviewGrid.vue`: preview compare block.
- `app/WebUI/src/components/workbench/status/StatusParamTable.vue`: task parameter table.
- `app/WebUI/src/components/admin/*`: 后端管理页原子组件（登录、任务表、IP统计、密码修改）。
- `app/WebUI/src/composables/useWorkbenchController.js`: workbench state orchestration and API interactions.
- `app/WebUI/src/composables/workbench/*`: atomic workbench logic units (theme/routing/forms/uploads/status/submission/builders).
- `app/WebUI/src/composables/workbench/submitPayloadBuilders/*`: 按任务类别拆分的提交载荷构建器（index 聚合导出）。
- `app/WebUI/src/composables/workbench/submission/*`: 提交流程原子模块（通用动作 + enhance/convert/transcribe/download 各自 submitter）。
- `app/WebUI/src/composables/workbench/useWorkbenchAdmin.js`: 管理鉴权与总览数据获取。
- `app/WebUI/src/composables/workbench/useWorkbenchFormConstraints.js`: 前端参数约束获取、字段策略解析与表单值纠正。
- `app/WebUI/src/components/admin/AdminConstraintEditor.vue`: 管理面板参数约束编辑器（按类别）。
- `app/WebUI/src/constants/formConstraints.js`: 前端字段名与后端参数名映射。
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
- Task categories in unified queue: `enhance` / `convert` / `transcribe`
- Transcription model cache roots:
  - `whisper`: `/workspace/storage/models/transcription/whisper-openai`
  - `faster_whisper`: `/workspace/storage/models/transcription/faster-whisper/<model_id>`

## Admin & Real IP
- 管理入口通过顶部菜单 `后端管理` 访问，采用密码登录，密码哈希保存在 SQLite `app_settings`。
- 后端管理页采用侧拉菜单结构，内置模糊搜索菜单项，方便后续扩展更多管理模块。
- 支持会话令牌（`admin_sessions`），接口使用 `Authorization: Bearer <token>`。
- 客户端IP解析由 `app/src/Utils/client_ip.py` 统一处理，支持 IPv4/IPv6、`Forwarded`、`X-Forwarded-For`、`X-Real-IP`。
- 通过“管理页可编辑配置 + 环境变量默认值”组合管理受信代理 CIDR，动态处理代理链，适配 Nginx / FRP 转发场景。

## Parameter Constraints
- 后端提供统一配置：`/api/admin/config/form-constraints`（管理端）与 `/api/form-constraints`（创建页）。
- 约束模型支持：
  - `free`：不约束
  - `fixed`：固定锁（用户不可改）
  - `range`：范围锁（数值字段）
- 创建任务时后端会再次应用约束，避免绕过前端直接提交非法参数。
