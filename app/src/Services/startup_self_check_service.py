import gc
import logging
import shutil
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from app.src.Audio.enhancer import AudioEnhancer
from app.src.Media.upscaler import build_model
from app.src.Utils.ffmpeg import run_ffmpeg
from app.src.Worker.pipelines.transcription.whisper_engine import ENGINE


logger = logging.getLogger("STARTUP_SELF_CHECK")


class StartupSelfCheckService:
    def __init__(self, *, config_payload):
        self.config_payload = config_payload or {}
        self.enabled = bool(((self.config_payload.get("runtime") or {}).get("startup_self_check_enabled")))
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.workspace = Path("/workspace/storage/selfcheck") / f"startup_{stamp}"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.sample_video = self.workspace / "sample_black_beep.mp4"

    @staticmethod
    def _cleanup_memory():
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def run_if_enabled(self):
        if not self.enabled:
            logger.info("Startup self-check disabled, skip.")
            return
        logger.info("Startup self-check enabled, begin full checks.")
        self.run()

    def run(self):
        try:
            self._generate_sample_video()
            self._check_conversion()
            self._check_enhancement()
            self._check_transcription()
            logger.info("Startup self-check completed successfully: 视频增强 / 视频转换 / 视频转录")
        except Exception as exc:
            logger.error("Startup self-check failed: %s", exc)
            logger.error("Startup self-check traceback:\n%s", traceback.format_exc())
            raise RuntimeError(f"启动自检失败: {exc}") from exc
        finally:
            self._cleanup_memory()

    def _generate_sample_video(self):
        logger.info("Self-check [视频转换] 生成黑屏+哔声音频测试视频...")
        run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=640x360:r=25:d=3",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=1000:sample_rate=48000:duration=3",
                "-filter_complex",
                "[1:a]aformat=sample_fmts=s16:channel_layouts=stereo,volume=0.2[aout]",
                "-map",
                "0:v:0",
                "-map",
                "[aout]",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                str(self.sample_video),
            ]
        )
        if not self.sample_video.exists():
            raise RuntimeError("测试视频生成失败")

    def _check_conversion(self):
        logger.info("Self-check [视频转换] 执行转换验证...")
        output_file = self.workspace / "conversion" / "converted.mp4"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(self.sample_video),
                "-r",
                "24",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-ac",
                "2",
                str(output_file),
            ]
        )
        if not output_file.exists():
            raise RuntimeError("视频转换自检失败：未生成输出文件")

    def _check_enhancement(self):
        logger.info("Self-check [视频增强] 执行快速超分与音频增强验证...")
        output_dir = self.workspace / "enhancement"
        output_dir.mkdir(parents=True, exist_ok=True)
        frame_path = output_dir / "frame.png"
        upscaled_path = output_dir / "frame_upscaled.png"
        audio_input = output_dir / "audio_input.wav"
        audio_output = output_dir / "audio_enhanced.wav"
        weights_dir = Path("/workspace/app/models/video")

        run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(self.sample_video),
                "-vf",
                "select=eq(n\\,0)",
                "-vframes",
                "1",
                str(frame_path),
            ]
        )
        if not frame_path.exists():
            raise RuntimeError("视频增强自检失败：无法提取测试帧")

        upsampler = build_model(
            model_name="realesr-general-x4v3",
            scale=2,
            tile=64,
            tile_pad=10,
            fp16=True,
            weights_dir=weights_dir,
            denoise_strength=0.5,
        )
        img = Image.open(frame_path).convert("RGB")
        out, _ = upsampler.enhance(np.array(img)[:, :, ::-1], outscale=2)
        Image.fromarray(out[:, :, ::-1]).save(upscaled_path)
        if not upscaled_path.exists():
            raise RuntimeError("视频增强自检失败：超分输出不存在")

        run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(self.sample_video),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "44100",
                "-acodec",
                "pcm_s16le",
                str(audio_input),
            ]
        )
        enhancer = AudioEnhancer()
        enhancer.process(audio_input, audio_output)
        if not audio_output.exists():
            raise RuntimeError("视频增强自检失败：音频增强输出不存在")

        del upsampler
        self._cleanup_memory()

    def _check_transcription(self):
        logger.info("Self-check [视频转录] 执行默认模型转录验证...")
        output_dir = self.workspace / "transcription"
        output_dir.mkdir(parents=True, exist_ok=True)
        audio_input = output_dir / "audio_16k.wav"
        run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(self.sample_video),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-acodec",
                "pcm_s16le",
                str(audio_input),
            ]
        )
        transcription = self.config_payload.get("transcription") or {}
        runtime = self.config_payload.get("runtime") or {}
        backend = str(transcription.get("backend") or "faster_whisper").strip().lower()
        model_name = str(transcription.get("active_model") or "large-v3").strip().lower()
        runtime_mode = str(runtime.get("transcribe_runtime_mode") or "parallel").strip().lower()

        result = ENGINE.transcribe(
            audio_input,
            backend=backend,
            model_name=model_name,
            language="auto",
            temperature=0.0,
            beam_size=1,
            best_of=1,
            runtime_mode=runtime_mode,
            task_id="startup_self_check",
        )
        if not isinstance(result, dict):
            raise RuntimeError("视频转录自检失败：转录结果格式异常")
        segment_count = len(result.get("segments") or [])
        logger.info(
            "Self-check [视频转录] 通过，backend=%s, model=%s, segments=%s",
            backend,
            model_name,
            segment_count,
        )
        ENGINE.finalize_task(runtime_mode=runtime_mode)
        self._cleanup_memory()

    def cleanup_workspace(self):
        try:
            shutil.rmtree(self.workspace, ignore_errors=True)
        except Exception:
            logger.warning("Failed to cleanup self-check workspace: %s", self.workspace, exc_info=True)
