import contextlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.src.Media import segmenter


class FakeUpsampler:
    """按需跳过某些帧，用来模拟单帧失败后没有写出文件的情况。"""

    def __init__(self, skip_frames=()):
        self.skip_frames = set(skip_frames)
        self.calls = []

    def enhance_to_file(self, input_path, output_path, outscale):
        self.calls.append(Path(input_path).name)
        if Path(input_path).name in self.skip_frames:
            return
        Path(output_path).write_bytes(b"sr")


class SegmentFrameIntegrityTests(unittest.TestCase):
    TOTAL_FRAMES = 3

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp_dir, True)
        self.input_path = self.tmp_dir / "seg_000.mp4"
        self.input_path.write_bytes(b"fake")
        self.output_path = self.tmp_dir / "seg_000_sr.mp4"
        # 预置 frames_in 和 audio，让 process_video_with_model 跳过抽帧和抽音轨，
        # 直接进入推理循环。
        work_dir = self.tmp_dir / "tmp_seg_000"
        frames_in = work_dir / "in"
        frames_in.mkdir(parents=True)
        for index in range(1, self.TOTAL_FRAMES + 1):
            (frames_in / f"f_{index:06d}.jpg").write_bytes(f"frame-{index}".encode())
        (work_dir / "audio.m4a").write_bytes(b"audio")

    @contextlib.contextmanager
    def _stubbed_ffmpeg(self):
        with contextlib.ExitStack() as stack:
            run_ffmpeg = stack.enter_context(patch.object(segmenter, "run_ffmpeg"))
            stack.enter_context(patch.object(segmenter, "get_video_fps", return_value=30.0))
            stack.enter_context(patch.object(segmenter, "normalize_output_codec", return_value="h264"))
            stack.enter_context(patch.object(segmenter, "get_video_encoder", return_value="libx264"))
            stack.enter_context(patch.object(segmenter.config, "FFMPEG_USE_GPU", False))
            yield run_ffmpeg

    def _process(self, upsampler):
        segmenter.process_video_with_model(
            self.input_path,
            self.output_path,
            upsampler,
            {"upscale": 2, "output_codec": "h264", "keep_audio": True},
        )

    def test_missing_frame_fails_before_recombining(self):
        upsampler = FakeUpsampler(skip_frames={"f_000002.jpg"})
        with self._stubbed_ffmpeg() as run_ffmpeg:
            with self.assertRaises(RuntimeError) as ctx:
                self._process(upsampler)
            # 缺帧时绝对不能走到合帧，否则会产出被截断的视频
            run_ffmpeg.assert_not_called()
        message = str(ctx.exception)
        self.assertIn(f"2/{self.TOTAL_FRAMES}", message)
        self.assertIn("1 missing", message)

    def test_complete_frames_proceed_to_recombine(self):
        upsampler = FakeUpsampler()
        with self._stubbed_ffmpeg() as run_ffmpeg:
            self._process(upsampler)
            run_ffmpeg.assert_called_once()
            args = run_ffmpeg.call_args[0][0]
        self.assertIn(str(self.output_path), args)
        self.assertEqual(len(upsampler.calls), self.TOTAL_FRAMES)


if __name__ == "__main__":
    unittest.main()
