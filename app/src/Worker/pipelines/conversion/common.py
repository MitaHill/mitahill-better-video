import re

GPU_CODEC_MAP = {
    "h264": ("h264_nvenc", "libx264"),
    "h265": ("hevc_nvenc", "libx265"),
    "hevc": ("hevc_nvenc", "libx265"),
}
VALID_FORMATS = {"mp4", "mkv", "mov", "avi"}
VALID_AUDIO_MODES = {"keep_original", "replace_uploaded", "mix_uploaded"}
VALID_WATERMARK_POSITIONS = {
    "top_left",
    "top_right",
    "bottom_left",
    "bottom_right",
    "center",
    "custom",
}
VALID_WATERMARK_ANIMATIONS = {"none", "swing", "dvd_bounce"}


def to_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def to_int(value, default=0, min_value=None, max_value=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def to_float(value, default=0.0, min_value=None, max_value=None):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def parse_ffmpeg_time(line):
    match = re.search(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", line)
    if not match:
        return None
    hh, mm, ss = match.groups()
    return int(hh) * 3600 + int(mm) * 60 + float(ss)
