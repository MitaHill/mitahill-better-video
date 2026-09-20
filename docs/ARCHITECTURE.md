# Architecture (Flask + Vue)

## Overview
- Flask provides REST endpoints for task submission, status, previews, and download.
- Worker runs in a dedicated subprocess started by `app/main.py`.
- Vue (Vite) builds to static assets served by Flask from `app/WebUI/dist`.

## Design Standard
- 本项目的代码设计优先级是：易实现、稳健、最小改动、简单。
- 优先复用现有模块和运行路径；不要为了未来可能性提前引入复杂抽象。
- 启动、恢复、清理、模型加载等基础路径必须保持短链路、可解释、可失败。
- 如果一个方案需要明显扩大状态机、调度器或跨模块耦合，应先证明简单方案不足。

## Service Flow
1. Frontend uploads file to `POST /api/tasks`.
2. Backend writes file into `/workspace/storage/upload/run_<task_id>/` and inserts task row.
3. Worker starts one isolated task process, which updates task progress.
4. Frontend reads the initial task state through `GET /api/tasks/<task_id>`, then receives progress and previews through WebSocket.
5. Finished output is downloaded from `/api/tasks/<task_id>/result`.

## Runtime Baseline
- Standard runtime entry is `pre-run/` (`docker compose up -d`).
- Persistent mount must target `pre-run/storage/` to avoid cross-environment state confusion.

## Process Model
- **Main process**: Flask API server
- **Worker process**: long-running task scheduling loop
- **Task process**: one child process per task, including conversion,
  enhancement, and transcription

## Processing Model
- Long videos are processed in segments to keep disk, memory, and VRAM usage
  bounded.
- Each segment follows the same lifecycle: extract frames, upscale, encode the
  segment, then release intermediate frames before moving on.
- This avoids full-video frame extraction for multi-hour inputs.
- Before encoding, every extracted frame must have a matching upscaled file. The
  check compares file names rather than counts, because a stale file left in
  `frames_out` can make the totals agree while a gap remains. A frame the upscaler
  failed to write would make `ffmpeg -start_number 1` stop at the gap and emit a
  silently truncated video, so a missing frame fails the task instead.
- A resumed segment only trusts a continuous prefix of finished frames and restarts
  at the first gap. Trusting the recorded resume point alone would carry an older
  gap into the pre-encode check and fail the task at the same place on every retry,
  with no way to recover.
- A task process starts its own CUDA context and owns every loaded model. It exits
  after the task reaches a terminal state, so the container releases its GPU
  context regardless of success, failure, cancellation, or OOM.
- The Worker does not cache models, inspect idle CUDA memory, or retry an OOM.
  It waits for the task process and starts the next task only after that process
  has exited.

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
- `app/src/Worker/pipelines/transcription/translation/*`: 转录翻译提供器与分段翻译子模块（仅 OpenAI 兼容 Chat Completions 格式）。
- `app/src/Worker/pipelines/transcription/engine.py`: 转录引擎入口，将本地与云端结果统一为字幕分段。
- `app/src/Worker/pipelines/transcription/whisper_engine.py`: Faster-Whisper 执行器（CUDA FP16）。
- `app/src/Worker/pipelines/transcription/scribe_engine.py`: ElevenLabs Scribe v2 适配器，负责流式上传和单词时间戳分段。
- `app/src/Media/hat_adapter.py`: 官方 HAT 架构的薄推理适配层，负责 BGR/RGB、分片、倍率输出；HAT 当前固定 fp32。
- `app/src/Api/task_parsers/*`: 后端任务参数解析按类别原子化拆分（enhance/convert/transcribe）；`app/src/Api/parsers.py` 仅保留兼容导出层。
- `app/src/Api/routes/transcriptions_handlers/*`: 转录路由子处理器（参数应用、提交处理、运行时配置载荷）原子化拆分。
- `app/WebUI/src/components/workbench/TaskStatusPanel.vue`: status panel shell.
- `app/WebUI/src/components/workbench/status/StatusQueryHeader.vue`: status query row + task list.
- `app/WebUI/src/components/workbench/status/StatusProgressSummary.vue`: progress and file summary.
- `app/WebUI/src/components/workbench/status/StatusPreviewGrid.vue`: preview compare block.
- `app/WebUI/src/components/workbench/status/StatusParamTable.vue`: task parameter table.
- `app/WebUI/src/components/admin/*`: 后端管理页原子组件（登录、任务表、IP统计、密码修改）。
- `app/WebUI/src/composables/useWorkbenchController.js`: workbench state orchestration and API interactions.
- `app/WebUI/src/composables/workbench/*`: atomic workbench logic units (theme/routing/forms/uploads/status/submission/builders).
- `app/WebUI/src/composables/workbench/submitPayloadBuilders/*`: 按任务类别拆分的提交载荷构建器（index 聚合导出）。
- `app/WebUI/src/composables/workbench/submission/*`: 提交流程原子模块（通用动作 + enhance/convert/transcribe 各自 submitter）。
- `app/WebUI/src/composables/workbench/useTranscribeLowDataMode.js`: 字幕与文本转录的低数据传输逻辑，前端用 ffmpeg.wasm 提取音频后复用原提交接口。
- `app/WebUI/src/composables/workbench/useWorkbenchAdmin.js`: 管理鉴权与总览数据获取。
- `app/WebUI/src/constants/workbench.js`: category path and menu constants.
- `app/WebUI/src/styles/navigation.css`: top menu animation/style module.

## Frontend Maintainability Rule
- Do not reintroduce large single-file page components.
- Keep page files focused on composition, move domain logic to composables, and move view sections to dedicated components.
- Transcription frontend components are exposed through the main workbench and
  admin console; keep future changes modular instead of rebuilding a large page.

## Storage
- SQLite: `/workspace/storage/data/tasks.db`
- Outputs: `/workspace/storage/output/run_<task_id>/results/`
- Run scratch: `/workspace/storage/output/run_<task_id>/`
- Uploads: `/workspace/storage/upload/run_<task_id>/`
- Task categories in unified queue: `enhance` / `convert` / `transcribe`
- Transcription model cache roots:
  - `whisper`: `/workspace/storage/models/transcription/whisper/<model_id>/`

ElevenLabs API Key 保存在 SQLite 管理配置中。公开运行配置、任务参数和日志不包含密钥原文。

## SQLite Runtime Rules
- SQLite runs in WAL mode with `synchronous=NORMAL`, `temp_store=MEMORY`, and a
  30s busy timeout.
- The intended concurrency model is one Worker writer plus API readers.
- Avoid long API transactions, especially around progress polling or admin
  task deletion.
- If multi-worker scale-out becomes necessary, move the task database to
  PostgreSQL instead of stretching SQLite beyond the single-writer model.

## Admin & Real IP
- 管理入口通过顶部菜单 `后端管理` 访问，采用密码登录，密码哈希保存在 SQLite `app_settings`。
- 后端管理页采用侧拉菜单结构，内置模糊搜索菜单项，方便后续扩展更多管理模块。
- 支持会话令牌（`admin_sessions`），接口使用 `Authorization: Bearer <token>`。
- 客户端IP解析由 `app/src/Utils/client_ip.py` 统一处理，支持 IPv4/IPv6、`Forwarded`、`X-Forwarded-For`、`X-Real-IP`。
- 通过“管理页可编辑配置 + 环境变量默认值”组合管理受信代理 CIDR，动态处理代理链，适配 Nginx / FRP 转发场景。
