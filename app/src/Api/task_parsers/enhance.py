from app.src.Config import settings as config

from .common import bool_from_form, int_from_form, float_from_form, merge_unparsed_form_fields


def parse_enhance_task_params(form):
    parsed = {
        "task_category": "enhance",
        "input_type": form.get("input_type", "Video"),
        "model_name": form.get("model_name", "realesrgan-x4plus"),
        "upscale": int_from_form(form, "upscale", 3),
        "tile": int_from_form(form, "tile", config.DEFAULT_SMART_TILE_SIZE),
        "denoise_strength": float_from_form(form, "denoise_strength", 0.5),
        "keep_audio": bool_from_form(form, "keep_audio", True),
        "audio_enhance": bool_from_form(form, "audio_enhance", config.ENABLE_AUDIO_ENHANCEMENT),
        "pre_denoise_mode": form.get("pre_denoise_mode", config.PRE_DENOISE_MODE),
        "haas_enabled": bool_from_form(form, "haas_enabled", False),
        "haas_delay_ms": int_from_form(form, "haas_delay_ms", 0),
        "haas_lead": form.get("haas_lead", "left"),
        "crf": int_from_form(form, "crf", 18),
        "output_codec": form.get("output_codec", "h264").lower(),
        "deinterlace": bool_from_form(form, "deinterlace", False),
        "tile_pad": int_from_form(form, "tile_pad", config.DEFAULT_TILE_PADDING),
        "fp16": bool_from_form(form, "fp16", config.DEFAULT_FP16),
    }
    return merge_unparsed_form_fields(form, parsed)
