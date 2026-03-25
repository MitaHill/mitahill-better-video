import json
import logging
import traceback
from datetime import datetime, timezone
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


def _flatten_result_outputs(media_results, key):
    outputs = []
    for item in media_results:
        outputs.extend(item.get(key) or [])
    return outputs


def _resolve_result_bundle(mode, media_results):
    multi_media = len(media_results) > 1
    subtitle_outputs = _flatten_result_outputs(media_results, "subtitle_outputs")
    video_outputs = _flatten_result_outputs(media_results, "video_outputs")
    preferred_outputs = _flatten_result_outputs(media_results, "preferred_outputs")

    # 这里把“业务模式”翻译成一个明确的出包策略。
    # 之前的问题不是转录失败，而是单文件/批量、字幕/视频混在一起后，
    # 最外层打包规则过于隐式，最后容易出现拿错结果、误打包的情况。
    if mode == "subtitled_video":
        bundle_kind = "batch_subtitled_video" if multi_media else "single_subtitled_video"
        outputs = preferred_outputs
        return {
            "bundle_kind": bundle_kind,
            "outputs": outputs,
            "should_zip": multi_media or len(outputs) != 1,
        }

    if mode == "subtitle_and_video_zip":
        bundle_kind = "batch_subtitle_and_video" if multi_media else "single_subtitle_and_video"
        outputs = subtitle_outputs + video_outputs
        return {
            "bundle_kind": bundle_kind,
            "outputs": outputs,
            "should_zip": len(outputs) != 1,
        }

    bundle_kind = "batch_subtitle_files" if multi_media else "single_subtitle_files"
    outputs = subtitle_outputs
    return {
        "bundle_kind": bundle_kind,
        "outputs": outputs,
        "should_zip": multi_media or len(outputs) != 1,
    }


def _process_single_media(task_id, media_item, options, run_dir, index, total, translator):
    media_path = Path(media_item.get("upload_path", ""))
    if not media_path.exists():
        raise RuntimeError(f"uploaded media missing: {media_item.get('filename')}")

    stem = _safe_stem(index, media_path)
    output_root = run_dir / "results" / stem
    subtitle_dir = output_root / "subtitles"
    text_dir = output_root / "texts"
    json_dir = output_root / "json"
    video_dir = output_root / "video"

    emit_progress(
        task_id,
        _build_item_progress(index, total, 0.05),
        f"转录文件 {index}/{total}: 准备中",
        file_index=index,
        file_count=total,
        stage="prepare",
    )
    audio_path, info, created_temp_audio = extract_transcribe_audio(media_path, run_dir)

    try:
        emit_progress(
            task_id,
            _build_item_progress(index, total, 0.25),
            f"转录文件 {index}/{total}: 语音识别中",
            file_index=index,
            file_count=total,
            stage="transcribe",
        )
        result = ENGINE.transcribe(
            audio_path,
            backend=options.get("transcription_backend", "faster_whisper"),
            model_name=options.get("whisper_model", "large-v3"),
            language=options.get("language", "auto"),
            temperature=options.get("temperature", 0.0),
            beam_size=options.get("beam_size", 5),
            best_of=options.get("best_of", 5),
            runtime_mode=options.get("transcribe_runtime_mode", "parallel"),
            task_id=task_id,
        )
        source_segments = _extract_segments(result)
        if not source_segments:
            raise RuntimeError(f"no transcript segments extracted from {media_item.get('filename')}")

        ENGINE.after_transcription_step(runtime_mode=options.get("transcribe_runtime_mode", "parallel"))

        subtitle_ext = _subtitle_suffix(options.get("subtitle_format", "srt"))
        text_outputs = []

        emit_progress(
            task_id,
            _build_item_progress(index, total, 0.45),
            f"转录文件 {index}/{total}: 写入原文字幕",
            file_index=index,
            file_count=total,
            stage="write_subtitle",
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
            emit_progress(
                task_id,
                _build_item_progress(index, total, 0.58),
                f"转录文件 {index}/{total}: 翻译中",
                file_index=index,
                file_count=total,
                stage="translate",
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
                    stage="translate",
                    unit_done=done,
                    unit_total=total_count,
                    unit_label="字幕段",
                )

            translated_segments = translate_segments(
                source_segments,
                translator,
                options.get("translate_to", ""),
                progress_callback=_translation_progress,
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
                # 双语字幕始终基于“原文段落 + 已翻译段落”重新配对生成，
                # 不复用单语写出的字幕文本，避免中间格式化差异把双语行宽搞乱。
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
                stage="render_video",
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
                    "transcription_backend": options.get("transcription_backend", "faster_whisper"),
                    "whisper_model": options.get("whisper_model", "large-v3"),
                    "translate_to": options.get("translate_to", ""),
                    "subtitle_format": options.get("subtitle_format", "srt"),
                    "transcribe_mode": options.get("transcribe_mode", "subtitle_zip"),
                },
            )
        )

        return {
            "subtitle_outputs": text_outputs,
            "video_outputs": video_outputs,
            # preferred_outputs 给最外层一个“默认交付物”的概念。
            # 单视频嵌入模式优先交视频；没有视频时，再优雅退回字幕文本。
            "preferred_outputs": video_outputs or text_outputs,
        }
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

        media_results = []
        total = len(media_files)
        for idx, media_item in enumerate(media_files, start=1):
            media_results.append(_process_single_media(task_id, media_item, options, run_dir, idx, total, translator))

        mode = options.get("transcribe_mode", "subtitle_zip")
        bundle = _resolve_result_bundle(mode, media_results)
        result_outputs = bundle.get("outputs") or []

        if not result_outputs:
            raise RuntimeError("No output generated by transcription pipeline.")

        if bundle["should_zip"]:
            result_name = f"{bundle['bundle_kind']}_{task_id}"
            result_path = run_dir / "results" / f"{result_name}.zip"
            zip_outputs(
                result_outputs,
                result_path,
                base_dir=run_dir / "results",
                # root_prefix 直接带上 bundle_kind，解压后目录名就能看出这是哪一类结果。
                root_prefix=result_name,
            )
        else:
            result_path = result_outputs[0]

        db.update_task_result(task_id, result_path)
        db.update_task_status(task_id, "COMPLETED", 100, f"Completed: {Path(result_path).name}")
        send_event(
            {
                "task_id": task_id,
                "task_category": "transcribe",
                "progress": 100,
                "message": "转录任务已完成",
                "stage": "completed",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
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
