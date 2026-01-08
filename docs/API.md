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
- `crf`
- `tile_pad`
- `fp16`

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

## GET /api/tasks/<task_id>/preview/original
Returns JPEG preview if available.

## GET /api/tasks/<task_id>/preview/upscaled
Returns JPEG preview if available.

## GET /api/tasks/<task_id>/result
Returns output file if task is completed.

## GET /api/health
Returns `{"status":"ok"}` when backend is alive.
