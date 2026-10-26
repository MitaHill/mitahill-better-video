import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.src.Utils import media_mux
from app.src.Utils.ffmpeg import FFmpegError


class AudioPolicyTests(unittest.TestCase):
    def test_container_policies(self):
        for container in ("mp4", "mov"):
            self.assertEqual(media_mux.choose_audio_args({"codec_name": "aac", "channels": 2}, container), ["-c:a", "copy"])
            self.assertEqual(media_mux.choose_audio_args({"codec_name": "wmav2", "channels": 2}, container), ["-c:a", "aac", "-b:a", "128k"])
        self.assertEqual(media_mux.choose_audio_args({"codec_name": "wmav2"}, "mkv"), ["-c:a", "copy"])
        self.assertEqual(media_mux.choose_audio_args({"codec_name": "mp3", "channels": 2}, "avi"), ["-c:a", "copy"])
        self.assertEqual(media_mux.choose_audio_args({"codec_name": "aac", "channels": 2}, "avi"), ["-c:a", "libmp3lame", "-b:a", "128k"])
        self.assertEqual(media_mux.choose_audio_args(None, "mp4"), [])

    def test_multichannel_is_not_silently_downmixed(self):
        self.assertIn("384k", media_mux.choose_audio_args({"codec_name": "ac3", "channels": 6}, "mp4"))
        with self.assertRaisesRegex(RuntimeError, "AVI"):
            media_mux.choose_audio_args({"codec_name": "ac3", "channels": 6}, "avi")

    def test_probe_failure_is_not_no_audio(self):
        with patch.object(media_mux.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "invalid input")):
            with self.assertRaisesRegex(RuntimeError, "探测"):
                media_mux.probe_media("broken.mp4")
        with patch.object(media_mux.subprocess, "run", side_effect=subprocess.TimeoutExpired("ffprobe", 30)):
            with self.assertRaisesRegex(RuntimeError, "探测"):
                media_mux.probe_media("slow.mp4")

    def test_missing_encoder_fails_before_mux(self):
        with patch.object(media_mux.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "Encoders:\n", "")):
            with self.assertRaisesRegex(RuntimeError, "aac"):
                media_mux.check_audio_encoder(["-c:a", "aac", "-b:a", "128k"])

    def test_only_audio_container_failure_retries_once(self):
        error = FFmpegError(1, "Could not find tag for codec wmav2 in stream #1, codec not currently supported in container", "first.log")
        audio = {"codec_name": "wmav2", "channels": 2}
        with patch.object(media_mux, "run_ffmpeg", side_effect=[error, None]) as run, patch.object(media_mux, "check_audio_encoder"):
            media_mux.mux_audio("encoded.mp4", "source.mp4", "out.mkv", audio, ["-c:a", "copy"])
        self.assertEqual(run.call_count, 2)
        self.assertIn("aac", run.call_args[0][0])
        self.assertEqual(run.call_args[0][0][run.call_args[0][0].index("-c:v") + 1], "copy")

        for stderr in ("No space left on device", "Permission denied", "Invalid data found when processing input", "Could not find tag for codec h264 in stream #0, codec not currently supported in container"):
            with self.subTest(stderr=stderr), patch.object(media_mux, "run_ffmpeg", side_effect=FFmpegError(1, stderr, "error.log")) as run:
                with self.assertRaises(FFmpegError):
                    media_mux.mux_audio("encoded.mp4", "source.mp4", "out.mkv", audio, ["-c:a", "copy"])
                self.assertEqual(run.call_count, 1)

        with patch.object(media_mux, "run_ffmpeg", side_effect=error) as run, patch.object(media_mux, "check_audio_encoder"):
            with self.assertRaises(FFmpegError):
                media_mux.mux_audio("encoded.mp4", "source.mp4", "out.mkv", audio, ["-c:a", "copy"])
            self.assertEqual(run.call_count, 2)

    def test_validation_rejects_missing_audio(self):
        payload = {"streams": [{"codec_type": "video"}], "format": {"duration": "1"}}
        with patch.object(media_mux, "probe_media", return_value=payload):
            with self.assertRaisesRegex(RuntimeError, "音轨"):
                media_mux.validate_media_output("out.mp4", expect_audio=True)
            media_mux.validate_media_output("out.mp4", expect_audio=False)


class AudioMuxIntegrationTests(unittest.TestCase):
    def setUp(self):
        # CI 的应用镜像必须具备这些工具；缺失应失败而非跳过回归。
        self.assertIsNotNone(shutil.which("ffmpeg"))
        self.assertIsNotNone(shutil.which("ffprobe"))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.video = self.root / "encoded.mp4"
        self.ffmpeg("-f", "lavfi", "-i", "color=size=64x64:rate=10", "-t", "1", "-c:v", "libx264", str(self.video))

    def ffmpeg(self, *args):
        return subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], capture_output=True, text=True, check=True)

    def test_disguised_asf_old_mux_fails_new_mux_preserves_audio(self):
        source = self.root / "disguised.mp4"
        self.ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "1", "-ac", "2", "-c:a", "wmav2", "-f", "asf", str(source))
        output = self.root / "out.mp4"
        old = subprocess.run(["ffmpeg", "-y", "-i", str(self.video), "-i", str(source), "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", str(output)], capture_output=True, text=True)
        self.assertNotEqual(old.returncode, 0)
        self.assertIn("codec not currently supported in container", old.stderr)
        info = media_mux.probe_media(source)
        self.assertIn("asf", info["format"]["format_name"])
        audio = media_mux.first_audio_stream(info)
        args = media_mux.choose_audio_args(audio, "mp4")
        media_mux.check_audio_encoder(args)
        media_mux.mux_audio(self.video, source, output, audio, args)
        media_mux.validate_media_output(output, expect_audio=True)
        result = media_mux.probe_media(output)
        self.assertEqual(media_mux.first_audio_stream(result)["codec_name"], "aac")
        self.assertEqual(media_mux.first_audio_stream(result)["channels"], 2)
        self.assertAlmostEqual(float(result["format"]["duration"]), 1, delta=0.15)
        self.ffmpeg("-i", str(output), "-f", "null", "-")

    def test_aac_all_containers_and_no_audio(self):
        source = self.root / "source.m4a"
        self.ffmpeg("-f", "lavfi", "-i", "sine=frequency=440", "-t", "1", "-c:a", "aac", str(source))
        audio = media_mux.first_audio_stream(media_mux.probe_media(source))
        for container, codec in (("mp4", "aac"), ("mov", "aac"), ("mkv", "aac"), ("avi", "mp3")):
            with self.subTest(container=container):
                output = self.root / f"output.{container}"
                args = media_mux.choose_audio_args(audio, container)
                media_mux.check_audio_encoder(args)
                media_mux.mux_audio(self.video, source, output, audio, args)
                media_mux.validate_media_output(output, expect_audio=True)
                self.assertEqual(media_mux.first_audio_stream(media_mux.probe_media(output))["codec_name"], codec)
                self.ffmpeg("-i", str(output), "-f", "null", "-")
        silent = self.root / "silent.mp4"
        media_mux.mux_audio(self.video, self.video, silent, None, [])
        media_mux.validate_media_output(silent, expect_audio=False)
        self.assertIsNone(media_mux.first_audio_stream(media_mux.probe_media(silent)))


if __name__ == "__main__":
    unittest.main()
