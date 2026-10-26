from dataclasses import dataclass
import math
from pathlib import Path

from .common import GPU_CODEC_MAP, to_bool, to_float, to_int


@dataclass
class ConversionPlan:
    container: str
    suffix: str
    video_index: int
    codec: str | None
    reencode: bool


def build_plan(info, source, options, has_filters=False):
    video = next((s for s in info['streams'] if s.get('codec_type') == 'video'
                  and not s.get('disposition', {}).get('attached_pic')), None)
    if video is None:
        raise RuntimeError('原文件没有可转换的视频流')
    container = options.get('output_format') or 'preserve'
    if container == 'preserve':
        names = (info.get('format', {}).get('format_name') or '').split(',')
        if 'mov' in names:
            container = 'mov' if Path(source).suffix.lower() == '.mov' else 'mp4'
        else:
            container = next((name for name in ('matroska', 'avi', 'asf', 'mpegts') if name in names), '')
    container = {'mkv': 'matroska'}.get(container, container)
    suffix = {'matroska': 'mkv', 'asf': 'wmv', 'mpegts': 'ts'}.get(container, container)
    if container not in {'mp4', 'mov', 'matroska', 'avi', 'asf', 'mpegts'}:
        raise RuntimeError('无法保持原容器，请明确选择 MP4、MOV 或 MKV')
    requested = options.get('video_codec') or 'preserve'
    requested = {'hevc': 'h265'}.get(requested, requested)
    original = {'hevc': 'h265'}.get(video.get('codec_name'), video.get('codec_name'))
    changed_quality = any(to_float(options.get(k), 0) > 0 for k in ('crf', 'video_bitrate_k', 'target_size_mb'))
    reencode = (requested != 'preserve' and requested != original) or has_filters or changed_quality or to_float(options.get('frame_rate'), 0) > 0 or to_bool(options.get('second_pass_reencode'))
    codec = original if requested == 'preserve' else requested
    if reencode and codec not in GPU_CODEC_MAP:
        raise RuntimeError('修改画面需要重新编码，请明确选择 H.264 或 HEVC')
    return ConversionPlan(container, suffix, video['index'], codec, reencode)


def stream_args(info, plan, filtered_video=None):
    args = []
    for stream in info['streams']:
        index = stream['index']
        args += ['-map', filtered_video if filtered_video and index == plan.video_index else f'0:{index}']
    args += ['-c', 'copy', '-map_metadata', '0', '-map_chapters', '0']
    for index, stream in enumerate(info['streams']):
        args += [f'-map_metadata:s:{index}', f"0:s:{stream['index']}"]
        flags = '+'.join(k for k, v in stream.get('disposition', {}).items() if v)
        args += [f'-disposition:{index}', flags or '0']
    return args


def encoding_args(info, plan, options, duration, gpu=False):
    if not plan.reencode:
        return []
    index = next(i for i, s in enumerate(info['streams']) if s['index'] == plan.video_index)
    stream = info['streams'][index]
    encoder = GPU_CODEC_MAP[plan.codec][0 if gpu else 1]
    args = [f'-c:{index}', encoder]
    if gpu:
        args += ['-preset', 'p4']
    pixel_format = stream.get('pix_fmt')
    if pixel_format:
        if gpu and pixel_format in {'yuv420p10le', 'yuv420p12le'}:
            if pixel_format.endswith('12le'):
                raise RuntimeError('当前 GPU 编码无法保留 12-bit，请使用 CPU 编码')
            pixel_format = 'p010le'
        args += [f'-pix_fmt:{index}', pixel_format]
    for key in ('color_primaries', 'color_transfer', 'color_space', 'color_range'):
        value = stream.get(key)
        if value and value not in {'unknown', 'unspecified'}:
            option = 'colorspace' if key == 'color_space' else key
            args += [f'-{option}:{index}', value]
    rate = to_float(options.get('frame_rate'), 0)
    args += [f'-fps_mode:{index}', 'passthrough'] if rate <= 0 else [f'-r:{index}', str(rate)]
    size = to_float(options.get('target_size_mb'), 0)
    bitrate = to_int(options.get('video_bitrate_k'), 0) * 1000
    if size > 0:
        copied_bitrate = sum(int(s.get('bit_rate') or 0) for s in info['streams'] if s['index'] != plan.video_index)
        bitrate = max(200_000, int(size * 8 * 1024 * 1024 / duration) - copied_bitrate)
    if bitrate > 0:
        args += [f'-b:{index}', str(bitrate)]
    else:
        quality = to_int(options.get('crf'), 0) or 18
        args += ['-rc:v', 'vbr', '-cq:v', str(quality), '-b:v', '0'] if gpu else ['-crf', str(quality)]
    return args


def validate_streams(original, output, plan):
    before, after = original['streams'], output['streams']
    # MP4 章节可能生成额外的文本数据轨；额外轨可接受，原有轨必须逐个存在。
    if len(after) < len(before):
        raise RuntimeError('转换结果丢失媒体流，拒绝交付')
    for src, dst in zip(before, after):
        expected_codec = 'hevc' if plan.codec == 'h265' else plan.codec
        encoded = plan.reencode and src['index'] == plan.video_index
        if src.get('codec_type') != dst.get('codec_type') or dst.get('codec_name') != (expected_codec if encoded else src.get('codec_name')):
            raise RuntimeError(f"媒体流 {src['index']} 类型或编码未按计划保留")
        if src.get('codec_type') == 'attachment' and src.get('extradata_hash') != dst.get('extradata_hash'):
            raise RuntimeError('转换结果附件内容改变')
        for key in ('language', 'title'):
            value = src.get('tags', {}).get(key)
            if value and value != 'und' and dst.get('tags', {}).get(key) != value:
                raise RuntimeError(f"媒体流 {src['index']} 的 {key} 未保留")
        for flag in ('default', 'forced', 'attached_pic'):
            if bool(src.get('disposition', {}).get(flag)) != bool(dst.get('disposition', {}).get(flag)):
                raise RuntimeError(f"媒体流 {src['index']} 的 {flag} 标记未保留")
    source_chapters = original.get('chapters', [])
    result_chapters = output.get('chapters', [])
    if len(source_chapters) != len(result_chapters):
        raise RuntimeError('转换结果章节数量改变')
    for src, dst in zip(source_chapters, result_chapters):
        if src.get('tags', {}).get('title') != dst.get('tags', {}).get('title') or any(abs(float(src[k]) - float(dst[k])) > .01 for k in ('start_time', 'end_time')):
            raise RuntimeError('转换结果章节内容或时间改变')
    duration = float(original.get('format', {}).get('duration') or 0)
    result_duration = float(output.get('format', {}).get('duration') or 0)
    if not math.isfinite(result_duration) or result_duration <= 0:
        raise RuntimeError('转换结果时长无效')
    if duration > 0 and abs(duration - result_duration) > max(.5, duration * .001):
        raise RuntimeError('转换结果时长异常，拒绝交付')
