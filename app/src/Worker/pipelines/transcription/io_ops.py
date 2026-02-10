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


def write_transcript_files(
    output_dir,
    stem,
    segments,
    *,
    subtitle_format="srt",
    prepend_timestamps=False,
    max_line_chars=42,
):
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    format_key = (subtitle_format or "srt").strip().lower()
    if format_key == "vtt":
        subtitle_path = output_dir / f"{stem}.vtt"
        subtitle_path.write_text(segments_to_vtt(segments, max_line_chars=max_line_chars), encoding="utf-8")
    else:
        subtitle_path = output_dir / f"{stem}.srt"
        subtitle_path.write_text(segments_to_srt(segments, max_line_chars=max_line_chars), encoding="utf-8")
    results.append(subtitle_path)

    text_path = output_dir / f"{stem}.txt"
    text_path.write_text(segments_to_text(segments, prepend_timestamps=prepend_timestamps), encoding="utf-8")
    results.append(text_path)
    return subtitle_path, results


def _subtitle_filter_arg(subtitle_path):
    escaped = str(subtitle_path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return f"subtitles='{escaped}'"


def render_subtitled_video(video_path, subtitle_path, output_path, codec_key, audio_bitrate_k):
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


def zip_outputs(paths, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in paths:
            file_path = Path(path)
            if not file_path.exists() or not file_path.is_file():
                continue
            zf.write(file_path, arcname=file_path.name)
    return destination
