import logging
import subprocess
from pathlib import Path

from app.src.Utils.ffmpeg import run_ffmpeg

logger = logging.getLogger("AUDIO_DENOISER")


def apply_pre_denoise(mode, input_path, output_path):
    input_path = Path(input_path)
    output_path = Path(output_path)
    mode = (mode or "off").lower()

    if mode == "off":
        run_ffmpeg(["ffmpeg", "-y", "-i", str(input_path), str(output_path)])
        return

    if mode == "speech_enhance":
        model_dir = Path("/root/.cache/DeepFilterNet/DeepFilterNet2")
        if not model_dir.exists():
            logger.error("DeepFilterNet2 cache missing at %s", model_dir)
            raise FileNotFoundError("DeepFilterNet2 cache missing; rebuild image.")
        temp_48k = output_path.with_suffix(".48k.wav")
        run_ffmpeg([
            "ffmpeg", "-y", "-i", str(input_path),
            "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "1",
            str(temp_48k),
        ])
        cmd = [
            "python3", "-m", "df.enhance",
            "-m", "DeepFilterNet2",
            str(temp_48k),
            "-o", str(output_path),
        ]
        logger.info("Running DeepFilterNet2 pre-denoise...")
        subprocess.run(cmd, check=True)
        temp_48k.unlink(missing_ok=True)
        return

    if mode == "vhs_hiss":
        # Target steady tape hiss with conservative spectral denoise.
        run_ffmpeg([
            "ffmpeg", "-y", "-i", str(input_path),
            "-af", "afftdn=nf=-25",
            str(output_path),
        ])
        return

    raise ValueError(f"Unknown pre-denoise mode: {mode}")
