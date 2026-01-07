import shutil
import os
import gc
from pathlib import Path
import numpy as np
from PIL import Image
import torch

import db
import config
from .utils import run_ffmpeg
from .upscaler import build_model

def process_segment(input_path, output_path, params, weights_dir, task_id, progress_offset, progress_scale):
    """Process a single video segment."""
    run_dir = input_path.parent
    in_frames = run_dir / f"frames_in_{input_path.stem}"
    out_frames = run_dir / f"frames_out_{input_path.stem}"
    
    # Clean previous if any
    shutil.rmtree(in_frames, ignore_errors=True)
    shutil.rmtree(out_frames, ignore_errors=True)
    in_frames.mkdir()
    out_frames.mkdir()

    try:
        # 1. Extract
        extract_cmd = ["ffmpeg", "-y"]
        if torch.cuda.is_available():
            extract_cmd.extend(["-hwaccel", "cuda"])
        extract_cmd.extend(["-i", str(input_path), "-vsync", "0", "-q:v", "2", str(in_frames / "f_%06d.jpg")])
        run_ffmpeg(extract_cmd)

        frames = sorted(list(in_frames.glob("*.jpg")))
        total_frames = len(frames)
        if total_frames == 0:
            print(f"Warning: Segment {input_path.name} has no frames.")
            return

        # 2. Upscale
        upsampler = build_model(
            params['model_name'], params['upscale'], params['tile'], params['tile_pad'],
            params['fp16'], weights_dir, params.get('denoise_strength')
        )

        for i, fpath in enumerate(frames, 1):
            img = Image.open(fpath).convert("RGB")
            img_np = np.array(img)[:, :, ::-1]
            output, _ = upsampler.enhance(img_np, outscale=params['upscale'])
            out_img = Image.fromarray(output[:, :, ::-1])
            out_img.save(out_frames / fpath.name)
            
            # Save previews if this is the very first segment of the task
            if "preview_done" not in params and i==1 and "seg_000" in input_path.name:
                 # Look up to run_{task_id} dir
                 preview_dir = run_dir.parent
                 img.save(preview_dir / "preview_original.jpg")
                 out_img.save(preview_dir / "preview_upscaled.jpg")
                 params['preview_done'] = True

            # Update DB Progress
            if i % 10 == 0 or i == total_frames:
                local_pct = i / total_frames
                global_pct = progress_offset + (local_pct * progress_scale)
                db.update_task_status(task_id, "PROCESSING", int(global_pct), f"Segment {input_path.stem}: {i}/{total_frames}")
        
        # Free memory
        del upsampler
        torch.cuda.empty_cache()
        gc.collect()

        # 3. Encode Segment
        audio_path = run_dir / f"audio_{input_path.stem}.m4a"
        has_audio = False
        if params.get('keep_audio'):
            try:
                run_ffmpeg(["ffmpeg", "-y", "-i", str(input_path), "-vn", "-acodec", "copy", str(audio_path)])
                has_audio = audio_path.exists() and audio_path.stat().st_size > 0
            except: pass

        encode = ["ffmpeg", "-y", "-framerate", str(params.get('fps', 30)), "-start_number", "1",
                  "-i", str(out_frames / "f_%06d.jpg")]
        if has_audio:
            encode.extend(["-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0?", "-c:a", "copy"])
        
        encode.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", str(params.get('crf', 18)), str(output_path)])
        run_ffmpeg(encode)

    finally:
        # ALWAYS clean up frames to save space
        shutil.rmtree(in_frames, ignore_errors=True)
        shutil.rmtree(out_frames, ignore_errors=True)
        if 'audio_path' in locals() and audio_path.exists():
            os.remove(audio_path)
