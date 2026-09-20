import subprocess
import unittest
from unittest.mock import patch

from app.src.Utils import ffmpeg


class FakeCompletedProcess:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


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

    def _fake_run(self, probe_returncode):
        """列清单永远成功，试编码按参数决定成败。"""

        def run(args, **_kwargs):
            if "-encoders" in args:
                return FakeCompletedProcess(stdout=ENCODER_LISTING)
            return FakeCompletedProcess(stderr="nvenc busy", returncode=probe_returncode)

        return run

    def test_empty_listing_is_not_cached(self):
        # ffmpeg 正常退出但没解析出任何已知编码器，同样按探测失败处理
        empty = FakeCompletedProcess(stdout="Encoders:\n V..... libvpx  VP8\n")
        with patch.object(ffmpeg.subprocess, "run", return_value=empty) as run:
            self.assertEqual(ffmpeg.get_ffmpeg_encoders(), frozenset())
            self.assertEqual(ffmpeg.get_ffmpeg_encoders(), frozenset())
            self.assertEqual(run.call_count, 2)

        with patch.object(
            ffmpeg.subprocess, "run", return_value=FakeCompletedProcess(stdout=ENCODER_LISTING)
        ):
            self.assertIn("h264_nvenc", ffmpeg.get_ffmpeg_encoders())

    def test_usable_encoder_is_probed_only_once(self):
        with patch.object(ffmpeg.subprocess, "run", side_effect=self._fake_run(0)) as run:
            self.assertEqual(ffmpeg.get_available_output_codecs(), ["h264", "h265"])
            after_first = run.call_count
            self.assertEqual(ffmpeg.get_available_output_codecs(), ["h264", "h265"])
            self.assertEqual(run.call_count, after_first)

    def test_unusable_encoder_is_not_cached(self):
        # NVENC 会话被占满这类瞬时失败不能永久生效，否则整个进程此后都没有可用编码器
        with patch.object(ffmpeg.subprocess, "run", side_effect=self._fake_run(1)) as run:
            self.assertEqual(ffmpeg.get_available_output_codecs(), [])
            after_first = run.call_count
            self.assertEqual(ffmpeg.get_available_output_codecs(), [])
            self.assertGreater(run.call_count, after_first)

        with patch.object(ffmpeg.subprocess, "run", side_effect=self._fake_run(0)):
            self.assertIn("h264", ffmpeg.get_available_output_codecs())


if __name__ == "__main__":
    unittest.main()
