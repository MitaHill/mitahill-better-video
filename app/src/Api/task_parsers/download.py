from .common import bool_from_form, float_from_form, get_list_field, int_from_form, merge_unparsed_form_fields


def _extract_subtitle_languages(form):
    subtitle_languages = get_list_field(form, "subtitle_languages")
    if subtitle_languages:
        return subtitle_languages
    raw_langs = (form.get("subtitle_languages") or "").strip()
    if not raw_langs:
        return []
    return [item.strip() for item in raw_langs.split(",") if item.strip()]


def parse_download_task_params(form):
    parsed = {
        "task_category": "download",
        "source_url": (form.get("source_url", "") or "").strip(),
        "source_title": (form.get("source_title", "") or "").strip(),
        "source_duration_sec": int_from_form(form, "source_duration_sec", 0),
        "source_width": int_from_form(form, "source_width", 0),
        "source_height": int_from_form(form, "source_height", 0),
        "source_fps": float_from_form(form, "source_fps", 0.0),
        "source_size_mb": float_from_form(form, "source_size_mb", 0.0),
        "download_mode": (form.get("download_mode", "video") or "video").strip().lower(),
        "quality_selector": (
            form.get("quality_selector", "bestvideo*+bestaudio/best") or "bestvideo*+bestaudio/best"
        ).strip(),
        "video_output_format": (form.get("video_output_format", "mp4") or "mp4").strip().lower(),
        "audio_output_format": (form.get("audio_output_format", "mp3") or "mp3").strip().lower(),
        "subtitle_output_format": (form.get("subtitle_output_format", "srt") or "srt").strip().lower(),
        "subtitle_include_auto": bool_from_form(form, "subtitle_include_auto", True),
        "subtitle_languages": _extract_subtitle_languages(form),
    }
    return merge_unparsed_form_fields(form, parsed)
