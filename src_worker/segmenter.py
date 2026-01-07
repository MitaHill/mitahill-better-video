import shutil
import os
import logging
from pathlib import Path
from .utils import run_ffmpeg, get_video_duration, get_video_fps
from .upscaler import build_model
import db

logger = logging.getLogger("SEGMENTER")

def process_segment(input_path, output_path, params, weights_dir, task_id, progress_base, progress_scale):
    """Processes a single video segment: extract frames, upscale, and combine."""
    logger.info(f"Segment Process: {input_path.name}")
    run_dir = input_path.parent
    frames_in = run_dir / "frames_in"
    frames_out = run_dir / "frames_out"
    audio_path = run_dir / "audio.m4a"

    try:
        # Cleanup old leftovers
        for d in [frames_in, frames_out]:
            if d.exists(): shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)

        # 1. Extract Audio
        logger.debug(f"[{input_path.name}] Extracting audio...")
        run_ffmpeg(["ffmpeg", "-y", "-i", str(input_path), "-vn", "-acodec", "copy", str(audio_path)])

        # 2. Extract Frames
        logger.debug(f"[{input_path.name}] Extracting frames...")
        run_ffmpeg(["ffmpeg", "-y", "-i", str(input_path), "-q:v", "2", "-f", "image2", str(frames_in / "f_%06d.jpg")])

        # 3. Upscale
        logger.info(f"[{input_path.name}] Loading model: {params['model_name']}")
        upsampler = build_model(
            params['model_name'], params['upscale'], params['tile'], params['tile_pad'],
            params['fp16'], weights_dir, params.get('denoise_strength')
        )

        frame_list = sorted(list(frames_in.glob("*.jpg")))
        total_frames = len(frame_list)
        logger.info(f"[{input_path.name}] Total frames to upscale: {total_frames}")

        for i, frame_path in enumerate(frame_list):
            out_frame = frames_out / frame_path.name
            upsampler.enhance_to_file(frame_path, out_frame, params['upscale'])
            
            # Progress Update
            if i % 10 == 0 or i == total_frames - 1:
                progress = progress_base + int(((i + 1) / total_frames) * progress_scale)
                db.update_task_status(task_id, "PROCESSING", progress, f"Upscaling {input_path.name}: {i+1}/{total_frames} frames")
                logger.debug(f"[{input_path.name}] Progress: {i+1}/{total_frames} frames upscaled.")

        # 4. Recombine
        fps = get_video_fps(input_path)
        logger.info(f"[{input_path.name}] Combining frames at {fps} FPS...")
        
        # Use simple combine if no audio, or combine with audio
        cmd = [
            "ffmpeg", "-y", "-framerate", str(fps), "-i", str(frames_out / "f_%06d.jpg")
        ]
        
        if audio_path.exists() and params.get('keep_audio', True):
            logger.debug(f"[{input_path.name}] Including audio in combination.")
            cmd += ["-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0?", "-c:a", "copy"]
        
        cmd += [
            "-c:v", "libx264", "-crf", str(params.get('crf', 18)), 
            "-pix_fmt", "yuv420p", str(output_path)
        ]
        run_ffmpeg(cmd)
        logger.info(f"[SUCCESS] Segment completed: {output_path.name}")

    finally:
        # Cleanup
        logger.debug(f"[{input_path.name}] Cleaning up temporary frames.")
        shutil.rmtree(frames_in, ignore_errors=True)
        shutil.rmtree(frames_out, ignore_errors=True)
        if audio_path.exists(): audio_path.unlink()