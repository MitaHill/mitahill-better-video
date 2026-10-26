import copy
import io
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from werkzeug.datastructures import FileStorage, MultiDict

from app.src.Utils import media_mux
from app.src.Worker.pipelines.conversion.plan import build_plan, stream_args, encoding_args, validate_streams
from app.src.Worker.pipelines.conversion.metadata import creation_date, same_date
from app.src.Api.services.conversion_tasks import create_conversion_task
from app.src.Api.task_parsers.conversion import parse_conversion_task_params


class ConversionPlanTests(unittest.TestCase):
    def setUp(self):
        self.info = {'format': {'format_name': 'matroska', 'duration': '10'}, 'chapters': [], 'streams': [
            {'index': 0, 'codec_type': 'video', 'codec_name': 'h264', 'disposition': {'default': 1}},
            {'index': 1, 'codec_type': 'audio', 'codec_name': 'aac', 'tags': {'language': 'eng'}},
            {'index': 2, 'codec_type': 'audio', 'codec_name': 'aac', 'tags': {'language': 'jpn'}},
            {'index': 3, 'codec_type': 'subtitle', 'codec_name': 'subrip', 'disposition': {'forced': 1}},
        ]}

    def test_default_plan_copies_every_stream(self):
        plan = build_plan(self.info, Path('source.mkv'), {})
        self.assertFalse(plan.reencode)
        self.assertEqual(plan.container, 'matroska')
        args = stream_args(self.info, plan)
        self.assertEqual([args[i+1] for i, v in enumerate(args) if v == '-map'], ['0:0', '0:1', '0:2', '0:3'])
        self.assertIn('-map_chapters', args)

    def test_only_requested_codec_changes(self):
        plan = build_plan(self.info, Path('source.mkv'), {'video_codec': 'h265'})
        self.assertTrue(plan.reencode)
        self.assertEqual(plan.codec, 'h265')
        same = copy.deepcopy(self.info)
        same['streams'][0]['codec_name'] = 'hevc'
        self.assertFalse(build_plan(same, Path('source.mkv'), {'video_codec': 'h265'}).reencode)

    def test_main_video_can_follow_audio_and_keeps_ten_bit_format(self):
        info = copy.deepcopy(self.info)
        info['streams'][0], info['streams'][1] = info['streams'][1], info['streams'][0]
        info['streams'][0]['index'] = 0
        info['streams'][1].update(index=1, pix_fmt='yuv420p10le')
        plan = build_plan(info, Path('source.mkv'), {'video_codec': 'h265'})
        args = encoding_args(info, plan, {}, 10)
        self.assertEqual(plan.video_index, 1)
        self.assertIn('-c:1', args)
        self.assertIn('yuv420p10le', args)
        self.assertNotIn('-r:1', args)

    def test_missing_track_or_changed_flags_fail(self):
        plan = build_plan(self.info, Path('source.mkv'), {})
        for mutate in (lambda x: x['streams'].pop(), lambda x: x['streams'][3]['disposition'].update(forced=0)):
            result = copy.deepcopy(self.info)
            mutate(result)
            with self.assertRaises(RuntimeError):
                validate_streams(self.info, result, plan)

    def test_probe_failure_is_not_no_audio(self):
        with patch.object(media_mux.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'bad input')):
            with self.assertRaisesRegex(RuntimeError, '探测'):
                media_mux.probe_media('broken.mp4')
        with patch.object(media_mux.subprocess, 'run', side_effect=subprocess.TimeoutExpired('ffprobe', 30)):
            with self.assertRaisesRegex(RuntimeError, '探测'):
                media_mux.probe_media('slow.mp4')

    def test_container_creation_is_not_claimed_as_camera_time(self):
        key, value = creation_date({'ASF:CreationDate': '2012:01:07 10:36:43Z'})
        self.assertEqual(key, 'ASF:CreationDate')
        self.assertTrue(same_date(value, '2012-01-07T10:36:43+00:00'))
        self.assertFalse(same_date(value, '2012-01-07T10:36:43'))

    def test_api_defaults_preserve_and_accept_fractional_frame_rates(self):
        params = parse_conversion_task_params({'frame_rate': '29.97'})
        self.assertEqual(params['output_format'], 'preserve')
        self.assertEqual(params['video_codec'], 'preserve')
        self.assertEqual(params['crf'], 0)
        self.assertEqual(params['frame_rate'], 29.97)

    def test_invalid_file_dates_rejected_before_writing(self):
        upload = FileStorage(io.BytesIO(b'fixture'), filename='source.mp4')
        req = SimpleNamespace(files=MultiDict([('media_files', upload)]),
                              form={'source_file_times': '[{"filename":"source.mp4","last_modified_ms":"NaN"}]'})
        with patch('app.src.Api.services.conversion_tasks.new_task_dirs') as create:
            task, error = create_conversion_task(req, 'test', {}, Path('unused'), Path('unused'))
        self.assertIsNone(task)
        self.assertIn('日期', error)
        create.assert_not_called()


if __name__ == '__main__':
    unittest.main()
