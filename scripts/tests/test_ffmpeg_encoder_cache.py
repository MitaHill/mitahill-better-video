import subprocess
import unittest
from unittest.mock import patch

from app.src.Utils import ffmpeg


class FakeCompletedProcess:
    def __init__(self, stdout="", stderr=""):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = 0


ENCODER_LISTING = """Encoders:
 V....D h264_nvenc           NVIDIA NVENC H.264 encoder
 V....D hevc_nvenc           NVIDIA NVENC hevc encoder
 V..... libx264              libx264 H.264 encoder
"""


class FfmpegEncoderCacheTests(unittest.TestCase):
    def setUp(self):
        ffmpeg.reset_ffmpeg_encoders_cache()
        self.addCleanup(ffmpeg.reset_ffmpeg_encoders_cache)

    def test_successful_probe_runs_only_once(self):
        with patch.object(
            ffmpeg.subprocess, "run", return_value=FakeCompletedProcess(stdout=ENCODER_LISTING)
        ) as run:
            first = ffmpeg.get_ffmpeg_encoders()
            second = ffmpeg.get_ffmpeg_encoders()

        self.assertEqual(run.call_count, 1)
        self.assertEqual(first, second)
        self.assertIn("h264_nvenc", first)
        self.assertIn("hevc_nvenc", first)
        self.assertIn("libx264", first)
        # 不认识的编码器不进结果
        self.assertNotIn("Encoders:", first)

    def test_result_is_immutable(self):
        with patch.object(
            ffmpeg.subprocess, "run", return_value=FakeCompletedProcess(stdout=ENCODER_LISTING)
        ):
            encoders = ffmpeg.get_ffmpeg_encoders()
        self.assertIsInstance(encoders, frozenset)

    def test_failed_probe_is_not_cached(self):
        # 一次瞬时失败不能让整个进程此后一直认为没有可用编码器
        failing = subprocess.CalledProcessError(1, "ffmpeg")
        with patch.object(ffmpeg.subprocess, "run", side_effect=failing) as run:
            self.assertEqual(ffmpeg.get_ffmpeg_encoders(), frozenset())
            self.assertEqual(ffmpeg.get_ffmpeg_encoders(), frozenset())
            self.assertEqual(run.call_count, 2)

        with patch.object(
            ffmpeg.subprocess, "run", return_value=FakeCompletedProcess(stdout=ENCODER_LISTING)
        ) as run:
            recovered = ffmpeg.get_ffmpeg_encoders()
            self.assertEqual(run.call_count, 1)
        self.assertIn("h264_nvenc", recovered)


if __name__ == "__main__":
    unittest.main()
