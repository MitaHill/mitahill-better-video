import json
import shutil
import os
import logging
from pathlib import Path
from PIL import Image
import numpy as np
import torch

import db
import config
from .utils import run_ffmpeg, get_video_codec, get_video_duration, get_video_total_frames, get_video_fps
from .upscaler import build_model
from .segmenter import process_segment

logger = logging.getLogger("PROCESSOR")

def generate_previews(input_path, run_dir, upsampler, upscale_factor):
    """Generates original and upscaled preview images using an already loaded model."""
    p_orig = run_dir / "preview_original.jpg"
    p_ups = run_dir / "preview_upscaled.jpg"
    
    try:
        # Extract a representative frame (avoid black intro)
        if not p_orig.exists():
            duration = get_video_duration(input_path)
            seek_time = max(0.1, min(1.0, duration * 0.1)) if duration > 0 else 0.0
            run_ffmpeg([
                "ffmpeg", "-y", "-i", str(input_path),
                "-ss", f"{seek_time:.2f}", "-vframes", "1",
                "-q:v", "2", str(p_orig)
            ])
        
        # Upscale that frame if model is provided
        if p_orig.exists() and not p_ups.exists() and upsampler:
            img = Image.open(p_orig).convert("RGB")
            # Enhance expects BGR for Real-ESRGAN implementation
            output, _ = upsampler.enhance(np.array(img)[:,:,::-1], outscale=upscale_factor)
            out_img = Image.fromarray(output[:,:,::-1])
            out_img.save(p_ups)
            logger.info("Previews generated successfully.")
    except Exception as e:
        logger.warning(f"Preview generation failed: {e}")

def process_single_task(task):
    task_id = task['task_id']
    logger.info(f"=== Starting Task Processor: {task_id} ===")
    
    try:
        db.update_task_status(task_id, "PROCESSING", 0, "Initializing...")
        params = json.loads(task['task_params'])
        output_root = Path("/workspace/output")
        run_dir = output_root / f"run_{task_id}"
        weights_dir = Path("/workspace/weights")
        
        input_path = run_dir / params['filename']
        if not input_path.exists():
            raise FileNotFoundError(f"Input missing: {params['filename']}")

        # 1. Load Model ONCE
        db.update_task_status(task_id, "PROCESSING", 5, "Loading Model...")
        upsampler = build_model(
            params['model_name'], params['upscale'], params['tile'], 
            params.get('tile_pad', 10), params.get('fp16', True), 
            weights_dir, params.get('denoise_strength', 0.5)
        )

        if params['input_type'] == 'Video':
            # 2. Previews
            generate_previews(input_path, run_dir, upsampler, params['upscale'])
            
            duration = get_video_duration(input_path)
            total_frames = get_video_total_frames(input_path)
            if total_frames <= 0:
                total_frames = max(1, int(round(get_video_duration(input_path) * get_video_fps(input_path))))
            db.upsert_task_progress(task_id, total_frames, 0)
            # 3. Process Video (reuse upsampler logic)
            if duration > config.SEGMENT_TIME_SECONDS:
                # Segmented processing
                db.update_task_status(task_id, "PROCESSING", 10, "Splitting Video...")
                segments_dir = run_dir / "segments"
                segments_dir.mkdir(exist_ok=True)
                
                segs = sorted(list(segments_dir.glob("seg_*.mp4")))
                if not segs:
                    # Split
                    run_ffmpeg([
                        "ffmpeg", "-y", "-i", str(input_path), "-c", "copy", "-map", "0",
                        "-segment_time", str(config.SEGMENT_TIME_SECONDS), "-f", "segment",
                        "-reset_timestamps", "1", str(segments_dir / "seg_%03d.mp4")
                    ])
                
                segs = sorted(list(segments_dir.glob("seg_*.mp4")))
                if not segs:
                    raise RuntimeError("Video split produced no segments.")
                db.upsert_task_progress(task_id, total_frames, len(segs))
                concat_list = run_dir / "concat_list.txt"
                
                with open(concat_list, "w") as f:
                    cumulative_frames = 0
                    segment_scale = 80.0 / len(segs)
                    for i, s_path in enumerate(segs):
                        seg_frames = get_video_total_frames(s_path)
                        if seg_frames <= 0:
                            seg_frames = max(1, int(round(get_video_duration(s_path) * get_video_fps(s_path))))
                        start_frame = cumulative_frames + 1
                        end_frame = start_frame + seg_frames - 1
                        segment_key = f"seg_{start_frame}_{end_frame}"
                        db.upsert_segment(task_id, segment_key, i, start_frame, end_frame, seg_frames)
                        out_s_path = segments_dir / f"{s_path.stem}_sr.mp4"
                        prog = 10 + int((i / len(segs)) * 80)
                        db.update_task_status(task_id, "PROCESSING", prog, f"Processing Part {i+1}/{len(segs)}...")
                        
                        # Call process_segment but we need to pass the upsampler if we want real reuse
                        # For now, let's keep the upsampler reuse inside the segmenter or pass it
                        # Since upscaler logic is inside build_model, let's just use it
                        from .segmenter import process_video_with_model
                        p_base = 10 + int(i * segment_scale)
                        p_scale = max(1, int(round(segment_scale)))
                        segment_progress = db.get_segment_progress(task_id, segment_key)
                        last_done = (segment_progress or {}).get("last_done_frame") or 0
                        resume_frame = max(1, last_done - 2) if last_done else 1
                        if not (out_s_path.exists() and last_done >= seg_frames and seg_frames > 0):
                            process_video_with_model(
                                s_path,
                                out_s_path,
                                upsampler,
                                params,
                                task_id,
                                p_base,
                                p_scale,
                                segment_key=segment_key,
                                resume_from_frame=resume_frame,
                                preview_path=run_dir / "preview_live.jpg",
                                segment_start_frame=start_frame,
                                total_total_frames=total_frames,
                                segment_index=i + 1,
                                segment_count=len(segs),
                            )
                        f.write(f"file 'segments/{out_s_path.name}'\n")
                        cumulative_frames += seg_frames
                
                db.update_task_status(task_id, "PROCESSING", 95, "Merging Parts...")
                out_name = f"sr_{input_path.stem}.mp4"
                run_ffmpeg([
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output_root / out_name)
                ])
                shutil.rmtree(segments_dir, ignore_errors=True)
            else:
                # Single pass video
                db.update_task_status(task_id, "PROCESSING", 20, "Upscaling Video...")
                out_name = f"sr_{input_path.stem}.mp4"
                from .segmenter import process_video_with_model
                segment_key = f"full_1_{total_frames}"
                db.upsert_task_progress(task_id, total_frames, 1)
                db.upsert_segment(task_id, segment_key, 0, 1, total_frames, total_frames)
                segment_progress = db.get_segment_progress(task_id, segment_key)
                last_done = (segment_progress or {}).get("last_done_frame") or 0
                resume_frame = max(1, last_done - 2) if last_done else 1
                output_path = output_root / out_name
                if not (output_path.exists() and last_done >= total_frames and total_frames > 0):
                    process_video_with_model(
                        input_path,
                        output_path,
                        upsampler,
                        params,
                        task_id,
                        20,
                        80,
                        segment_key=segment_key,
                        resume_from_frame=resume_frame,
                        preview_path=run_dir / "preview_live.jpg",
                        segment_start_frame=1,
                        total_total_frames=total_frames,
                        segment_index=1,
                        segment_count=1,
                    )

        else:
            # 4. Process Image
            db.update_task_status(task_id, "PROCESSING", 50, "Upscaling Image...")
            img = Image.open(input_path).convert("RGB")
            output, _ = upsampler.enhance(np.array(img)[:,:,::-1], outscale=params['upscale'])
            out_img = Image.fromarray(output[:,:,::-1])
            out_name = f"sr_{input_path.stem}.png"
            out_img.save(output_root / out_name)
            # Previews for image are just the files themselves
            img.save(run_dir / "preview_original.jpg")
            out_img.save(run_dir / "preview_upscaled.jpg")

        db.update_task_status(task_id, "COMPLETED", 100, f"Completed: {out_name}")

    except Exception as e:
        logger.error(f"Task failed: {e}", exc_info=True)
        db.update_task_status(task_id, "FAILED", message=str(e))
    finally:
        if 'upsampler' in locals():
            del upsampler
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
