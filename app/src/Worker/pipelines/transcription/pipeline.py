import json
import logging
from pathlib import Path
import time
import traceback

from app.src.Database import core as db
from app.src.Notifications.events import send_event
from app.src.Utils.http import ffprobe_info

from .checkpoints import (
    build_asr_signature,
    build_media_signature,
    build_translation_signature,
    build_translation_signature_legacy,
    build_translation_signature_with_explicit_thinking,
    load_cached_source_segments,
    load_cached_translation_map,
    mark_media_completed,
    save_source_segments,
    save_translated_segments,
    save_translation_segment,
)
from .io_ops import (
    extract_transcribe_audio,
    render_subtitled_video,
    write_json_file,
    write_subtitle_file,
    write_text_file,
    zip_outputs,
)
from .options import normalize_transcription_options
from .progress import TaskCancelledError, emit_progress, emit_stream_event, ensure_not_cancelled
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
    ensure_not_cancelled(task_id)
    media_path = Path(media_item.get("upload_path", ""))
    if not media_path.exists():
        raise RuntimeError(f"uploaded media missing: {media_item.get('filename')}")

    stem = _safe_stem(index, media_path)
    output_root = run_dir / "results" / stem
    subtitle_dir = output_root / "subtitles"
    text_dir = output_root / "texts"
    json_dir = output_root / "json"
    video_dir = output_root / "video"
    media_signature = build_media_signature(media_path)
    asr_signature = build_asr_signature(options)
    translation_signature = build_translation_signature(options)
    translation_signature_legacy = build_translation_signature_legacy(options)
    translation_signature_transitional = build_translation_signature_with_explicit_thinking(options)

    emit_progress(
        task_id,
        _build_item_progress(index, total, 0.05),
        f"转录文件 {index}/{total}: 准备中",
        file_index=index,
        file_count=total,
    )
    info = ffprobe_info(media_path)
    created_temp_audio = False
    audio_path = media_path

    try:
        ensure_not_cancelled(task_id)
        source_segments = load_cached_source_segments(
            task_id,
            stem,
            media_signature=media_signature,
            asr_signature=asr_signature,
        )
        if source_segments:
            emit_progress(
                task_id,
                _build_item_progress(index, total, 0.25),
                f"转录文件 {index}/{total}: 复用已保存转录结果",
                file_index=index,
                file_count=total,
            )
        else:
            emit_progress(
                task_id,
                _build_item_progress(index, total, 0.25),
                f"转录文件 {index}/{total}: 语音识别中",
                file_index=index,
                file_count=total,
            )
            audio_path, audio_info, created_temp_audio = extract_transcribe_audio(media_path, run_dir)
            media_duration = max(
                float((info or {}).get("duration", 0.0) or 0.0),
                float((audio_info or {}).get("duration", 0.0) or 0.0),
            )
            asr_state = {"last_ratio": -1.0, "last_emit_ts": 0.0}

            def _asr_progress(done_sec, total_sec):
                safe_done = max(0.0, float(done_sec or 0.0))
                safe_total = max(
                    float(total_sec or 0.0),
                    media_duration,
                    safe_done,
                )
                if safe_total <= 0:
                    return
                ratio = max(0.0, min(1.0, safe_done / safe_total))
                now = time.time()
                if ratio < 1.0:
                    ratio_delta = ratio - float(asr_state["last_ratio"])
                    elapsed = now - float(asr_state["last_emit_ts"])
                    if ratio_delta < 0.008 and elapsed < 0.6:
                        return
                asr_state["last_ratio"] = ratio
                asr_state["last_emit_ts"] = now
                progress_percent = int(round(ratio * 100))
                emit_progress(
                    task_id,
                    _build_item_progress(index, total, 0.25 + ratio * 0.18),
                    (
                        f"转录文件 {index}/{total}: 语音识别中 {progress_percent}% "
                        f"({safe_done:.1f}s/{safe_total:.1f}s)"
                    ),
                    file_index=index,
                    file_count=total,
                )

            def _asr_segment(seg_idx, start_sec, end_sec, text):
                safe_text = str(text or "").strip()
                if not safe_text:
                    return
                emit_stream_event(
                    task_id,
                    channel="asr",
                    mode="line",
                    text=safe_text,
                    file_index=index,
                    file_count=total,
                    segment_index=int(seg_idx or 0),
                    line_key=f"asr:{index}:{int(seg_idx or 0)}",
                    meta={"start_sec": float(start_sec or 0.0), "end_sec": float(end_sec or 0.0)},
                )

            result = ENGINE.transcribe(
                audio_path,
                backend=options.get("transcription_backend", "whisper"),
                model_name=options.get("whisper_model", "medium"),
                language=options.get("language", "auto"),
                temperature=options.get("temperature", 0.0),
                beam_size=options.get("beam_size", 5),
                best_of=options.get("best_of", 5),
                runtime_mode=options.get("transcribe_runtime_mode", "parallel"),
                task_id=task_id,
                progress_callback=_asr_progress,
                expected_duration_sec=media_duration,
                segment_callback=_asr_segment,
            )
            source_segments = _extract_segments(result)
            if not source_segments:
                raise RuntimeError(f"no transcript segments extracted from {media_item.get('filename')}")
            save_source_segments(
                task_id,
                stem,
                source_path=str(media_path),
                media_signature=media_signature,
                asr_signature=asr_signature,
                source_segments=source_segments,
            )
            ENGINE.after_transcription_step(runtime_mode=options.get("transcribe_runtime_mode", "parallel"))

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
            subtitle_dir / f"original.{subtitle_ext}",
            source_segments,
            subtitle_format=options.get("subtitle_format", "srt"),
            max_line_chars=options.get("max_line_chars", 42),
        )
        text_outputs.append(original_subtitle)
        text_outputs.append(
            write_text_file(
                text_dir / "original.txt",
                source_segments,
                prepend_timestamps=options.get("prepend_timestamps", False),
            )
        )
        if options.get("export_json"):
            text_outputs.append(
                write_json_file(
                    json_dir / "original.json",
                    {"media": media_item, "segments": source_segments},
                )
            )

        translated_segments = None
        translated_subtitle = None
        if translator and (options.get("translate_to") or "").strip():
            cached_translation_map = load_cached_translation_map(
                task_id,
                stem,
                source_segments,
                media_signature=media_signature,
                translation_signature=translation_signature,
                compatible_translation_signatures=[
                    translation_signature_legacy,
                    translation_signature_transitional,
                ],
            )
            emit_progress(
                task_id,
                _build_item_progress(index, total, 0.58),
                f"转录文件 {index}/{total}: 翻译中",
                file_index=index,
                file_count=total,
            )
            if cached_translation_map:
                emit_progress(
                    task_id,
                    _build_item_progress(index, total, 0.60),
                    (
                        f"转录文件 {index}/{total}: 翻译断点恢复 "
                        f"{len(cached_translation_map)}/{len(source_segments)}"
                    ),
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

            def _translation_checkpoint(seg_idx, source_text, translated_text, status, message):
                save_translation_segment(
                    task_id,
                    stem,
                    seg_idx,
                    source_text,
                    translated_text,
                    status=status,
                    message=message,
                )
                line_key = f"translate:{index}:{int(seg_idx or 0)}"
                if not _translation_raw_seen.get(int(seg_idx or 0)) and str(translated_text or "").strip():
                    emit_stream_event(
                        task_id,
                        channel="translation_raw",
                        mode="append",
                        text=str(translated_text or ""),
                        file_index=index,
                        file_count=total,
                        segment_index=int(seg_idx or 0),
                        line_key=line_key,
                    )
                emit_stream_event(
                    task_id,
                    channel="translation_raw",
                    mode="commit",
                    text="",
                    file_index=index,
                    file_count=total,
                    segment_index=int(seg_idx or 0),
                    line_key=line_key,
                    meta={"status": status, "message": str(message or "")},
                )

            _translation_raw_seen = {}

            def _translation_raw_stream(seg_idx, raw_delta):
                safe_delta = str(raw_delta or "")
                if not safe_delta:
                    return
                safe_seg_idx = int(seg_idx or 0)
                _translation_raw_seen[safe_seg_idx] = True
                emit_stream_event(
                    task_id,
                    channel="translation_raw",
                    mode="append",
                    text=safe_delta,
                    file_index=index,
                    file_count=total,
                    segment_index=safe_seg_idx,
                    line_key=f"translate:{index}:{safe_seg_idx}",
                )

            translated_segments = translate_segments(
                source_segments,
                translator,
                options.get("translate_to", ""),
                progress_callback=_translation_progress,
                cached_text_map=cached_translation_map,
                checkpoint_callback=_translation_checkpoint,
                should_cancel=lambda: db.is_task_cancel_requested(task_id),
                raw_stream_callback=_translation_raw_stream,
            )
            save_translated_segments(
                task_id,
                stem,
                media_signature=media_signature,
                translation_signature=translation_signature,
                translated_segments=translated_segments,
            )

            translated_subtitle = write_subtitle_file(
                subtitle_dir / f"translated.{subtitle_ext}",
                translated_segments,
                subtitle_format=options.get("subtitle_format", "srt"),
                max_line_chars=options.get("max_line_chars", 42),
            )
            text_outputs.append(translated_subtitle)
            text_outputs.append(
                write_text_file(
                    text_dir / "translated.txt",
                    translated_segments,
                    prepend_timestamps=options.get("prepend_timestamps", False),
                )
            )
            if options.get("generate_bilingual"):
                bilingual_segments = build_bilingual_segments(source_segments, translated_segments)
                text_outputs.append(
                    write_subtitle_file(
                        subtitle_dir / f"bilingual.{subtitle_ext}",
                        bilingual_segments,
                        subtitle_format=options.get("subtitle_format", "srt"),
                        max_line_chars=options.get("max_line_chars", 42),
                    )
                )
            if options.get("export_json"):
                text_outputs.append(
                    write_json_file(
                        json_dir / "translated.json",
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
                    video_dir / "subtitled.mp4",
                    options.get("output_video_codec", "h264"),
                    options.get("output_audio_bitrate_k", 192),
                )
            )

        text_outputs.append(
            write_json_file(
                output_root / "meta.json",
                {
                    "task_id": task_id,
                    "source_file": media_item,
                    "runtime_mode": options.get("transcribe_runtime_mode", "parallel"),
                    "transcription_backend": options.get("transcription_backend", "whisper"),
                    "whisper_model": options.get("whisper_model", "medium"),
                    "translate_to": options.get("translate_to", ""),
                    "translator_context_window_size": options.get("translator_context_window_size", 6),
                    "translator_batch_window_size": options.get("translator_batch_window_size", 10),
                    "translator_batch_max_chars": options.get("translator_batch_max_chars", 2500),
                    "resume_checkpoint_enabled": True,
                    "subtitle_format": options.get("subtitle_format", "srt"),
                    "transcribe_mode": options.get("transcribe_mode", "subtitle_zip"),
                },
            )
        )
        mark_media_completed(
            task_id,
            stem,
            media_signature=media_signature,
            asr_signature=asr_signature,
            translation_signature=translation_signature,
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
    ensure_not_cancelled(task_id)

    translator = None
    try:
        if (options.get("translate_to") or "").strip():
            translator = create_translator(options)
            if translator is None:
                raise RuntimeError("translation requested but translator provider is disabled (translator_provider=none).")
            logger.info("Task %s translation enabled, provider=%s", task_id, getattr(translator, "label", "-"))
            try:
                translator.prepare_for_task()
            except Exception:
                logger.warning("Task %s translator prepare failed", task_id, exc_info=True)

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
            zip_outputs(
                all_outputs,
                result_path,
                base_dir=run_dir / "results",
                root_prefix=f"transcribe_{task_id}",
            )
        else:
            result_path = all_outputs[-1]

        db.update_task_result(task_id, result_path)
        db.update_task_status(task_id, "COMPLETED", 100, f"Completed: {Path(result_path).name}")
        send_event({"task_id": task_id, "progress": 100, "message": "转录任务已完成"})
    except TaskCancelledError:
        logger.info("Task %s transcription cancelled by admin.", task_id)
        raise
    except Exception:
        logger.error("Task %s transcription pipeline failed.\n%s", task_id, traceback.format_exc())
        raise
    finally:
        try:
            ENGINE.finalize_task(runtime_mode=options.get("transcribe_runtime_mode", "parallel"))
        except Exception:
            logger.warning("Task %s engine finalize failed", task_id, exc_info=True)
        if translator:
            try:
                translator.on_task_end()
            except Exception:
                logger.warning("Task %s translator finalize failed", task_id, exc_info=True)
