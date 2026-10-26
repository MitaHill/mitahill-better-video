import json
import math
import os
import re
import subprocess
from datetime import datetime

from app.src.Utils.media_mux import probe_media


DATE_TAGS = {'DateTimeOriginal', 'CreateDate', 'ModifyDate', 'CreationDate',
             'TrackCreateDate', 'TrackModifyDate', 'MediaCreateDate', 'MediaModifyDate',
             'DateCreated', 'DateTimeUTC', 'OffsetTimeOriginal', 'SubSecTimeOriginal'}
DESCRIPTIVE_TAGS = {'Make', 'Model', 'CameraModelName', 'SerialNumber', 'LensModel',
                    'GPSCoordinates', 'GPSLatitude', 'GPSLongitude', 'GPSAltitude',
                    'GPSLatitudeRef', 'GPSLongitudeRef', 'GPSAltitudeRef',
                    'LocationInformation', 'LocationName', 'Location',
                    'Title', 'Artist', 'Author', 'Comment', 'Description', 'Copyright'}


def unset_date(key, value):
    if not isinstance(value, str):
        return False
    if value.startswith('0000:'):
        return True
    group, tag = key.split(':', 1)
    # Debian 的旧版 ExifTool 没有 StrictDate，零值会显示为 1904 年。
    binary_date = group == 'QuickTime' or re.fullmatch(r'Track\d+', group)
    return bool(binary_date and tag in DATE_TAGS
                and value in {'1904:01:01 00:00:00', '1904:01:01 00:00:00+00:00'})


def exiftool(*args):
    try:
        result = subprocess.run(['exiftool', *map(str, args)], capture_output=True,
                                text=True, timeout=120, env=dict(os.environ, TZ='UTC'))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f'元数据工具无法运行: {exc}') from exc
    if result.returncode:
        raise RuntimeError(f'元数据处理失败: {result.stderr.strip()}')
    return result.stdout


def read_metadata(path):
    # QuickTime 的零值表示未设置日期，StrictDate 防止将它解释成纪元日期。
    payload = json.loads(exiftool('-json', '-G1', '-s', '-n', '-api', 'QuickTimeUTC=1',
                                 '-api', 'StrictDate=1', path))
    if not payload:
        raise RuntimeError('无法读取原文件元数据')
    return {key: value for key, value in payload[0].items()
            if ':' in key and key.split(':', 1)[0] not in {'System', 'File', 'Composite', 'ExifTool'}
            and key.split(':')[-1] in DATE_TAGS | DESCRIPTIVE_TAGS
            and not unset_date(key, value)}


def creation_date(metadata):
    for key in ('ExifIFD:DateTimeOriginal', 'Keys:CreationDate', 'XMP-exif:DateTimeOriginal',
                'XMP-xmp:CreateDate', 'QuickTime:CreateDate', 'Matroska:DateTimeOriginal',
                'Matroska:DateTimeUTC', 'RIFF:DateTimeOriginal', 'ASF:CreationDate'):
        value = metadata.get(key)
        if value and not str(value).startswith('0000:'):
            return key, str(value)
    return None, None


def iso_date(value):
    return re.sub(r'^(\d{4}):(\d\d):(\d\d) ', r'\1-\2-\3T', str(value))


def same_date(left, right):
    try:
        dates = [datetime.fromisoformat(iso_date(v).replace('Z', '+00:00')) for v in (left, right)]
        # 无时区值只与无时区值比较，不把本地拍摄日期猜成 UTC。
        if bool(dates[0].tzinfo) != bool(dates[1].tzinfo):
            return False
        return abs((dates[0] - dates[1]).total_seconds()) < 1
    except (ValueError, TypeError):
        return str(left) == str(right)


def ffmpeg_metadata_args(metadata, container):
    key, value = creation_date(metadata)
    args = []
    if value:
        timestamp = iso_date(value)
        # QuickTime 数字日期按规范是 UTC；没有时区的相机字符串不擅自猜时区。
        if key.startswith(('QuickTime:', 'ASF:')) and not re.search(r'(Z|[+-]\d\d:?\d\d)$', timestamp):
            timestamp += 'Z'
        if re.search(r'(Z|[+-]\d\d:?\d\d)$', timestamp):
            args += ['-metadata', f'creation_time={timestamp}']
    if container in {'mp4', 'mov'}:
        args += ['-movflags', '+use_metadata_tags']
    return args


def restore_metadata(source, output, original, container, options, modified_ms=None, *, unchanged=False):
    report = {'source': source.name, 'metadata': original, 'file_modified_ms': modified_ms,
              'limitations': ['浏览器直接下载无法保证本机文件创建日期；ZIP 可保留解压后的修改日期。']}
    if unchanged:
        report['unchanged_media_bytes'] = True
    elif container in {'mp4', 'mov'}:
        # 只复制描述性字段和日期，不把原编码器、码率或分辨率写回新视频。
        args = ['-overwrite_original', '-P', '-api', 'QuickTimeUTC=1', '-TagsFromFile', source]
        args += [f'-{key}' for key in original if not key.startswith('ASF:')]
        source_key, date = creation_date(original)
        if date and source_key == 'ASF:CreationDate':
            args += [f'-QuickTime:CreateDate={date}', f'-QuickTime:ModifyDate={date}',
                     f'-TrackCreateDate={date}', f'-TrackModifyDate={date}',
                     f'-MediaCreateDate={date}', f'-MediaModifyDate={date}']
        # 用户显式填写的字段优先于原字段。
        for option, tag in (('meta_title', 'Title'), ('meta_author', 'Artist'), ('meta_comment', 'Comment')):
            if str(options.get(option) or '').strip():
                args += [f'-{tag}={options[option].strip()}']
        if original or len(args) > 7:
            exiftool(*args, output)
        result = read_metadata(output)
        overrides = {'Title': 'meta_title', 'Artist': 'meta_author', 'Author': 'meta_author', 'Comment': 'meta_comment'}
        for key, value in original.items():
            tag = key.split(':')[-1]
            if key == 'ASF:CreationDate' or options.get(overrides.get(tag, '')):
                continue
            if key in result and str(result[key]) == str(value):
                continue
            if key.startswith('Keys:'):
                raise RuntimeError(f'元数据 {key} 未在原位置保留，拒绝交付')
            # 跨格式写入时同一字段可能迁移到另一个标准组。
            if not any(k.split(':')[-1] == tag and (same_date(v, value) if tag in DATE_TAGS else str(v) == str(value)) for k, v in result.items()):
                raise RuntimeError(f'元数据 {key} 未保留，拒绝交付；请尝试保持原容器')
        if source_key == 'ASF:CreationDate':
            # FILETIME 有 UTC 时区；输出电影头和每个轨道都必须得到有效日期。
            dates = [v for k, v in result.items() if k.endswith((':CreateDate', ':TrackCreateDate', ':MediaCreateDate'))]
            if not dates or not all(same_date(v, date) for v in dates):
                raise RuntimeError('ASF 原始创建日期未完整写入 MP4 文件及轨道')
    elif original:
        actual = read_metadata(output)
        fields = probe_media(output).get('format', {}).get('tags', {})
        for key, value in original.items():
            tag = key.split(':')[-1]
            if tag in DESCRIPTIVE_TAGS and not options.get({'Title': 'meta_title', 'Artist': 'meta_author', 'Comment': 'meta_comment'}.get(tag, '')):
                values = [v for k, v in actual.items() if k.split(':')[-1] == tag]
                values += [v for k, v in fields.items() if k.lower() == tag.lower()]
                if str(value) not in map(str, values):
                    raise RuntimeError(f'目标容器无法保留 {key}，请尝试 MP4、MOV 或保持原容器')
        _, expected = creation_date(original)
        if expected:
            _, date = creation_date(actual)
            date = date or fields.get('creation_time') or fields.get('date')
            if not date or not same_date(date, expected):
                raise RuntimeError('目标容器无法保留原日期，请选择 MP4、MOV 或保持原容器')
    source_key, date = creation_date(original)
    if date:
        report['date_source'] = source_key
        report['date_value'] = date
        report['date_meaning'] = '容器创建时间' if source_key == 'ASF:CreationDate' else '原文件日期字段'
    if modified_ms is not None:
        seconds = float(modified_ms) / 1000
        if not math.isfinite(seconds) or seconds < 0 or seconds > 4102444800:
            raise RuntimeError('原文件修改日期无效')
        os.utime(output, (seconds, seconds))
    return report
