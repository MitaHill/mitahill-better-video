from app.src.Config import settings as config
from app.src.Database import core as db

from ...constants import OUTPUT_ROOT, UPLOAD_ROOT
from ...services import create_transcription_task
from .params import apply_transcription_form_params, validate_translation_provider_guard


def submit_transcription_request(req, client_ip):
    params, err = apply_transcription_form_params(req.form)
    if err:
        return {"error": err}, 400

    provider_guard_error = validate_translation_provider_guard(params)
    if provider_guard_error:
        return {"error": provider_guard_error}, 400

    task_id, create_error = create_transcription_task(
        req,
        client_ip,
        params,
        OUTPUT_ROOT,
        UPLOAD_ROOT,
        config.MAX_VIDEO_SIZE_MB,
    )
    if create_error:
        if task_id:
            db.update_task_status(task_id, "FAILED", progress=0, message=create_error)
        return {"error": create_error, "task_id": task_id}, 400

    return {"task_id": task_id}, 201
