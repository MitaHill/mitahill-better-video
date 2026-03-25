from pathlib import Path

from app.src.Audio.haas_effect import apply_haas_effect
from app.src.Config import settings as config
from app.src.Utils.ffmpeg import get_video_duration, run_ffmpeg

from .common import GPU_CODEC_MAP, VALID_AUDIO_MODES, VALID_FORMATS, to_bool, to_float, to_int
from .filters import build_audio_filter, build_video_filters
from .progress import emit_progress, run_ffmpeg_with_progress
from .watermark import apply_watermark_and_metadata


def render_single_video(task_id, video_path, audio_paths, options, run_dir, index, total):
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
    tmp_haas = run_dir / f"{base_stem}_haas.wav"
    tmp_audio = run_dir / f"{base_stem}_audio.wav"
    tmp_marked = run_dir / f"{base_stem}_marked.{output_format}"
    final_path = out_dir / f"{base_stem}.{output_format}"

    size_limit_mb = to_float(options.get("target_size_mb"), 0.0, min_value=0.0)
    audio_bitrate_k = to_int(options.get("audio_bitrate_k"), 192, min_value=32, max_value=1024)
    target_video_bitrate = None
    if size_limit_mb > 0 and duration > 0:
        total_bps = int((size_limit_mb * 8 * 1024 * 1024) / duration)
        audio_bps = 0 if to_bool(options.get("mute_audio"), False) else audio_bitrate_k * 1000
        target_video_bitrate = max(200_000, total_bps - audio_bps)
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

    mute_audio = to_bool(options.get("mute_audio"), False)
    audio_mode = (options.get("audio_source_mode") or "keep_original").lower()
    if audio_mode not in VALID_AUDIO_MODES:
        audio_mode = "keep_original"

    selected_audio = audio_paths[(index - 1) % len(audio_paths)] if audio_paths else None
    has_uploaded_audio = selected_audio is not None and Path(selected_audio).exists()
    if audio_mode in {"replace_uploaded", "mix_uploaded"} and not has_uploaded_audio:
        audio_mode = "keep_original"

    map_audio_from_video = audio_mode in {"keep_original", "mix_uploaded"} and not mute_audio
    map_audio_uploaded = has_uploaded_audio and audio_mode in {"replace_uploaded", "mix_uploaded"} and not mute_audio

    af = build_audio_filter({**options, "_duration": duration})
    sample_rate = to_int(options.get("audio_sample_rate"), 0, min_value=0, max_value=192000)
    channels_mode = (options.get("audio_channels_mode") or "keep").lower()
    channels = 0
    if channels_mode == "mono":
        channels = 1
    elif channels_mode == "stereo":
        channels = 2

    emit_progress(
        task_id,
        60 + int((index - 1) * (80 / max(total, 1))),
        f"转换视频 {index}/{total}: 音频处理中",
        file_index=index,
        file_count=total,
        stage="audio",
    )

    if not map_audio_from_video and not map_audio_uploaded:
        run_ffmpeg(["ffmpeg", "-y", "-i", str(tmp_video_only), "-c:v", "copy", "-an", str(tmp_muxed)])
    else:
        mux_cmd = ["ffmpeg", "-y", "-i", str(tmp_video_only)]
        if map_audio_from_video:
            mux_cmd += ["-i", str(video_path)]
        if map_audio_uploaded:
            mux_cmd += ["-i", str(selected_audio)]

        filter_parts = []
        if map_audio_from_video and map_audio_uploaded and audio_mode == "mix_uploaded":
            filter_parts.append("[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=2[mixa]")
            if af:
                filter_parts.append(f"[mixa]{af}[aout]")
            else:
                filter_parts.append("[mixa]anull[aout]")
        else:
            src_label = "[1:a]"
            if af:
                filter_parts.append(f"{src_label}{af}[aout]")
            else:
                filter_parts.append(f"{src_label}anull[aout]")

        if filter_parts:
            mux_cmd += ["-filter_complex", ";".join(filter_parts), "-map", "0:v:0", "-map", "[aout]"]
        else:
            mux_cmd += ["-map", "0:v:0", "-map", "1:a?"]

        mux_cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", f"{audio_bitrate_k}k"]
        if sample_rate > 0:
            mux_cmd += ["-ar", str(sample_rate)]
        if channels > 0:
            mux_cmd += ["-ac", str(channels)]
        mux_cmd += ["-shortest", str(tmp_muxed)]
        run_ffmpeg(mux_cmd)

    if to_bool(options.get("haas_enabled"), False) and not mute_audio:
        delay = to_int(options.get("haas_delay_ms"), 0, min_value=0, max_value=3000)
        lead = options.get("haas_lead", "left")
        run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(tmp_muxed),
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "44100",
                "-ac",
                "2",
                str(tmp_audio),
            ]
        )
        apply_haas_effect(tmp_audio, tmp_haas, delay, lead)
        run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(tmp_muxed),
                "-i",
                str(tmp_haas),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                f"{audio_bitrate_k}k",
                "-shortest",
                str(tmp_marked),
            ]
        )
        source_for_mark = tmp_marked
    else:
        source_for_mark = tmp_muxed

    emit_progress(
        task_id,
        75 + int((index - 1) * (80 / max(total, 1))),
        f"转换视频 {index}/{total}: 水印与元数据",
        file_index=index,
        file_count=total,
        stage="finalize",
    )
    apply_watermark_and_metadata(source_for_mark, final_path, options, duration, run_dir)

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
                "aac",
                "-b:a",
                f"{audio_bitrate_k}k",
                str(reencoded),
            ]
        )
        reencoded.replace(final_path)

    for tmp in [tmp_video_only, tmp_muxed, tmp_audio, tmp_haas, tmp_marked]:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass

    return final_path
