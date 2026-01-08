import shutil
import os
import logging
from pathlib import Path
from .utils import run_ffmpeg, get_video_fps
import db

logger = logging.getLogger("SEGMENTER")

def process_video_with_model(input_path, output_path, upsampler, params, task_id=None, p_base=0, p_scale=100):
    """
    Common logic to process a video file (or segment) using a provided upsampler model.
    Handles frame extraction, model inference, and ffmpeg recombination.
    """
    logger.info(f"Processing video: {input_path.name} -> {output_path.name}")
    
    # Create temp workspace inside the run directory
    temp_dir = input_path.parent / f"tmp_{input_path.stem}"
    frames_in = temp_dir / "in"
    frames_out = temp_dir / "out"
    audio_path = temp_dir / "audio.m4a"
    
    try:
        if temp_dir.exists(): shutil.rmtree(temp_dir)
        frames_in.mkdir(parents=True)
        frames_out.mkdir(parents=True)

        # 1. Extract Audio
        try:
            run_ffmpeg(["ffmpeg", "-y", "-i", str(input_path), "-vn", "-acodec", "copy", str(audio_path)])
        except:
            logger.warning(f"Audio extraction failed for {input_path.name}, continuing without audio.")

        # 2. Extract Frames (lossless PNG to avoid codec artifacts)
        run_ffmpeg([
            "ffmpeg", "-y", "-i", str(input_path),
            "-vsync", "0", "-f", "image2", str(frames_in / "f_%06d.png")
        ])

        # 3. Inference
        frame_list = sorted(list(frames_in.glob("*.png")))
        total = len(frame_list)
        
        for i, f_path in enumerate(frame_list):
            out_f = frames_out / f_path.name
            upsampler.enhance_to_file(f_path, out_f, params['upscale'])
            
            if task_id and (i % 20 == 0 or i == total - 1):
                prog = p_base + int(((i + 1) / total) * p_scale)
                db.update_task_status(task_id, "PROCESSING", prog, f"Upscaling {input_path.name}: {i+1}/{total} frames")

        # 4. Recombine
        fps = get_video_fps(input_path)
        cmd = ["ffmpeg", "-y", "-framerate", str(fps), "-i", str(frames_out / "f_%06d.png")]
        
        if audio_path.exists() and params.get('keep_audio', True):
            cmd += ["-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0?", "-c:a", "copy"]
        
        cmd += ["-c:v", "libx264", "-crf", str(params.get('crf', 18)), "-pix_fmt", "yuv420p", str(output_path)]
        run_ffmpeg(cmd)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def process_segment(input_path, output_path, params, weights_dir, task_id, progress_base, progress_scale):
    """
    Deprecated or Compatibility Wrapper. 
    In the new architecture, the processor should manage the upsampler lifecycle.
    """
    # This is a fallback if someone calls the old signature.
    # It's better to avoid building model here.
    from .upscaler import build_model
    upsampler = build_model(
        params['model_name'], params['upscale'], params['tile'], params['tile_pad'],
        params['fp16'], weights_dir, params.get('denoise_strength')
    )
    process_video_with_model(input_path, output_path, upsampler, params, task_id, progress_base, progress_scale)
