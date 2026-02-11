import json
import logging
from pathlib import Path

from app.src.Database import core as db
from app.src.Notifications.events import send_event

from .io_ops import (
    extract_transcribe_audio,
    render_subtitled_video,
    write_json_file,
    write_subtitle_file,
    write_text_file,
    zip_outputs,
)
from .options import normalize_transcription_options
from .progress import emit_progress
from .translation import build_bilingual_segments, create_translator, translate_segments
from .whisper_engine import ENGINE

logger = logging.getLogger("TRANSCRIBE")


def _extract_segments(transcript_result):
    if isinstance(transcript_result, dict):
        segments = transcript_result.get("segments")
        if isinstance(segments, list):
            return segments
    return []


def _build_item_progress(index, total, inner):
    total_items = max(1, int(total or 1))
    clamped_inner = max(0.0, min(1.0, float(inner or 0.0)))
    base = (index - 1) / total_items
    return int(5 + (base + clamped_inner / total_items) * 90)


def _safe_stem(index, media_path):
    stem = media_path.stem.replace(" ", "_")
    return f"{index:03d}_{stem}"


def _subtitle_suffix(subtitle_format):
    return "vtt" if (subtitle_format or "srt").lower() == "vtt" else "srt"


def _process_single_media(task_id, media_item, options, run_dir, index, total, translator):
    media_path = Path(media_item.get("upload_path", ""))
    if not media_path.exists():
        raise RuntimeError(f"uploaded media missing: {media_item.get('filename')}")

    stem = _safe_stem(index, media_path)
    output_dir = run_dir / "results"

    emit_progress(
        task_id,
        _build_item_progress(index, total, 0.05),
        f"转录文件 {index}/{total}: 准备中",
        file_index=index,
        file_count=total,
    )
    audio_path, info, created_temp_audio = extract_transcribe_audio(media_path, run_dir)

    try:
        emit_progress(
            task_id,
            _build_item_progress(index, total, 0.25),
            f"转录文件 {index}/{total}: 语音识别中",
            file_index=index,
            file_count=total,
        )
        result = ENGINE.transcribe(
            audio_path,
            backend=options.get("transcription_backend", "whisper"),
            model_name=options.get("whisper_model", "medium"),
            language=options.get("language", "auto"),
            temperature=options.get("temperature", 0.0),
            beam_size=options.get("beam_size", 5),
            best_of=options.get("best_of", 5),
        )
        source_segments = _extract_segments(result)
        if not source_segments:
            raise RuntimeError(f"no transcript segments extracted from {media_item.get('filename')}")

        subtitle_ext = _subtitle_suffix(options.get("subtitle_format", "srt"))
        text_outputs = []

        emit_progress(
            task_id,
            _build_item_progress(index, total, 0.45),
            f"转录文件 {index}/{total}: 写入原文字幕",
            file_index=index,
            file_count=total,
        )
        original_subtitle = write_subtitle_file(
            output_dir / f"{stem}_original.{subtitle_ext}",
            source_segments,
            subtitle_format=options.get("subtitle_format", "srt"),
            max_line_chars=options.get("max_line_chars", 42),
        )
        text_outputs.append(original_subtitle)
        text_outputs.append(
            write_text_file(
                output_dir / f"{stem}_original.txt",
                source_segments,
                prepend_timestamps=options.get("prepend_timestamps", False),
            )
        )
        if options.get("export_json"):
            text_outputs.append(
                write_json_file(
                    output_dir / f"{stem}_original.json",
                    {"media": media_item, "segments": source_segments},
                )
            )

        translated_segments = None
        translated_subtitle = None
        if translator and (options.get("translate_to") or "").strip():
            emit_progress(
                task_id,
                _build_item_progress(index, total, 0.58),
                f"转录文件 {index}/{total}: 翻译中",
                file_index=index,
                file_count=total,
            )

            def _translation_progress(done, total_count):
                if total_count <= 0:
                    return
                ratio = max(0.0, min(1.0, float(done) / float(total_count)))
                emit_progress(
                    task_id,
                    _build_item_progress(index, total, 0.58 + ratio * 0.18),
                    f"转录文件 {index}/{total}: 翻译中 {done}/{total_count}",
                    file_index=index,
                    file_count=total,
                )

            translated_segments = translate_segments(
                source_segments,
                translator,
                options.get("translate_to", ""),
                progress_callback=_translation_progress,
            )

            translated_subtitle = write_subtitle_file(
                output_dir / f"{stem}_translated.{subtitle_ext}",
                translated_segments,
                subtitle_format=options.get("subtitle_format", "srt"),
                max_line_chars=options.get("max_line_chars", 42),
            )
            text_outputs.append(translated_subtitle)
            text_outputs.append(
                write_text_file(
                    output_dir / f"{stem}_translated.txt",
                    translated_segments,
                    prepend_timestamps=options.get("prepend_timestamps", False),
                )
            )
            if options.get("generate_bilingual"):
                bilingual_segments = build_bilingual_segments(source_segments, translated_segments)
                text_outputs.append(
                    write_subtitle_file(
                        output_dir / f"{stem}_bilingual.{subtitle_ext}",
                        bilingual_segments,
                        subtitle_format=options.get("subtitle_format", "srt"),
                        max_line_chars=options.get("max_line_chars", 42),
                    )
                )
            if options.get("export_json"):
                text_outputs.append(
                    write_json_file(
                        output_dir / f"{stem}_translated.json",
                        {"media": media_item, "segments": translated_segments},
                    )
                )

        mode = options.get("transcribe_mode", "subtitle_zip")
        video_outputs = []
        if mode in {"subtitled_video", "subtitle_and_video_zip"} and info.get("has_video"):
            emit_progress(
                task_id,
                _build_item_progress(index, total, 0.86),
                f"转录文件 {index}/{total}: 合成字幕视频",
                file_index=index,
                file_count=total,
            )
            subtitle_for_video = translated_subtitle or original_subtitle
            video_outputs.append(
                render_subtitled_video(
                    media_path,
                    subtitle_for_video,
                    output_dir / f"{stem}_subtitled.mp4",
                    options.get("output_video_codec", "h264"),
                    options.get("output_audio_bitrate_k", 192),
                )
            )

        if mode == "subtitled_video":
            if video_outputs:
                return video_outputs
            return text_outputs
        if mode == "subtitle_and_video_zip":
            return text_outputs + video_outputs
        return text_outputs
    finally:
        if created_temp_audio and audio_path.exists():
            try:
                audio_path.unlink()
            except Exception:
                pass


def process_transcription_task(task):
    task_id = task["task_id"]
    raw_params = json.loads(task.get("task_params") or "{}")
    options = normalize_transcription_options(raw_params)
    run_dir = Path("/workspace/storage/output") / f"run_{task_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    media_files = raw_params.get("media_files") or []
    if not media_files:
        raise RuntimeError("No uploaded audio/video files for transcription.")

    emit_progress(task_id, 2, "转录任务初始化中...")

    translator = None
    if (options.get("translate_to") or "").strip():
        translator = create_translator(options)
        if translator is None:
            raise RuntimeError("translation requested but translator provider is disabled (translator_provider=none).")
        logger.info("Task %s translation enabled, provider=%s", task_id, getattr(translator, "label", "-"))

    all_outputs = []
    total = len(media_files)
    for idx, media_item in enumerate(media_files, start=1):
        outputs = _process_single_media(task_id, media_item, options, run_dir, idx, total, translator)
        all_outputs.extend(outputs)

    if not all_outputs:
        raise RuntimeError("No output generated by transcription pipeline.")

    mode = options.get("transcribe_mode", "subtitle_zip")
    should_zip = len(media_files) > 1 or mode in {"subtitle_zip", "subtitle_and_video_zip"}
    if mode == "subtitled_video" and not any(str(p).lower().endswith(".mp4") for p in all_outputs):
        should_zip = True

    if should_zip:
        result_path = run_dir / "results" / f"transcribe_{task_id}.zip"
        zip_outputs(all_outputs, result_path)
    else:
        result_path = all_outputs[-1]

    db.update_task_result(task_id, result_path)
    db.update_task_status(task_id, "COMPLETED", 100, f"Completed: {Path(result_path).name}")
    send_event({"task_id": task_id, "progress": 100, "message": "转录任务已完成"})
