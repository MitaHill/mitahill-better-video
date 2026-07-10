from ...parsers import parse_transcription_task_params


def apply_transcription_form_params(form):
    return parse_transcription_task_params(form), None


def validate_translation_provider_guard(params):
    translate_to = str(params.get("translate_to") or "").strip()
    provider = str(params.get("translator_provider") or "none").strip().lower()
    if translate_to and provider == "none":
        return "已设置“翻译到”，但管理员尚未在后端管理页面配置可用翻译提供器。"
    if not translate_to:
        return None
    model = str(params.get("translator_model") or "").strip()
    base_url = str(params.get("translator_base_url") or "").strip()
    if provider != "openai_compatible":
        return "当前仅支持 OpenAI 兼容格式的翻译提供器。"
    if not model:
        return "已启用翻译，但未配置翻译模型名。"
    if not base_url:
        return "已启用翻译，但未配置 OpenAI 兼容服务地址。"
    return None
