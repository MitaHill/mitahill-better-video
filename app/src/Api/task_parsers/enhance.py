from app.src.Config import settings as config
from app.src.Utils.ffmpeg import normalize_output_codec

from .common import bool_from_form, int_from_form, float_from_form, merge_unparsed_form_fields


def parse_enhance_task_params(form):
    parsed = {
        "task_category": "enhance",
        "input_type": form.get("input_type", "Video"),
        "model_name": form.get("model_name", "realesrgan-x4plus"),
        "upscale": int_from_form(form, "upscale", 3),
        "tile": int_from_form(form, "tile", config.DEFAULT_SMART_TILE_SIZE),
        "denoise_strength": float_from_form(form, "denoise_strength", 0.5),
        "keep_audio": True,
        "crf": int_from_form(form, "crf", 18),
        "output_codec": normalize_output_codec(form.get("output_codec", "h264")),
        "tile_pad": int_from_form(form, "tile_pad", config.DEFAULT_TILE_PADDING),
        "fp16": bool_from_form(form, "fp16", config.DEFAULT_FP16),
    }
    merged = merge_unparsed_form_fields(form, parsed)
    for key in (
        "audio_enhance",
        "pre_denoise_mode",
        "haas_enabled",
        "haas_delay_ms",
        "haas_lead",
        "deinterlace",
    ):
        merged.pop(key, None)
    return merged
