from ...parsers import parse_transcription_task_params
from ...services.form_constraints import apply_constraints_to_params


def apply_transcription_form_params(form):
    params = parse_transcription_task_params(form)
    return apply_constraints_to_params("transcribe", params)


def validate_translation_provider_guard(params):
    translate_to = str(params.get("translate_to") or "").strip()
    provider = str(params.get("translator_provider") or "none").strip().lower()
    if translate_to and provider == "none":
        return "已设置“翻译到”，但管理员尚未在后端管理页面配置可用翻译提供器。"
    return None
