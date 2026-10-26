import json
import struct
import subprocess
import tempfile
import unittest
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app.src.Utils.media_mux import probe_media
from app.src.Worker.pipelines.conversion import transcode
from app.src.Worker.pipelines.conversion.metadata import read_metadata, same_date
from app.src.Worker.pipelines.conversion.packaging import zip_paths


class ConversionPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def ffmpeg(self, *args):
        return subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *map(str, args)],
                              capture_output=True, text=True, check=True)

    def render(self, source, options):
        run_dir = self.root / f'run_{len(list(self.root.glob("run_*")))}'
        run_dir.mkdir()
        with patch.object(transcode, 'emit_progress'), patch.object(transcode.config, 'FFMPEG_USE_GPU', False), patch('app.src.Worker.pipelines.conversion.progress.emit_progress'):
            return transcode.render_single_video('test', source, options, run_dir, 1, 1)

    def make_mp4(self, name='source.mp4', date=True):
        source = self.root / name
        cmd = ['-f', 'lavfi', '-i', 'testsrc2=size=160x120:rate=30000/1001',
               '-f', 'lavfi', '-i', 'sine=frequency=440', '-t', '1',
               '-c:v', 'libx264', '-c:a', 'aac']
        if date:
            cmd += ['-metadata', 'creation_time=2020-02-03T04:05:06Z']
        self.ffmpeg(*cmd, source)
        return source

    def test_date_survives_watermark_metadata_and_second_pass(self):
        source = self.make_mp4()
        original = read_metadata(source)
        for options in ({}, {'meta_title': 'New title'},
                        {'video_codec': 'h265', 'watermark_enable_text': True, 'watermark_default_text': 'TEST'},
                        {'video_codec': 'h265', 'second_pass_reencode': True}):
            with self.subTest(options=options):
                result = self.render(source, options)
                actual = read_metadata(result)
                if not options:
                    self.assertEqual(result.read_bytes(), source.read_bytes())
                self.assertTrue(same_date(actual['QuickTime:CreateDate'], original['QuickTime:CreateDate']))
                self.assertEqual(probe_media(result)['streams'][0]['codec_name'], 'hevc' if options.get('video_codec') else 'h264')
                self.ffmpeg('-i', result, '-f', 'null', '-')

    def test_asf_header_date_is_recovered_and_wma_is_not_silently_changed(self):
        source = self.root / 'disguised.mp4'
        self.ffmpeg('-f', 'lavfi', '-i', 'color=size=160x120:rate=10', '-f', 'lavfi', '-i', 'sine=frequency=440',
                    '-t', '1', '-c:v', 'wmv2', '-c:a', 'wmav2', '-f', 'asf', source)
        data = bytearray(source.read_bytes())
        offset = data.index(uuid.UUID('8cabdca1-a947-11cf-8ee4-00c00c205365').bytes_le)
        epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
        stamp = datetime(2012, 1, 7, 10, 36, 44, tzinfo=timezone.utc)
        struct.pack_into('<Q', data, offset + 48, int((stamp - epoch).total_seconds()) * 10_000_000)
        source.write_bytes(data)
        self.assertNotIn('creation_time', probe_media(source)['format'].get('tags', {}))
        kept = self.render(source, {})
        self.assertEqual(kept.suffix, '.wmv')
        with self.assertRaisesRegex(RuntimeError, 'MKV'):
            self.render(source, {'output_format': 'mp4', 'video_codec': 'h265'})
        mkv = self.render(source, {'output_format': 'mkv', 'video_codec': 'h265'})
        mkv_info = probe_media(mkv)
        self.assertIn('wmav2', [s.get('codec_name') for s in mkv_info['streams']])
        self.assertTrue(same_date(mkv_info['format']['tags']['creation_time'], '2012-01-07T10:36:44Z'))
        # 无音轨的 ASF 用来验证 ASF -> MP4 日期映射，不转换任何额外音频。
        silent = self.root / 'silent.wmv'
        self.ffmpeg('-i', source, '-map', '0:v', '-c', 'copy', '-f', 'asf', silent)
        data = bytearray(silent.read_bytes())
        offset = data.index(uuid.UUID('8cabdca1-a947-11cf-8ee4-00c00c205365').bytes_le)
        struct.pack_into('<Q', data, offset + 48, int((stamp - epoch).total_seconds()) * 10_000_000)
        silent.write_bytes(data)
        result = self.render(silent, {'output_format': 'mp4', 'video_codec': 'h265'})
        self.assertTrue(same_date(read_metadata(result)['QuickTime:CreateDate'], '2012-01-07T10:36:44Z'))
        report = json.loads(result.with_name(result.name + '.metadata.json').read_text())
        self.assertEqual(report['date_meaning'], '容器创建时间')

    def test_all_audio_subtitles_attachments_and_chapters_survive_hevc(self):
        subtitle = self.root / 'sub.srt'
        subtitle.write_text('1\n00:00:00,000 --> 00:00:00,800\nHello\n')
        attachment = self.root / 'font.txt'
        attachment.write_text('fixture attachment')
        chapters = self.root / 'chapters.txt'
        chapters.write_text(';FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=900\ntitle=Intro\n')
        source = self.root / 'multi.mkv'
        self.ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=160x120:rate=30000/1001',
                    '-f', 'lavfi', '-i', 'sine=frequency=440', '-f', 'lavfi', '-i', 'sine=frequency=880',
                    '-i', subtitle, '-i', chapters, '-map', '0:v', '-map', '1:a', '-map', '2:a', '-map', '3:s',
                    '-map_metadata', '4', '-map_chapters', '4', '-t', '1', '-c:v', 'libx264', '-c:a', 'aac', '-c:s', 'srt',
                    '-metadata:s:a:0', 'language=eng', '-metadata:s:a:1', 'language=jpn', '-disposition:s:0', 'forced',
                    '-attach', attachment, '-metadata:s:t', 'mimetype=text/plain', source)
        result = self.render(source, {'video_codec': 'h265'})
        info = probe_media(result)
        self.assertEqual([s['codec_type'] for s in info['streams']], ['video', 'audio', 'audio', 'subtitle', 'attachment'])
        self.assertEqual(info['streams'][0]['codec_name'], 'hevc')
        self.assertEqual(info['streams'][0]['avg_frame_rate'], '30000/1001')
        self.assertEqual(info['streams'][3]['disposition']['forced'], 1)
        self.assertEqual(info['chapters'][0]['tags']['title'], 'Intro')
        for stream in ('a:0', 'a:1', 's:0'):
            hashes = [self.ffmpeg('-i', path, '-map', f'0:{stream}', '-c', 'copy', '-f', 'hash', '-hash', 'sha256', '-').stdout for path in (source, result)]
            self.assertEqual(*hashes)

    def test_file_modified_time_and_zip(self):
        source = self.make_mp4(date=False)
        stamp = 1577934245000
        result = self.render(source, {'source_file_times': {source.name: stamp}})
        self.assertAlmostEqual(result.stat().st_mtime, stamp / 1000, delta=.001)
        self.assertNotIn('QuickTime:CreateDate', read_metadata(result))
        archive = self.root / 'output.zip'
        zip_paths([result], archive, result.parent)
        with zipfile.ZipFile(archive) as zf:
            extra = zf.getinfo(result.name).extra
            self.assertIn(struct.pack('<HHBI', 0x5455, 5, 1, stamp // 1000), extra)

    def test_probe_failure_prevents_encoding(self):
        with patch.object(transcode, 'probe_media', side_effect=RuntimeError('媒体探测失败')), patch.object(transcode, 'run_ffmpeg_with_progress') as encode:
            with self.assertRaisesRegex(RuntimeError, '探测失败'):
                transcode.render_single_video('test', Path('broken.mp4'), {}, self.root, 1, 1)
            encode.assert_not_called()

    def test_device_location_and_offset_date_survive(self):
        source = self.make_mp4()
        subprocess.run(['exiftool', '-overwrite_original', '-Keys:Make=Apple', '-Keys:Model=Test Camera',
                        '-Keys:GPSCoordinates=25.0 121.5', '-Keys:CreationDate=2020:02:03 12:05:06+08:00', str(source)],
                       capture_output=True, text=True, check=True)
        original = read_metadata(source)
        result = self.render(source, {'video_codec': 'h265'})
        actual = read_metadata(result)
        for key in ('Keys:Make', 'Keys:Model', 'Keys:GPSCoordinates', 'Keys:CreationDate'):
            self.assertEqual(actual[key], original[key])

    def test_explicit_mp4_with_incompatible_subtitle_fails_without_dropping_it(self):
        source = self.root / 'subtitle.mkv'
        subtitles = self.root / 'sub.srt'
        subtitles.write_text('1\n00:00:00,000 --> 00:00:00,800\nHello\n')
        self.ffmpeg('-f', 'lavfi', '-i', 'color=size=160x120:rate=10', '-i', subtitles,
                    '-t', '1', '-map', '0:v', '-map', '1:s', '-c:v', 'libx264', '-c:s', 'srt', source)
        with self.assertRaisesRegex(RuntimeError, 'MKV'):
            self.render(source, {'output_format': 'mp4'})


if __name__ == '__main__':
    unittest.main()
