import logging

import numpy as np
from PIL import Image

from app.src.Config import settings as config
from app.src.Utils.ffmpeg import get_video_duration, run_ffmpeg

logger = logging.getLogger("PROCESSOR")


def generate_previews(input_path, run_dir, upsampler, upscale_factor):
    """Generate original and upscaled preview images using loaded model."""
    p_orig = run_dir / "preview_original.jpg"
    p_ups = run_dir / "preview_upscaled.jpg"

    try:
        if not p_orig.exists():
            duration = get_video_duration(input_path)
            seek_time = max(0.1, min(1.0, duration * 0.1)) if duration > 0 else 0.0
            hwaccel = ["-hwaccel", "cuda"] if config.FFMPEG_USE_GPU else []
            cmd = [
                "ffmpeg",
                "-y",
                *hwaccel,
                "-i",
                str(input_path),
                "-ss",
                f"{seek_time:.2f}",
                "-vframes",
                "1",
                "-q:v",
                "2",
                str(p_orig),
            ]
            fallback = None
            if hwaccel:
                fallback = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(input_path),
                    "-ss",
                    f"{seek_time:.2f}",
                    "-vframes",
                    "1",
                    "-q:v",
                    "2",
                    str(p_orig),
                ]
            run_ffmpeg(cmd, fallback_args=fallback)

        if p_orig.exists() and not p_ups.exists() and upsampler:
            img = Image.open(p_orig).convert("RGB")
            output, _ = upsampler.enhance(np.array(img)[:, :, ::-1], outscale=upscale_factor)
            out_img = Image.fromarray(output[:, :, ::-1])
            out_img.save(p_ups)
            logger.info("Previews generated successfully.")
    except Exception as exc:
        logger.warning("Preview generation failed: %s", exc)
