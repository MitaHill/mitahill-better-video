from app.src.Config import settings as config
from app.src.Utils.ffmpeg import get_video_duration, run_ffmpeg

from .common import GPU_CODEC_MAP, VALID_FORMATS, to_bool, to_float, to_int
from .filters import build_video_filters
from .progress import emit_progress, run_ffmpeg_with_progress
from .watermark import apply_watermark_and_metadata


def render_single_video(task_id, video_path, options, run_dir, index, total):
    output_format = (options.get("output_format") or "mp4").lower()
    if output_format not in VALID_FORMATS:
        output_format = "mp4"

    codec_key = (options.get("video_codec") or "h264").lower()
    gpu_codec, cpu_codec = GPU_CODEC_MAP.get(codec_key, GPU_CODEC_MAP["h264"])
    frame_rate = to_int(options.get("frame_rate"), 0, min_value=0, max_value=120)
    duration = max(0.01, get_video_duration(video_path))

    out_dir = run_dir / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    base_stem = video_path.stem
    tmp_video_only = run_dir / f"{base_stem}_video_only.mp4"
    tmp_muxed = run_dir / f"{base_stem}_muxed.{output_format}"
    final_path = out_dir / f"{base_stem}.{output_format}"

    size_limit_mb = to_float(options.get("target_size_mb"), 0.0, min_value=0.0)
    target_video_bitrate = None
    if size_limit_mb > 0 and duration > 0:
        total_bps = int((size_limit_mb * 8 * 1024 * 1024) / duration)
        target_video_bitrate = max(200_000, total_bps)
    elif to_int(options.get("video_bitrate_k"), 0, min_value=0) > 0:
        target_video_bitrate = to_int(options.get("video_bitrate_k"), 0) * 1000

    vf = build_video_filters(options, duration)
    emit_progress(
        task_id,
        5 + int((index - 1) * (80 / max(total, 1))),
        f"转换视频 {index}/{total}: 编码准备",
        file_index=index,
        file_count=total,
        stage="prepare",
    )

    hwaccel = ["-hwaccel", "cuda"] if config.FFMPEG_USE_GPU else []
    video_cmd = ["ffmpeg", "-y", *hwaccel, "-i", str(video_path), "-an"]
    if vf:
        video_cmd += ["-vf", vf]
    if frame_rate > 0:
        video_cmd += ["-r", str(frame_rate)]
    video_cmd += ["-c:v", gpu_codec, "-preset", "p4", "-pix_fmt", "yuv420p"]
    if target_video_bitrate:
        video_cmd += [
            "-b:v",
            str(target_video_bitrate),
            "-maxrate",
            str(target_video_bitrate),
            "-bufsize",
            str(target_video_bitrate * 2),
        ]
    else:
        crf = to_int(options.get("crf"), 18, min_value=10, max_value=35)
        video_cmd += ["-rc:v", "vbr", "-cq:v", str(crf), "-b:v", "0"]
    video_cmd += [str(tmp_video_only)]

    cpu_fallback = ["ffmpeg", "-y", "-i", str(video_path), "-an"]
    if vf:
        cpu_vf = vf.replace("yadif_cuda=mode=send_frame:parity=auto:deint=all", "yadif")
        cpu_fallback += ["-vf", cpu_vf]
    if frame_rate > 0:
        cpu_fallback += ["-r", str(frame_rate)]
    cpu_fallback += ["-c:v", cpu_codec, "-pix_fmt", "yuv420p"]
    if target_video_bitrate:
        cpu_fallback += [
            "-b:v",
            str(target_video_bitrate),
            "-maxrate",
            str(target_video_bitrate),
            "-bufsize",
            str(target_video_bitrate * 2),
        ]
    else:
        cpu_fallback += ["-crf", str(to_int(options.get("crf"), 18, min_value=10, max_value=35))]
    cpu_fallback += [str(tmp_video_only)]

    try:
        run_ffmpeg_with_progress(
            video_cmd,
            task_id=task_id,
            duration_seconds=duration,
            progress_start=5 + int((index - 1) * (80 / max(total, 1))),
            progress_end=55 + int((index - 1) * (80 / max(total, 1))),
            stage_message=f"转换视频 {index}/{total}: 视频编码中",
            file_index=index,
            file_count=total,
        )
    except Exception:
        run_ffmpeg_with_progress(
            cpu_fallback,
            task_id=task_id,
            duration_seconds=duration,
            progress_start=5 + int((index - 1) * (80 / max(total, 1))),
            progress_end=55 + int((index - 1) * (80 / max(total, 1))),
            stage_message=f"转换视频 {index}/{total}: CPU 编码中",
            file_index=index,
            file_count=total,
        )

    emit_progress(
        task_id,
        60 + int((index - 1) * (80 / max(total, 1))),
        f"转换视频 {index}/{total}: 封装音轨",
        file_index=index,
        file_count=total,
        stage="audio",
    )

    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(tmp_video_only),
            "-i",
            str(video_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0?",
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-shortest",
            str(tmp_muxed),
        ]
    )

    emit_progress(
        task_id,
        75 + int((index - 1) * (80 / max(total, 1))),
        f"转换视频 {index}/{total}: 水印与元数据",
        file_index=index,
        file_count=total,
        stage="finalize",
    )
    apply_watermark_and_metadata(tmp_muxed, final_path, options, duration, run_dir)

    if to_bool(options.get("second_pass_reencode"), False):
        reencoded = out_dir / f"{base_stem}_pass2.{output_format}"
        bitrate_args = []
        if target_video_bitrate:
            bitrate_args = [
                "-b:v",
                str(target_video_bitrate),
                "-maxrate",
                str(target_video_bitrate),
                "-bufsize",
                str(target_video_bitrate * 2),
            ]
        else:
            bitrate_args = ["-crf", str(to_int(options.get("crf"), 18, min_value=10, max_value=35))]
        run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(final_path),
                "-c:v",
                cpu_codec,
                *bitrate_args,
                "-c:a",
                "copy",
                str(reencoded),
            ]
        )
        reencoded.replace(final_path)

    for tmp in [tmp_video_only, tmp_muxed]:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass

    return final_path
