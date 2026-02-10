import logging
from pathlib import Path

from app.src.Utils.ffmpeg import run_ffmpeg, get_audio_channels

logger = logging.getLogger("AUDIO_HAAS")


def apply_haas_effect(input_path, output_path, delay_ms, lead_channel):
    input_path = Path(input_path)
    output_path = Path(output_path)
    delay_ms = max(0, int(delay_ms))
    lead = (lead_channel or "left").lower()
    if lead not in ("left", "right"):
        lead = "left"

    channels = get_audio_channels(input_path)
    if channels <= 0:
        logger.warning("Unable to detect audio channels for %s. Skipping Haas.", input_path.name)
        run_ffmpeg(["ffmpeg", "-y", "-i", str(input_path), str(output_path)])
        return

    if lead == "left":
        delays = f"0|{delay_ms}"
    else:
        delays = f"{delay_ms}|0"

    if delay_ms <= 0:
        logger.info("Haas enabled at 0ms: forcing stereo if mono.")
        run_ffmpeg([
            "ffmpeg", "-y", "-i", str(input_path),
            "-ac", "2", "-c:a", "pcm_s16le",
            str(output_path),
        ])
        return

    if channels == 1:
        filt = f"pan=stereo|c0=c0|c1=c0,adelay={delays}"
    else:
        filt = f"adelay={delays}"
    logger.info("Applying Haas effect: %sms (%s first)", delay_ms, lead)
    run_ffmpeg([
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", filt, "-ac", "2", "-c:a", "pcm_s16le",
        str(output_path),
    ])
