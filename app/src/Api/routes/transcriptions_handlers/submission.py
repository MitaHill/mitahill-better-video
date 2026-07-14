from app.src.Config import settings as config
from app.src.Database import core as db

from ...constants import OUTPUT_ROOT, UPLOAD_ROOT
from ...services import create_transcription_tasks
from .params import apply_transcription_form_params, validate_translation_provider_guard


def submit_transcription_request(req, client_ip):
    params, err = apply_transcription_form_params(req.form)
    if err:
        return {"error": err}, 400

    provider_guard_error = validate_translation_provider_guard(params)
    if provider_guard_error:
        return {"error": provider_guard_error}, 400

    batch_id, task_ids, errors = create_transcription_tasks(
        req,
        client_ip,
        params,
        OUTPUT_ROOT,
        UPLOAD_ROOT,
        config.MAX_VIDEO_SIZE_MB,
    )
    if errors:
        for item in errors:
            if item.get("task_id"):
                db.update_task_status(item["task_id"], "FAILED", progress=0, message=item.get("error"))
        if not task_ids:
            return {"error": errors[0].get("error") or "提交转录任务失败", "errors": errors}, 400

    payload = {"task_id": task_ids[0], "task_ids": task_ids}
    if batch_id:
        payload["batch_id"] = batch_id
    if errors:
        payload["errors"] = errors
    return payload, 201
