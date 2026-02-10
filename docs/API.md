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
- `transcribe_mode` (`subtitle_zip` | `subtitled_video` | `subtitle_and_video_zip`)
- `subtitle_format` (`srt` | `vtt`)
- `whisper_model` (e.g. `small` / `medium` / `large-v3` / `turbo`)
- `language` (`auto` or language code like `zh`, `en`)
- `translate_to` (optional, 目标语言；留空表示不翻译)
- `translator_provider` (`none` | `ollama` | `openai_compatible`)
- `translator_base_url` (optional)
- `translator_model` (optional)
- `translator_api_key` (optional)
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
