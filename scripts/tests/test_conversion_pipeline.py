import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.src.Utils.media_mux import first_audio_stream, probe_media
from app.src.Worker.pipelines.conversion import transcode


class ConversionPipelineTests(unittest.TestCase):
    def test_wma_survives_finalization_and_second_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "disguised.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=size=320x240:rate=10",
                "-f", "lavfi", "-i", "sine=frequency=440", "-t", "1",
                "-c:v", "wmv2", "-c:a", "wmav2", "-f", "asf", str(source),
            ], capture_output=True, text=True, check=True)
            variants = (
                {},
                {"meta_title": "Audio compatibility test"},
                {"watermark_enable_text": True, "watermark_default_text": "TEST"},
                {"second_pass_reencode": True},
            )
            for index, options in enumerate(variants):
                with self.subTest(options=options):
                    run_dir = root / f"run_{index}"
                    run_dir.mkdir()
                    with patch.object(transcode, "emit_progress") as emit, patch.object(transcode.config, "FFMPEG_USE_GPU", False), patch("app.src.Worker.pipelines.conversion.progress.emit_progress"):
                        result = transcode.render_single_video("test", source, options, run_dir, 1, 1)
                    audio = first_audio_stream(probe_media(result))
                    self.assertIsNotNone(audio)
                    self.assertEqual(audio["codec_name"], "aac")
                    self.assertTrue(any("AAC" in call.args[2] for call in emit.call_args_list))
                    subprocess.run(["ffmpeg", "-v", "error", "-i", str(result), "-f", "null", "-"], capture_output=True, text=True, check=True)

    def test_probe_failure_prevents_video_encoding(self):
        with patch.object(transcode, "probe_media", side_effect=RuntimeError("媒体探测失败")), patch.object(transcode, "run_ffmpeg_with_progress") as encode:
            with self.assertRaisesRegex(RuntimeError, "探测失败"):
                transcode.render_single_video("test", Path("broken.mp4"), {}, Path("unused"), 1, 1)
            encode.assert_not_called()


if __name__ == "__main__":
    unittest.main()
