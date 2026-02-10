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

## GET /api/tasks/<task_id>
Response includes:
- `status` (PENDING/PROCESSING/COMPLETED/FAILED)
- `progress` (0-100)
- `message`
- `task_params`
- `video_info`

## GET /api/tasks/<task_id>/preview/original
Returns JPEG preview if available.

## GET /api/tasks/<task_id>/preview/upscaled
Returns JPEG preview if available.

## GET /api/tasks/<task_id>/result
Returns output file if task is completed.

## GET /api/health
Returns `{"status":"ok"}` when backend is alive.

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
