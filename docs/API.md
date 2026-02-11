# API Contract

## POST /api/tasks
**Content-Type**: multipart/form-data

Fields:
- `file` (required)
- `input_type` (Video | Image)
- `model_name`
- `upscale` (2/3/4)
- `tile`
- `denoise_strength`
- `keep_audio`
- `audio_enhance`
- `pre_denoise_mode`
- `haas_enabled`
- `haas_delay_ms`
- `haas_lead`
- `crf`
- `output_codec` (h264 | h265)
- `deinterlace` (true | false)
- `tile_pad`
- `fp16`

Response:
```
{ "task_id": "<uuid>" }
```

## POST /api/tasks/batch
**Content-Type**: multipart/form-data

Fields:
- `files` (required, multiple)
- 其余字段同 `/api/tasks`，批量任务共享同一组参数

Response:
```
{ "task_ids": ["<uuid>", "..."], "errors": [{ "filename": "...", "error": "...", "task_id": "<uuid>" }] }
```

## POST /api/transcriptions
**Content-Type**: multipart/form-data

Fields:
- `media_files` (required, multiple; also兼容 `files` / `file`)
- `transcription_backend` (`whisper` | `faster_whisper`，可省略；省略时使用管理页当前配置)
- `transcribe_mode` (`subtitle_zip` | `subtitled_video` | `subtitle_and_video_zip`)
- `subtitle_format` (`srt` | `vtt`)
- `whisper_model` (e.g. `small` / `medium` / `large-v3` / `turbo`)
- `language` (`auto` or language code like `zh`, `en`)
- `translate_to` (optional, 目标语言；留空表示不翻译)
- `translator_provider` (`none` | `ollama` | `openai_compatible`)
- `translator_base_url` (optional)
- `translator_model` (optional)
- `translator_api_key` (optional)
- `translator_enable_thinking` (optional, bool, 由管理页控制；当前主要对 Ollama 生效)
- `translator_prompt` (optional)
- `translator_timeout_sec` (optional)
- `generate_bilingual` (true | false)
- `export_json` (true | false)
- `prepend_timestamps` (true | false)
- `max_line_chars`
- `temperature`
- `beam_size`
- `best_of`
- `output_video_codec` (`h264` | `h265`)
- `output_audio_bitrate_k`

Response:
```
{ "task_id": "<uuid>" }
```

## GET /api/tasks/<task_id>
Response includes:
- `status` (PENDING/PROCESSING/COMPLETED/FAILED)
- `progress` (0-100)
- `message`
- `task_params`
- `video_info`
- `task_params.task_category` (`enhance` | `convert` | `transcribe`)

## GET /api/tasks/<task_id>/preview/original
Returns JPEG preview if available.

## GET /api/tasks/<task_id>/preview/upscaled
Returns JPEG preview if available.

## GET /api/tasks/<task_id>/result
Returns output file if task is completed.

## GET /api/health
Returns `{"status":"ok"}` when backend is alive.

## GET /api/form-constraints
公开读取任务创建参数约束（前端创建面板使用）。

Response:
```json
{
  "version": 1,
  "categories": {
    "enhance": {
      "global_lock": "free",
      "fields": {
        "upscale": {
          "kind": "number",
          "lock": "range",
          "default_value": 3,
          "fixed_value": 3,
          "min_value": 2,
          "max_value": 4
        }
      }
    }
  }
}
```

## Admin APIs (Password Auth)

### POST /api/admin/login
**Content-Type**: application/json

Request:
```json
{ "password": "..." }
```

Response:
```json
{ "token": "...", "session_id": "...", "expires_at": "..." }
```

### GET /api/admin/session
Header:
- `Authorization: Bearer <token>`

Response:
```json
{ "ok": true, "session_id": "...", "expires_at": "...", "client_ip": "..." }
```

### POST /api/admin/logout
Header:
- `Authorization: Bearer <token>`

### POST /api/admin/password
Header:
- `Authorization: Bearer <token>`

Request:
```json
{ "old_password": "...", "new_password": "..." }
```

### GET /api/admin/overview
Header:
- `Authorization: Bearer <token>`

Query:
- `status` (optional: PENDING/PROCESSING/COMPLETED/FAILED)
- `limit` (optional)
- `offset` (optional)

Response includes:
- `counts` (pending/processing/completed/failed/total)
- `tasks` (task_id, category, status, progress, client_ip...)
- `ip_stats` (IPv4/IPv6 with scope classification)
- `real_ip_config` (trusted proxy config and resolved request IP)
- `maintenance_mode` (bool, 是否维护模式)

### POST /api/admin/tasks/<task_id>/cancel
Header:
- `Authorization: Bearer <token>`

按任务ID取消任务。
- `PENDING`/`PROCESSING`：置为 `FAILED`，消息为“已取消（管理员操作）”
- `COMPLETED`/`FAILED`：返回当前任务状态（幂等）

### PUT /api/admin/maintenance-mode
Header:
- `Authorization: Bearer <token>`

Request:
```json
{ "enabled": true }
```

说明：
- `enabled=true`：进入维护模式，Worker 暂停拉取新任务（已有运行任务不会被强杀）
- `enabled=false`：退出维护模式，恢复任务拉取

### GET /api/admin/gpu-usage
Header:
- `Authorization: Bearer <token>`

Query:
- `seconds` (optional, 默认 60，范围 10~86400)

说明：
- 服务端每 1 秒通过 `nvidia-smi` 采样并写入数据库
- 此接口返回所选时间窗口内的按GPU分组序列，用于管理页折线图展示

### GET /api/admin/config/real-ip
Header:
- `Authorization: Bearer <token>`

Response:
```json
{
  "trusted_proxies": "127.0.0.1/32,::1/128,...",
  "resolved_client_ip": "x.x.x.x",
  "from_env_default": "..."
}
```

### PUT /api/admin/config/real-ip
Header:
- `Authorization: Bearer <token>`

Request:
```json
{ "trusted_proxies": "127.0.0.1/32,::1/128,10.0.0.0/8,..." }
```

### GET /api/admin/config/form-constraints
Header:
- `Authorization: Bearer <token>`

读取完整参数约束配置（含增强/转换/转录三类）。

### PUT /api/admin/config/form-constraints
Header:
- `Authorization: Bearer <token>`

按类别增量更新参数约束配置。

Request (example):
```json
{
  "categories": {
    "transcribe": {
      "global_lock": "free",
      "fields": {
        "temperature": {
          "lock": "range",
          "min_value": 0.0,
          "max_value": 0.7,
          "default_value": 0.2
        },
        "whisper_model": {
          "lock": "fixed",
          "fixed_value": "large-v3"
        }
      }
    }
  }
}
```

### GET /api/admin/config/transcription-sources
Header:
- `Authorization: Bearer <token>`

读取“转录模型设置 + 翻译源设置 + aria2下载参数”。

### PUT /api/admin/config/transcription-sources
Header:
- `Authorization: Bearer <token>`

按需增量更新转录源配置。

Request (example):
```json
{
  "transcription": {
    "backend": "whisper",
    "active_model": "large-v3",
    "allowed_models": ["small", "medium", "large-v3", "turbo"]
  },
  "translation": {
    "provider": "ollama",
    "base_url": "http://127.0.0.1:11434",
    "model": "qwen2.5:7b",
    "enable_thinking": false,
    "timeout_sec": 120
  },
  "download": {
    "aria2": {
      "split": 16,
      "max_connection_per_server": 16,
      "proxy": "socks5://127.0.0.1:1080"
    }
  }
}
```

### GET /api/admin/transcription/models
Header:
- `Authorization: Bearer <token>`

返回 whisper / faster-whisper 模型目录，以及本地安装状态。

### POST /api/admin/transcription/models/download
Header:
- `Authorization: Bearer <token>`

启动模型下载任务（aria2，支持断点续传）。

Request:
```json
{ "backend": "whisper", "model_id": "large-v3" }
```

### GET /api/admin/transcription/models/downloads
Header:
- `Authorization: Bearer <token>`

查看模型下载任务列表（状态、进度、错误信息）。

### GET /api/admin/transcription/models/downloads/<job_id>
Header:
- `Authorization: Bearer <token>`

查看单个模型下载任务详情。

### POST /api/admin/debug/test-transcription-model
Header:
- `Authorization: Bearer <token>`

执行转录模型测试：
1. 目标解析（读取当前管理配置中的 backend + active_model）
2. HASH 校验
3. GPU 热身（5秒静音音频识别）

Request (optional):
```json
{
  "mode": "hash",
  "backend": "faster_whisper",
  "model_id": "large-v3"
}
```
- `mode=hash`：执行到 HASH 校验即返回
- `mode=warmup` / `mode=full`：执行完整链路
- 不传 `backend/model_id` 时，使用管理页当前配置中的目标模型

### POST /api/admin/debug/test-translation-provider
Header:
- `Authorization: Bearer <token>`

执行翻译源测试：
- `ollama`: TCP-PING(3秒) -> 模型列表检查 -> 对话测速(60秒超时)
- `openai_compatible`: Chat Completions 调用 + 常见错误分类

### GET /api/admin/logs
Header:
- `Authorization: Bearer <token>`

读取数据库中的系统日志（默认 WARN+）。

Query:
- `min_level` (`WARNING` | `ERROR` | `CRITICAL` | `INFO`)
- `logger` (optional)
- `q` (optional keyword)
- `limit` (optional)
- `offset` (optional)
