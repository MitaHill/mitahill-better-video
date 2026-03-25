import json
import zipfile
from pathlib import Path

from app.src.Config import settings as config
from app.src.Utils.ffmpeg import run_ffmpeg
from app.src.Utils.http import ffprobe_info

from .formatting import segments_to_srt, segments_to_text, segments_to_vtt


def extract_transcribe_audio(input_path, run_dir):
    info = ffprobe_info(input_path)
    if not info.get("has_video"):
        return input_path, info, False

    audio_path = run_dir / f"{input_path.stem}_asr.wav"
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(audio_path),
        ]
    )
    return audio_path, info, True


def write_subtitle_file(path, segments, subtitle_format="srt", max_line_chars=42):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = (subtitle_format or "srt").strip().lower()
    if fmt == "vtt":
        file_path.write_text(segments_to_vtt(segments, max_line_chars=max_line_chars), encoding="utf-8")
    else:
        file_path.write_text(segments_to_srt(segments, max_line_chars=max_line_chars), encoding="utf-8")
    return file_path


def write_text_file(path, segments, prepend_timestamps=False):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        segments_to_text(segments, prepend_timestamps=prepend_timestamps),
        encoding="utf-8",
    )
    return file_path


def write_json_file(path, payload):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return file_path


def _subtitle_filter_arg(subtitle_path):
    escaped = str(subtitle_path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    force_style = "FontName=Noto Sans CJK SC"
    return f"subtitles='{escaped}':force_style='{force_style}'"


def render_subtitled_video(video_path, subtitle_path, output_path, codec_key, audio_bitrate_k):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gpu_codec = "h264_nvenc"
    cpu_codec = "libx264"
    if (codec_key or "").lower() in {"h265", "hevc"}:
        gpu_codec = "hevc_nvenc"
        cpu_codec = "libx265"
    video_codec = gpu_codec if config.FFMPEG_USE_GPU else cpu_codec
    base_cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        _subtitle_filter_arg(subtitle_path),
        "-c:v",
        video_codec,
        "-c:a",
        "aac",
        "-b:a",
        f"{max(32, int(audio_bitrate_k or 192))}k",
        str(output_path),
    ]
    fallback_cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        _subtitle_filter_arg(subtitle_path),
        "-c:v",
        cpu_codec,
        "-c:a",
        "aac",
        "-b:a",
        f"{max(32, int(audio_bitrate_k or 192))}k",
        str(output_path),
    ]
    run_ffmpeg(base_cmd, fallback_args=fallback_cmd)
    return output_path


def zip_outputs(paths, destination, base_dir=None, root_prefix=""):
    destination.parent.mkdir(parents=True, exist_ok=True)
    arcname_counts = {}
    base_path = Path(base_dir).resolve() if base_dir else None
    safe_prefix = str(root_prefix or "").strip().strip("/")
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in paths:
            file_path = Path(path)
            if not file_path.exists() or not file_path.is_file():
                continue
            if base_path:
                try:
                    arcname = str(file_path.resolve().relative_to(base_path)).replace("\\", "/")
                except Exception:
                    arcname = file_path.name
            else:
                arcname = file_path.name
            if safe_prefix:
                arcname = f"{safe_prefix}/{arcname}".replace("//", "/")
            count = arcname_counts.get(arcname, 0)
            if count > 0:
                arc_path = Path(arcname)
                stem = arc_path.stem
                suffix = arc_path.suffix
                arcname = str(arc_path.parent / f"{stem}_{count}{suffix}").replace("\\", "/")
            arcname_counts[arcname] = count + 1
            zf.write(file_path, arcname=arcname)
    return destination
