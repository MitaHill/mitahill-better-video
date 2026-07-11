import hashlib
import json
import shutil
import zipfile
from pathlib import Path

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


def render_subtitled_video(video_path, subtitle_tracks, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subtitle_tmp_dir = Path("/workspace/storage/tmp/subtitles")
    subtitle_tmp_dir.mkdir(parents=True, exist_ok=True)
    subtitle_hash = hashlib.sha1(str(output_path).encode("utf-8")).hexdigest()[:12]
    render_subtitles = []

    for idx, track in enumerate(subtitle_tracks or []):
        source_subtitle = Path(track["path"])
        subtitle_suffix = source_subtitle.suffix or ".srt"
        render_subtitle = subtitle_tmp_dir / f"render_subtitle_{subtitle_hash}_{idx}{subtitle_suffix}"
        render_subtitle.unlink(missing_ok=True)
        shutil.copy2(source_subtitle, render_subtitle)
        render_subtitles.append((render_subtitle, track))

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
    ]
    for render_subtitle, _track in render_subtitles:
        cmd.extend(["-i", str(render_subtitle)])

    cmd.extend([
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
    ])
    for idx, _item in enumerate(render_subtitles, start=1):
        cmd.extend(["-map", f"{idx}:0"])

    cmd.extend(["-c", "copy", "-c:s", "mov_text"])
    for idx, (_render_subtitle, track) in enumerate(render_subtitles):
        title = str(track.get("title") or "字幕")
        disposition = "default" if track.get("default") else "0"
        cmd.extend(
            [
                f"-metadata:s:s:{idx}",
                "language=und",
                f"-metadata:s:s:{idx}",
                f"title={title}",
                f"-metadata:s:s:{idx}",
                f"handler_name={title}",
                f"-disposition:s:{idx}",
                disposition,
            ]
        )
    cmd.append(str(output_path))

    try:
        run_ffmpeg(cmd)
    finally:
        for render_subtitle, _track in render_subtitles:
            render_subtitle.unlink(missing_ok=True)
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
