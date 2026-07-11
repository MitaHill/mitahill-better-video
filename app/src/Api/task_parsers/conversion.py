from .common import (
    bool_from_form,
    float_from_form,
    int_from_form,
    merge_unparsed_form_fields,
    parse_watermark_timeline,
)


def parse_conversion_task_params(form):
    parsed = {
        "task_category": "convert",
        "convert_mode": (form.get("convert_mode", "transcode") or "transcode").lower(),
        "output_format": (form.get("output_format", "mp4") or "mp4").lower(),
        "video_codec": (form.get("video_codec", "h264") or "h264").lower(),
        "frame_rate": int_from_form(form, "frame_rate", 0),
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
    merged = merge_unparsed_form_fields(form, parsed)
    for key in (
        "audio_source_mode",
        "audio_channels_mode",
        "audio_sample_rate",
        "audio_bitrate_k",
        "mute_audio",
        "audio_fade_in_sec",
        "audio_fade_out_sec",
        "audio_echo",
        "audio_echo_delay_ms",
        "audio_echo_decay",
        "audio_denoise",
        "audio_reverse",
        "audio_volume",
        "haas_enabled",
        "haas_delay_ms",
        "haas_lead",
    ):
        merged.pop(key, None)
    return merged
