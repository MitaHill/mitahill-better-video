import json
import re
import shutil

from app.src.Config import settings as config
from app.src.Utils.ffmpeg import run_ffmpeg
from app.src.Utils.media_mux import probe_media

from .common import to_bool
from .filters import build_video_filters
from .metadata import read_metadata, ffmpeg_metadata_args, restore_metadata
from .plan import build_plan, stream_args, encoding_args, validate_streams
from .progress import emit_progress, run_ffmpeg_with_progress
from .watermark import build_watermark_filter


def render_single_video(task_id, video_path, options, run_dir, index, total):
    original = probe_media(video_path)
    metadata = read_metadata(video_path)
    duration = max(.01, float(original.get('format', {}).get('duration') or 0))
    video = next((s for s in original['streams'] if s.get('codec_type') == 'video'
                  and not s.get('disposition', {}).get('attached_pic')), None)
    if video is None:
        raise RuntimeError('原文件没有视频流')
    vf = build_video_filters(options, duration)
    extra_inputs, graph, filtered_video = build_watermark_filter(options, duration, run_dir, video['index'])
    if vf:
        if graph:
            graph = f"[0:{video['index']}]{vf}[basevideo];" + graph.replace(f"[0:{video['index']}]", '[basevideo]', 1)
        else:
            graph, filtered_video = f"[0:{video['index']}]{vf}[filtered_video]", '[filtered_video]'
    plan = build_plan(original, video_path, options, has_filters=bool(graph))
    if plan.reencode and any(s.get('side_data_type') in {'Mastering display metadata', 'Content light level metadata', 'DOVI configuration record'} for s in video.get('side_data_list', [])):
        raise RuntimeError('该视频包含 HDR/Dolby Vision 专用元数据，当前无法保证重新编码后完整保留；请保持原编码')
    out_dir = run_dir / 'results'
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / f'{video_path.stem}.{plan.suffix}'
    working = run_dir / f'{video_path.stem}_working.{plan.suffix}'
    progress_start = 5 + int((index - 1) * 80 / max(total, 1))
    progress_end = 5 + int(index * 80 / max(total, 1))

    def command(gpu):
        cmd = ['ffmpeg', '-y', '-noautorotate', '-i', str(video_path), *extra_inputs]
        if graph:
            cmd += ['-filter_complex', graph]
        cmd += stream_args(original, plan, filtered_video)
        cmd += encoding_args(original, plan, options, duration, gpu=gpu)
        cmd += ffmpeg_metadata_args(metadata, plan.container)
        for option, key in (('meta_title', 'title'), ('meta_author', 'artist'), ('meta_comment', 'comment')):
            if str(options.get(option) or '').strip():
                cmd += ['-metadata', f'{key}={options[option].strip()}']
        return [*cmd, '-f', plan.container, str(working)]

    def execute(gpu):
        run_ffmpeg_with_progress(
            command(gpu), task_id=task_id, duration_seconds=duration,
            progress_start=progress_start, progress_end=progress_end,
            stage_message=f'转换视频 {index}/{total}: 仅修改指定视频，复制其他媒体流',
            file_index=index, file_count=total,
        )

    original_plan = build_plan(original, video_path, {})
    unchanged = (not plan.reencode and plan.container == original_plan.container
                 and not any(options.get(k) for k in ('meta_title', 'meta_author', 'meta_comment')))
    use_gpu = bool(plan.reencode and config.FFMPEG_USE_GPU)
    try:
        if unchanged:
            shutil.copyfile(video_path, working)
        else:
            execute(use_gpu)
    except RuntimeError as exc:
        # 仅硬件故障改用同编码的 CPU 实现；容器不兼容不改变其他流。
        if use_gpu and re.search(r'Cannot load.*(?:cuda|nvidia)|No capable devices|OpenEncodeSessionEx failed|InitializeEncoder failed|CUDA_ERROR|Driver does not support', str(exc), re.I):
            execute(False)
        else:
            raise RuntimeError(f'{exc}\n为保留原音轨、字幕及附件，本任务不会自动丢弃或转码它们；请尝试 MKV 或保持原容器。') from exc

    if to_bool(options.get('second_pass_reencode')):
        second = run_dir / f'{video_path.stem}_pass2.{plan.suffix}'
        run_ffmpeg(['ffmpeg', '-y', '-noautorotate', '-i', str(working),
                    *stream_args(original, plan),
                    *encoding_args(original, plan, options, duration),
                    *ffmpeg_metadata_args(metadata, plan.container), '-f', plan.container, str(second)])
        second.replace(working)

    emit_progress(task_id, progress_end, f'转换视频 {index}/{total}: 恢复日期和元数据并核对媒体流',
                  file_index=index, file_count=total, stage='finalize')
    modified_ms = (options.get('source_file_times') or {}).get(video_path.name)
    report = restore_metadata(video_path, working, metadata, plan.container, options, modified_ms, unchanged=unchanged)
    report['stream_normalizations'] = validate_streams(original, probe_media(working), plan)
    working.with_name(working.name + '.metadata.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    working.replace(final)
    working.with_name(working.name + '.metadata.json').replace(final.with_name(final.name + '.metadata.json'))
    return final
