import logging
import subprocess
import shutil
from pathlib import Path

from app.src.Utils.ffmpeg import run_ffmpeg

logger = logging.getLogger("AUDIO_DENOISER")


def apply_pre_denoise(mode, input_path, output_path):
    input_path = Path(input_path)
    output_path = Path(output_path)
    mode = (mode or "off").lower()
    if output_path.exists() and output_path.is_dir():
        raise RuntimeError(f"Output path is a directory: {output_path}")

    if mode == "off":
        run_ffmpeg(["ffmpeg", "-y", "-i", str(input_path), str(output_path)])
        return

    if mode == "speech_enhance":
        model_dir = Path("/root/.cache/DeepFilterNet/DeepFilterNet2")
        if not model_dir.exists():
            logger.error("DeepFilterNet2 cache missing at %s", model_dir)
            raise FileNotFoundError("DeepFilterNet2 cache missing; rebuild image.")
        temp_48k = output_path.with_suffix(".48k.wav")
        temp_out_dir = output_path.parent / f"{output_path.stem}_dfn"
        if temp_out_dir.exists():
            if temp_out_dir.is_dir():
                for item in temp_out_dir.iterdir():
                    item.unlink(missing_ok=True)
                temp_out_dir.rmdir()
            else:
                temp_out_dir.unlink(missing_ok=True)
        run_ffmpeg([
            "ffmpeg", "-y", "-i", str(input_path),
            "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "1",
            str(temp_48k),
        ])
        cmd = [
            "python3", "-m", "df.enhance",
            "-m", "DeepFilterNet2",
            str(temp_48k),
            "-o", str(temp_out_dir),
        ]
        logger.info("Running DeepFilterNet2 pre-denoise...")
        subprocess.run(cmd, check=True)
        temp_48k.unlink(missing_ok=True)
        if temp_out_dir.exists() and temp_out_dir.is_dir():
            candidates = list(temp_out_dir.glob("*.wav"))
            if not candidates:
                raise RuntimeError("DeepFilterNet2 produced no output wav.")
            shutil.move(str(candidates[0]), str(output_path))
            for item in temp_out_dir.iterdir():
                item.unlink(missing_ok=True)
            temp_out_dir.rmdir()
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
