import json

from app.src.Config import settings as config


def bool_from_form(form, key, default=False):
    value = form.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def int_from_form(form, key, default=0):
    value = form.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def float_from_form(form, key, default=0.0):
    value = form.get(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def parse_watermark_timeline(raw):
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    out = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "label": str(item.get("label", "")).strip(),
                "enabled": bool(item.get("enabled", True)),
                "source_type": str(item.get("source_type", "text")).strip().lower(),
                "text": str(item.get("text", "")),
                "image_index": int(item.get("image_index", 0) or 0),
                "start_sec": float(item.get("start_sec", 0.0) or 0.0),
                "end_sec": float(item.get("end_sec", 0.0) or 0.0),
                "position": str(item.get("position", "bottom_right")).strip().lower(),
                "x_expr": str(item.get("x_expr", "")).strip(),
                "y_expr": str(item.get("y_expr", "")).strip(),
                "rotation_deg": float(item.get("rotation_deg", 0.0) or 0.0),
                "alpha": float(item.get("alpha", 0.45) or 0.45),
                "animation": str(item.get("animation", "none")).strip().lower(),
                "font_size": int(item.get("font_size", 26) or 26),
                "font_color": str(item.get("font_color", "white")).strip(),
            }
        )
    return out


def merge_unparsed_form_fields(form, parsed):
    """Keep unknown form fields so task params are extensible without parser rewrites."""
    for key in form.keys():
        if key in parsed:
            continue
        values = form.getlist(key)
        parsed[key] = values if len(values) > 1 else form.get(key)
    return parsed


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


def parse_conversion_task_params(form):
    parsed = {
        "task_category": "convert",
        "convert_mode": (form.get("convert_mode", "transcode") or "transcode").lower(),
        "output_format": (form.get("output_format", "mp4") or "mp4").lower(),
        "video_codec": (form.get("video_codec", "h264") or "h264").lower(),
        "frame_rate": int_from_form(form, "frame_rate", 0),
        "audio_source_mode": (form.get("audio_source_mode", "keep_original") or "keep_original").lower(),
        "audio_channels_mode": (form.get("audio_channels_mode", "keep") or "keep").lower(),
        "haas_enabled": bool_from_form(form, "haas_enabled", False),
        "haas_delay_ms": int_from_form(form, "haas_delay_ms", 0),
        "haas_lead": (form.get("haas_lead", "left") or "left").lower(),
        "aspect_ratio": (form.get("aspect_ratio", "") or "").strip(),
        "second_pass_reencode": bool_from_form(form, "second_pass_reencode", False),
        "deinterlace": bool_from_form(form, "deinterlace", False),
        "flip_horizontal": bool_from_form(form, "flip_horizontal", False),
        "flip_vertical": bool_from_form(form, "flip_vertical", False),
        "video_fade_in_sec": float_from_form(form, "video_fade_in_sec", 0.0),
        "video_fade_out_sec": float_from_form(form, "video_fade_out_sec", 0.0),
        "crf": int_from_form(form, "crf", 18),
        "video_bitrate_k": int_from_form(form, "video_bitrate_k", 0),
        "target_size_mb": float_from_form(form, "target_size_mb", 0.0),
        "target_width": int_from_form(form, "target_width", 0),
        "target_height": int_from_form(form, "target_height", 0),
        "audio_sample_rate": int_from_form(form, "audio_sample_rate", 0),
        "audio_bitrate_k": int_from_form(form, "audio_bitrate_k", 192),
        "mute_audio": bool_from_form(form, "mute_audio", False),
        "audio_fade_in_sec": float_from_form(form, "audio_fade_in_sec", 0.0),
        "audio_fade_out_sec": float_from_form(form, "audio_fade_out_sec", 0.0),
        "audio_echo": bool_from_form(form, "audio_echo", False),
        "audio_echo_delay_ms": int_from_form(form, "audio_echo_delay_ms", 200),
        "audio_echo_decay": float_from_form(form, "audio_echo_decay", 0.4),
        "audio_denoise": bool_from_form(form, "audio_denoise", False),
        "audio_reverse": bool_from_form(form, "audio_reverse", False),
        "audio_volume": float_from_form(form, "audio_volume", 1.0),
        "meta_title": form.get("meta_title", ""),
        "meta_author": form.get("meta_author", ""),
        "meta_comment": form.get("meta_comment", ""),
        "watermark_enable_text": bool_from_form(form, "watermark_enable_text", False),
        "watermark_enable_image": bool_from_form(form, "watermark_enable_image", False),
        "watermark_default_text": form.get("watermark_default_text", ""),
        "watermark_alpha": float_from_form(form, "watermark_alpha", 0.45),
        "watermark_timeline": parse_watermark_timeline(form.get("watermark_timeline")),
        "watermark_yaml_config": form.get("watermark_yaml_config", ""),
        "watermark_lua_script": form.get("watermark_lua_script", ""),
        "frame_export_fps": int_from_form(form, "frame_export_fps", 0),
        "frame_export_fps_mode": (form.get("frame_export_fps_mode", "manual") or "manual").lower(),
        "frame_export_format": (form.get("frame_export_format", "jpg") or "jpg").lower(),
    }
    return merge_unparsed_form_fields(form, parsed)


def parse_transcription_task_params(form):
    parsed = {
        "task_category": "transcribe",
        "transcribe_mode": (form.get("transcribe_mode", "subtitle_zip") or "subtitle_zip").lower(),
        "subtitle_format": (form.get("subtitle_format", "srt") or "srt").lower(),
        "whisper_model": (form.get("whisper_model", "medium") or "medium").lower(),
        "language": (form.get("language", "auto") or "auto").strip(),
        "translate_to": (form.get("translate_to", "") or "").strip(),
        "prepend_timestamps": bool_from_form(form, "prepend_timestamps", False),
        "max_line_chars": int_from_form(form, "max_line_chars", 42),
        "temperature": float_from_form(form, "temperature", 0.0),
        "beam_size": int_from_form(form, "beam_size", 5),
        "best_of": int_from_form(form, "best_of", 5),
        "output_video_codec": (form.get("output_video_codec", "h264") or "h264").lower(),
        "output_audio_bitrate_k": int_from_form(form, "output_audio_bitrate_k", 192),
    }
    return merge_unparsed_form_fields(form, parsed)
