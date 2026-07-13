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
- `crf`
- `output_codec` (available values come from `/api/config/recommendations`)
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

## GET /api/config/recommendations
Returns runtime recommendations. Enhancement output codecs are detected from
the FFmpeg encoders available inside the container and verified against the
current GPU:

```json
{
  "gpu_name": "NVIDIA GeForce GTX 960",
  "vram_gb": 3.94,
  "tile_size": 256,
  "upscale": 2,
  "enhance_output_codecs": ["h264", "h265"]
}
```

## Conversion APIs

### POST /api/conversions
**Content-Type**: multipart/form-data

Fields:
- `media_files` (required, multiple video files)
- `convert_mode` (`transcode` | `export_frames` | `demux_streams`)
- `output_format` (`mp4` | `mkv` | `mov` | `avi`)
- `video_codec` (`h264` | `h265`)
- `frame_rate`
- `aspect_ratio`
- `second_pass_reencode`
- `deinterlace`
- `flip_horizontal`
- `flip_vertical`
- `video_fade_in_sec`
- `video_fade_out_sec`
- `crf`
- `video_bitrate_k`
- `target_size_mb`
- `target_width`
- `target_height`
- watermark and metadata fields
- frame export fields

Audio-only uploads are rejected. Transcode outputs copy the first source audio
stream when present and do not expose audio processing parameters.

Response:
```json
{ "task_id": "<uuid>" }
```

## Transcription APIs

Transcription backend APIs are exposed through the workbench transcription
entry and admin transcription tools.

### POST /api/transcriptions
**Content-Type**: multipart/form-data

Fields:
- `media_files` (required, multiple; also compatible with `files` / `file`)
- `transcription_backend` (`whisper`)
- `transcribe_mode` (`subtitle_zip` | `subtitled_video` | `subtitle_and_video_zip`)
- `subtitle_format` (`srt` | `vtt`)
- `whisper_model`
- `language`
- `translate_to`
- `translator_provider` (`none` | `openai_compatible`)
- `translator_base_url`
- `translator_model`
- `translator_api_key`

Response:
```json
{ "task_id": "<uuid>" }
```

## Download APIs

### POST /api/downloads/probe
**Content-Type**: `multipart/form-data`

Fields:
- `url` or `source_url` (required)
- `cookie_file` (optional, Netscape cookies.txt format, max 5MB)

`cookie_file` is saved to `/workspace/storage/data/download_cookies.txt` and
will be reused by later probe/download requests. Uploading a new file replaces
the old one.

### POST /api/downloads/tasks
**Content-Type**: `multipart/form-data`

Fields:
- `source_url` (required, one URL per line for batch download)
- `download_mode` (`video` | `audio` | `subtitle_only`)
- `quality_selector`
- `video_output_format`
- `audio_output_format`
- `subtitle_output_format`
- `subtitle_languages`
- `subtitle_include_auto`
- `cookie_file` (optional, Netscape cookies.txt format, max 5MB)

When present, `cookie_file` updates the persistent download Cookie. If the
stored Cookie exists but no longer works for a source, the download fails
directly.
Created tasks use a per-task Cookie snapshot, so later Cookie uploads do not
change already queued tasks.

yt-dlp downloads use conservative defaults: one fragment at a time, 9M/s
download rate limit, short request sleeps, and retry enabled.

Response:
```json
{ "task_id": "<uuid>", "task_ids": ["<uuid>", "..."], "errors": [{ "url": "...", "error": "..." }] }
```

`errors` is only present for batch requests with partial invalid URLs. A `201`
response means at least one task was created.

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

### DELETE /api/admin/tasks/<task_id>
Header:
- `Authorization: Bearer <token>`

删除已结束任务及相关实体文件。

- 仅允许 `COMPLETED` / `FAILED` 任务。
- 删除数据库中的任务、进度、分段进度、控制记录。
- 删除对应上传目录、运行临时目录和结果文件。

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

### GET /api/admin/config/transcription-sources
Header:
- `Authorization: Bearer <token>`

读取转录与翻译配置。管理页面当前仅暴露翻译源设置；转录模型由任务创建页选择。

### PUT /api/admin/config/transcription-sources
Header:
- `Authorization: Bearer <token>`

按需增量更新转录源配置。

Request (example):
```json
{
  "transcription": {
    "backend": "whisper",
    "active_model": "medium",
    "allowed_models": ["small", "medium", "large-v3", "large"]
  },
  "translation": {
    "provider": "openai_compatible",
    "base_url": "http://127.0.0.1:8000/v1",
    "model": "qwen2.5:7b"
  }
}
```

### GET /api/admin/transcription/models
Header:
- `Authorization: Bearer <token>`

返回 OpenAI Whisper 模型目录，以及本地安装状态。

### POST /api/admin/transcription/models/download
Header:
- `Authorization: Bearer <token>`

启动模型下载任务（aria2，支持断点续传）。

Request:
```json
{ "backend": "whisper", "model_id": "medium" }
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
  "backend": "whisper",
  "model_id": "medium"
}
```
- `mode=hash`：执行到 HASH 校验即返回
- `mode=warmup` / `mode=full`：执行完整链路
- 不传 `backend/model_id` 时，使用管理页当前配置中的目标模型

### POST /api/admin/debug/test-translation-provider
Header:
- `Authorization: Bearer <token>`

执行翻译源测试：
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
