# API Contract

任务接口使用普通 HTTP 上传、查询和下载，可接入 n8n。当前不要求 API Key；管理接口仍需管理员登录。新增 URL 字段均为相对路径，调用方需与服务地址拼接。

任务 ID 是字符串（当前为四位数字，如 `"0123"`），不是 UUID；请保留前导零，并将其作为不透明标识使用。

## POST /api/tasks

创建一个增强任务。**Content-Type**：`multipart/form-data`。

| 字段 | 默认值 / 说明 |
| --- | --- |
| `file` | 必填，单个视频或图片 |
| `input_type` | `Video`，也可为 `Image` |
| `model_name` | `realesrgan-x4plus` |
| `upscale` | 启动时根据显存确定，可从 `/api/config/recommendations` 查询 |
| `tile` | 启动时根据显存确定，可从 `/api/config/recommendations` 查询 |
| `denoise_strength` | `0.5` |
| `crf` | `18` |
| `output_codec` | `h264`；可用值见 `/api/config/recommendations` 的 `enhance_output_codecs` |
| `tile_pad` | 服务端 `DEFAULT_TILE_PADDING`，未配置时为 `10` |
| `fp16` | 服务端 `DEFAULT_FP16`，未配置时为 `true` |

成功返回 **201**：

```json
{ "task_id": "0123", "status_url": "/api/tasks/0123" }
```

缺少文件、文件名不合法或媒体被拒绝时返回 **400** 和 `error`。部分拒绝发生在创建记录之后，此时还会返回 `task_id`，对应任务为 `FAILED`。

## POST /api/tasks/batch

**Content-Type**：`multipart/form-data`。`files` 为多个上传文件（也兼容 `file`），其余增强参数与单任务相同。

成功返回 **201**，可能包含部分失败：

```json
{
  "batch_id": "9500",
  "task_ids": ["0123", "0124"],
  "errors": [{ "filename": "bad.mp4", "error": "...", "task_id": "0124" }]
}
```

批次状态和结果分别使用 `GET /api/batches/<batch_id>`、`GET /api/batches/<batch_id>/result`。

## POST /api/chains

**Content-Type**：`multipart/form-data`。已有任务链接口保留，前端入口暂时隐藏，详见 [任务链设计](TASK_CHAIN.md)。外部工作流首版使用单任务接口，不依赖任务链。

- `file`：必填，整条链的一个输入文件。
- `steps`：必填，JSON 数组，每项为 `{"category": "enhance|convert|transcribe", "params": {...}}`；后续输入由后端使用上一步结果填充。
- 最多五步；`transcribe` 只能是最后一步；非最后一步的 `convert` 只允许 `convert_mode=transcode`。`convert` 是保留的内部链步骤，独立转换提交接口已移除。

成功返回 **201**：

```json
{ "chain_id": "9500", "task_ids": ["0123", "0124"] }
```

通过批次接口查询和下载，整条取消使用 `POST /api/admin/batches/<chain_id>/cancel`。

## GET /api/tasks/<task_id>

成功返回 **200**，保留原有任务字段，包括：

- `task_id`、`task_category`、`status`、`progress`（0–100）、`message`。
- `task_params`、`video_info`、`task_progress`、`segment_progress`、`gpu_live`。
- `created_at`、`updated_at` 为带 UTC 时区的时间字符串。
- `result_available`：仅 `COMPLETED` 且能找到结果文件时为 `true`。
- `result_url`：结果可用时为相对下载路径，否则为 `null`。不要使用返回中的服务端文件路径下载文件。

任务参数中的 `translator_api_key` 会被遮盖。

```json
{
  "task_id": "0123",
  "status": "COMPLETED",
  "progress": 100,
  "result_available": true,
  "result_url": "/api/tasks/0123/result"
}
```

以上为响应节选。状态含义：

| 状态 | 客户端行为 |
| --- | --- |
| `PENDING` / `PROCESSING` / `WAITING` | 继续等待；`WAITING` 用于尚未轮到的内部链步骤 |
| `FAILED` | 停止，读取 `message`；管理员取消也使用此状态 |
| `COMPLETED` | 检查 `result_available`，为真时下载；为假时作为文件缺失处理 |

任务不存在返回 **404**，`error_code=task_not_found`。轮询不要通过重复提交任务来实现。

## GET /api/tasks/<task_id>/preview/original

原始预览，存在时返回 JPEG。

## GET /api/tasks/<task_id>/preview/upscaled

增强预览，存在时返回 JPEG。

## GET /api/tasks/<task_id>/result

成功返回 **200** 和结果文件，`Content-Disposition: attachment` 携带文件名。增强视频通常为视频文件，转录 `subtitle_zip` 为 ZIP；客户端应保存实际二进制响应。

失败均返回 **404** 和 JSON：

| `error_code` | 含义 |
| --- | --- |
| `task_not_found` | 无对应任务 |
| `result_not_ready` | 任务不是 `COMPLETED`；响应同时包含当前 `status`，包括失败状态 |
| `result_missing` | 任务已完成，但结果文件缺失 |

示例：`{"error":"result not available","error_code":"result_not_ready","status":"PROCESSING"}`。

查询时可用的文件仍可能在下载前被管理员删除；下载请求失败应进入错误分支。

## GET /api/health

示例：`{"status":"ok","db":"ok","worker":"running"}`。部署验收需同时确认应用、数据库和 Worker 状态。

## GET /api/config/recommendations

返回运行建议。增强编码器来自 FFmpeg 编码器清单及当前 GPU 的实际探测：

```json
{
  "gpu_name": "NVIDIA GeForce GTX 960",
  "vram_gb": 3.94,
  "tile_size": 256,
  "upscale": 2,
  "enhance_output_codecs": ["h264", "h265"]
}
```

## POST /api/transcriptions

创建转录任务。**Content-Type**：`multipart/form-data`。

| 字段 | 默认值 / 说明 |
| --- | --- |
| `media_files` | 必填，可多个；也兼容 `files` / `file`，最小工作流每次用 `file` 上传一个文件 |
| `transcription_backend` | `whisper`，也可为 `elevenlabs`（需服务端已配置密钥） |
| `transcribe_mode` | `subtitle_zip`；也可为 `subtitled_video` / `subtitle_and_video_zip` |
| `subtitle_format` | `srt`，也可为 `vtt` |
| `whisper_model` | 管理员配置的活动模型，未配置时为 `large-v3`；必须已安装 |
| `language` | `auto` |
| `translate_to` | 空，即不翻译；填写目标语言时使用服务端翻译配置 |
| `translator_fallback_mode` | 服务端配置，未配置时为 `model_full_text`；也可为 `source_text` |
| `max_line_chars` | `42` |
| `temperature` / `beam_size` / `best_of` | 分别为 `0.0` / `5` / `5` |

翻译提供器、地址、模型、密钥和提示词由管理员在服务端配置。上传请求中的 `translator_provider`、`translator_base_url`、`translator_model`、`translator_api_key` 不用于覆盖这些配置。启用翻译但配置不完整时返回 **400**。

单文件成功返回 **201**：

```json
{ "task_id": "0124", "task_ids": ["0124"], "status_url": "/api/tasks/0124" }
```

多文件为每个文件创建一个任务，响应保留 `task_id`（首个任务）、`task_ids`、`batch_id` 及可能的 `errors`，不增加单任务 `status_url`；用批次接口查询，注意部分失败。参数校验失败、模型未安装或全部上传失败时返回 **400** 和 `error`。

### GET /api/transcriptions/runtime-config

公开转录配置，包含 `transcription.active_model`、`installed_models`、`elevenlabs_configured` 和翻译可用性，不返回密钥。可先查询已安装模型，再提交任务。

## 外部工作流：curl 与 n8n

最小闭环为：增强 → 等待 → 下载视频 → 上传转录 → 等待 → 下载字幕 ZIP。普通视频传输经过调用方；第一版不接受上游任务引用或本地路径。

### curl 示例

以下使用 Bash、curl 和 jq；将服务地址和文件路径替换为实际值。增强示例显式使用二倍放大和 H.264；转录模型使用运行配置中的活动模型（需要已安装）。

```bash
set -euo pipefail
BASE_URL='http://192.168.9.4:8501'

# 提交只执行一次；不要配置自动重试，以免响应丢失后重复创建任务。
enhance=$(curl --fail-with-body -sS "$BASE_URL/api/tasks" \
  -F 'file=@input.mp4' -F 'input_type=Video' -F 'upscale=2' -F 'output_codec=h264')
enhance_id=$(jq -er '.task_id' <<< "$enhance")
enhance_status=$(jq -er '.status_url' <<< "$enhance")

wait_result() {
  local status_path="$1" deadline=$((SECONDS + 86400)) state status
  while (( SECONDS < deadline )); do
    sleep 10
    state=$(curl --fail-with-body -sS --max-time 30 "$BASE_URL$status_path") || return 1
    status=$(jq -er '.status' <<< "$state") || return 1
    case "$status" in
      PENDING|PROCESSING|WAITING) ;;
      FAILED) jq -r '.message' <<< "$state" >&2; return 1 ;;
      COMPLETED)
        if jq -e '.result_available == true' <<< "$state" >/dev/null; then
          jq -er '.result_url' <<< "$state"
          return
        fi
        echo "任务已完成但结果文件缺失：$status_path" >&2; return 1 ;;
      *) echo "未知状态：$status" >&2; return 1 ;;
    esac
  done
  echo "等待超过 24 小时，保留任务供后续查询：$status_path" >&2
  return 1
}

enhance_result=$(wait_result "$enhance_status") || exit 1
curl --fail-with-body -sS "$BASE_URL$enhance_result" -o enhanced.mp4 || exit 1

model=$(curl --fail-with-body -sS "$BASE_URL/api/transcriptions/runtime-config" | jq -er '.transcription.active_model')
transcribe=$(curl --fail-with-body -sS "$BASE_URL/api/transcriptions" \
  -F 'file=@enhanced.mp4' -F "whisper_model=$model" \
  -F 'transcribe_mode=subtitle_zip' -F 'subtitle_format=srt')
transcribe_id=$(jq -er '.task_id' <<< "$transcribe")
transcribe_status=$(jq -er '.status_url' <<< "$transcribe")
transcribe_result=$(wait_result "$transcribe_status") || exit 1
curl --fail-with-body -sS "$BASE_URL$transcribe_result" -o subtitles.zip
```

脚本中 `enhance_id`、`transcribe_id` 可用于超时后的查询或管理。24 小时是每个任务的客户端等待上限，不会取消服务端任务。下载失败时停止，不继续提交下一步。

### n8n 节点配置

1. 准备服务地址和输入二进制文件，例如字段名 `data`。HTTP Request 使用 `POST /api/tasks`，Body Content Type 选择 **Form-Data**，添加 **n8n Binary File** 参数：Name 为 `file`，Input Data Field Name 为 `data`；另加 `input_type=Video`、`upscale=2`、`output_codec=h264` 的 Form Data 参数。关闭 **Retry On Fail**。
2. 用 Edit Fields 保存 `task_id`、`status_url`、服务地址以及本次任务的 `deadline = Date.now() + 86400000`。将轮询所需字段与响应分开保留，避免 HTTP 响应覆盖任务 ID 或在每次循环时重置 deadline。
3. Wait 配置 **After Time Interval / 10 Seconds**。等待后先比较当前时间与 deadline，超时进入错误分支并保留任务 ID；否则 HTTP Request 对服务地址加 `status_url` 发起 GET，返回 JSON。
4. Switch 根据 `status` 分支：`PENDING` / `PROCESSING` / `WAITING` 回到 Wait；`FAILED` 用 `message` 终止；`COMPLETED` 检查 `result_available`，为假时按结果缺失终止；未知状态或非 2xx 响应也进入错误分支。
5. 结果可用时对服务地址加 `result_url` 发起 GET，Response Format 选 **File**，输出二进制字段设为 `data`。与下一步上传之间不要丢弃该二进制字段。
6. 另一个 HTTP Request 向 `/api/transcriptions` 上传 `file=data`，并设置 `transcribe_mode=subtitle_zip`、`subtitle_format=srt`；模型可使用已安装的活动模型。保存新的任务 ID、状态 URL 和 deadline，复用上述轮询逻辑，最终以 File 格式下载并保存 ZIP。

GET 查询、下载请求均设置合理的单次请求超时（示例为 30 秒的状态查询）；提交请求的超时应能覆盖实际文件上传。失败和超时分支停止执行，不自动重新提交或取消任务。无需 Socket.IO、Webhook 或专用节点。

大视频会经过 n8n 的二进制存储；按 n8n 部署模式配置文件存储，避免默认内存模式承载大文件。官方说明：[HTTP Request](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.httprequest/)、[Wait](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.wait/)、[二进制数据存储](https://docs.n8n.io/hosting/scaling/binary-data/)。

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

### POST /api/admin/batches/<batch_id>/cancel
Header:
- `Authorization: Bearer <token>`

取消批次下仍在排队或处理中的子任务。
- `PENDING`/`PROCESSING` 子任务：置为 `FAILED`，消息为“已取消（管理员操作）”
- 已结束子任务保持原状态

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

读取转录、ElevenLabs 和翻译配置。`elevenlabs.api_key` 不会返回，仅提供 `api_key_configured`。

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
    "allowed_models": ["tiny.en", "tiny", "base.en", "base", "small.en", "small", "medium.en", "medium", "large-v1", "large-v2", "large-v3"]
  },
  "translation": {
    "provider": "openai_compatible",
    "base_url": "http://127.0.0.1:8000/v1",
    "model": "qwen2.5:7b"
  },
  "elevenlabs": {
    "api_key": "xi-..."
  }
}
```

ElevenLabs 密钥为空时保留现有值；传入 `clear_api_key: true` 时清除密钥。

### POST /api/admin/debug/test-elevenlabs
Header:
- `Authorization: Bearer <token>`

使用服务端保存的 API Key 查询 ElevenLabs 用户信息，不提交音频、不产生转录任务。

若 Key 为受限权限（未授予 `user_read`），用户信息接口会返回 401 `missing_permissions`。此时改为向转录接口发送一次不带文件的探测请求：只要鉴权通过（非 401/403）即判定连接正常，返回的 `tier` 与 `status` 为 `unknown`。探测请求不携带音频，也不会产生转录任务。

### GET /api/admin/transcription/models
Header:
- `Authorization: Bearer <token>`

返回所有标准 Faster-Whisper 模型目录，以及本地安装状态。

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
2. 必要文件检查
3. GPU 热身（5秒静音音频识别）

Request (optional):
```json
{
  "mode": "files",
  "backend": "whisper",
  "model_id": "large-v3"
}
```
- `mode=files`：执行到必要文件检查即返回
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

读取数据库中的系统日志（默认 INFO+）。

Query:
- `min_level` (`INFO` | `WARNING` | `ERROR` | `CRITICAL`)
- `logger` (optional)
- `q` (optional keyword)
- `limit` (optional)
- `offset` (optional)
