from ...parsers import parse_transcription_task_params
from ...services.admin.transcription_catalog import build_whisper_model_entry
from ...services.admin.transcription_config import get_elevenlabs_api_key


VALID_TRANSCRIPTION_BACKENDS = {"whisper", "elevenlabs"}


def apply_transcription_form_params(form):
    backend = str(form.get("transcription_backend") or "whisper").strip().lower()
    if backend not in VALID_TRANSCRIPTION_BACKENDS:
        return None, f"不支持的转录引擎: {backend}"
    return parse_transcription_task_params(form), None


def validate_transcription_backend_guard(params):
    backend = str(params.get("transcription_backend") or "whisper").strip().lower()
    if backend == "elevenlabs":
        if not get_elevenlabs_api_key():
            return "ElevenLabs API Key 尚未配置，请先在管理中心完成配置。"
        return None

    model_id = str(params.get("whisper_model") or "").strip().lower()
    model = build_whisper_model_entry(model_id)
    if not model:
        return f"不支持的 Whisper 模型: {model_id}"
    if not model.get("installed"):
        return f"Whisper 模型尚未安装: {model_id}"
    return None


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
