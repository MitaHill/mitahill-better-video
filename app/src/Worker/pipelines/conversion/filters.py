from app.src.Config import settings as config

from .common import to_bool, to_float, to_int


def build_video_filters(options, duration_seconds):
    vf = []
    if to_bool(options.get("deinterlace"), False):
        vf.append("yadif_cuda=mode=send_frame:parity=auto:deint=all" if config.FFMPEG_USE_GPU else "yadif")
    if to_bool(options.get("flip_horizontal"), False):
        vf.append("hflip")
    if to_bool(options.get("flip_vertical"), False):
        vf.append("vflip")

    width = to_int(options.get("target_width"), 0, min_value=0)
    height = to_int(options.get("target_height"), 0, min_value=0)
    if width > 0 and height > 0:
        vf.append(
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
        )

    aspect_ratio = (options.get("aspect_ratio") or "").strip()
    if aspect_ratio:
        vf.append(f"setdar={aspect_ratio}")

    fade_in = to_float(options.get("video_fade_in_sec"), 0.0, min_value=0.0, max_value=30.0)
    fade_out = to_float(options.get("video_fade_out_sec"), 0.0, min_value=0.0, max_value=30.0)
    if fade_in > 0:
        vf.append(f"fade=t=in:st=0:d={fade_in:.3f}")
    if fade_out > 0 and duration_seconds > 0:
        start = max(0.0, duration_seconds - fade_out)
        vf.append(f"fade=t=out:st={start:.3f}:d={fade_out:.3f}")

    return ",".join(vf) if vf else None


def build_audio_filter(options):
    af = []
    fade_in = to_float(options.get("audio_fade_in_sec"), 0.0, min_value=0.0, max_value=30.0)
    fade_out = to_float(options.get("audio_fade_out_sec"), 0.0, min_value=0.0, max_value=30.0)
    duration = to_float(options.get("_duration"), 0.0, min_value=0.0)
    if fade_in > 0:
        af.append(f"afade=t=in:st=0:d={fade_in:.3f}")
    if fade_out > 0 and duration > 0:
        start = max(0.0, duration - fade_out)
        af.append(f"afade=t=out:st={start:.3f}:d={fade_out:.3f}")

    if to_bool(options.get("audio_echo"), False):
        echo_delay = to_int(options.get("audio_echo_delay_ms"), 200, min_value=1, max_value=3000)
        echo_decay = to_float(options.get("audio_echo_decay"), 0.4, min_value=0.0, max_value=1.0)
        af.append(f"aecho=0.8:0.9:{echo_delay}:{echo_decay:.2f}")
    if to_bool(options.get("audio_denoise"), False):
        af.append("afftdn")
    if to_bool(options.get("audio_reverse"), False):
        af.append("areverse")

    volume = to_float(options.get("audio_volume"), 1.0, min_value=0.0, max_value=5.0)
    if abs(volume - 1.0) > 1e-3:
        af.append(f"volume={volume:.3f}")

    return ",".join(af) if af else None
