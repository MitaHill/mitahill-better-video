import json
import shutil
import os
import logging
from pathlib import Path
from PIL import Image
import numpy as np

import db
import config
from .utils import run_ffmpeg, get_video_codec, get_video_duration
from .upscaler import build_model
from .segmenter import process_segment

logger = logging.getLogger("PROCESSOR")

def process_single_task(task):
    task_id = task['task_id']
    logger.info(f"=== Starting Task Processor: {task_id} ===")
    
    try:
        db.update_task_status(task_id, "PROCESSING", 0, "Initializing context...")
        params = json.loads(task['task_params'])
        logger.debug(f"Task parameters: {params}")
        
        output_root = Path("/workspace/output")
        run_dir = output_root / f"run_{task_id}"
        weights_dir = Path("/workspace/weights") # Using image weights
        
        input_type = params.get('input_type', 'Video')
        filename = params.get('filename')
        input_path = run_dir / filename
        
        logger.info(f"Input Type: {input_type}, Path: {input_path}")
        
        if not input_path.exists():
            logger.critical(f"[FAILED] Input file missing at {input_path}")
            raise FileNotFoundError(f"Input file missing: {filename}")

        if input_type == 'Video':
            # Codec check
            codec = get_video_codec(input_path)
            logger.info(f"Source Video Codec: {codec}")
            if codec in ['vp9', 'av1']:
                logger.error(f"Unsupported codec found: {codec}")
                raise ValueError(f"Unsupported codec: {codec}. VP9 and AV1 are not supported.")

            duration = get_video_duration(input_path)
            logger.info(f"Video Duration: {duration}s (Segment Threshold: {config.SEGMENT_TIME_SECONDS}s)")
            
            # --- GENERATE PREVIEW ---
            try:
                preview_path = run_dir / "preview_original.jpg"
                if not preview_path.exists():
                    logger.debug(f"Generating preview for {input_path.name}...")
                    run_ffmpeg([
                        "ffmpeg", "-y", "-i", str(input_path), 
                        "-ss", "00:00:00", "-vframes", "1", 
                        "-q:v", "2", str(preview_path)
                    ])
            except Exception as e:
                logger.warning(f"Failed to generate preview: {e}")

            # --- SEGMENTATION LOGIC ---
            if duration > config.SEGMENT_TIME_SECONDS:
                logger.info("Decision: Using SEGMENTATION mode.")
                segments_dir = run_dir / "segments"
                segments_dir.mkdir(exist_ok=True)
                
                db.update_task_status(task_id, "PROCESSING", 1, "Splitting video into chunks...")
                
                existing_segs = sorted(list(segments_dir.glob("seg_*.mp4")))
                if not existing_segs:
                    logger.debug("Splitting original video using FFmpeg segmenter...")
                    run_ffmpeg([
                        "ffmpeg", "-i", str(input_path), 
                        "-c", "copy", "-map", "0",
                        "-segment_time", str(config.SEGMENT_TIME_SECONDS), 
                        "-f", "segment", "-reset_timestamps", "1",
                        str(segments_dir / "seg_%03d.mp4")
                    ])
                    existing_segs = sorted(list(segments_dir.glob("seg_*.mp4")))
                
                total_segs = len(existing_segs)
                logger.info(f"Total segments to process: {total_segs}")
                
                concat_list_path = run_dir / "concat_list.txt"
                with open(concat_list_path, "w") as f:
                    for idx, seg_path in enumerate(existing_segs):
                        sr_seg_name = f"{seg_path.stem}_sr.mp4"
                        sr_seg_path = segments_dir / sr_seg_name
                        
                        if not sr_seg_path.exists():
                            logger.info(f"Processing segment {idx+1}/{total_segs}: {seg_path.name}")
                            p_start = 5 + int((idx / total_segs) * 90)
                            p_end = 5 + int(((idx + 1) / total_segs) * 90)
                            p_scale = p_end - p_start
                            
                            process_segment(seg_path, sr_seg_path, params, weights_dir, task_id, p_start, p_scale)
                        else:
                            logger.debug(f"Segment {seg_path.name} already processed. Skipping.")
                        
                        f.write(f"file 'segments/{sr_seg_path.name}'\n")
                
                db.update_task_status(task_id, "PROCESSING", 98, "Merging all segments...")
                logger.info("Merging segments into final output...")
                video_out_name = f"sr_{Path(filename).stem}.mp4"
                video_out = output_root / video_out_name
                
                run_ffmpeg([
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(concat_list_path), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video_out)
                ])
                
                logger.info(f"Cleaning up segments directory: {segments_dir}")
                shutil.rmtree(segments_dir, ignore_errors=True)
                db.update_task_status(task_id, "COMPLETED", 100, f"Completed: {video_out_name}")
                
            else:
                logger.info("Decision: Using SINGLE PASS mode.")
                video_out_name = f"sr_{Path(filename).stem}.mp4"
                process_segment(input_path, output_root / video_out_name, params, weights_dir, task_id, 0, 100)
                db.update_task_status(task_id, "COMPLETED", 100, f"Completed: {video_out_name}")

        elif input_type == 'Image':
            logger.info("Processing Image Task...")
            db.update_task_status(task_id, "PROCESSING", 10, "Loading upscaler model...")
            upsampler = build_model(
                params['model_name'], params['upscale'], params['tile'], params['tile_pad'],
                params['fp16'], weights_dir, params.get('denoise_strength')
            )
            
            logger.debug(f"Reading image: {input_path}")
            img = Image.open(input_path).convert("RGB")
            
            logger.info("Starting inference enhance...")
            output, _ = upsampler.enhance(np.array(img)[:,:,::-1], outscale=params['upscale'])
            
            out_img = Image.fromarray(output[:,:,::-1])
            out_name = f"sr_{Path(filename).stem}.png"
            out_path = output_root / out_name
            out_img.save(out_path)
            logger.info(f"Image saved to: {out_path}")
            
            logger.debug("Generating previews...")
            img.save(run_dir / "preview_original.jpg")
            out_img.save(run_dir / "preview_upscaled.jpg")
            
            db.update_task_status(task_id, "COMPLETED", 100, f"Completed: {out_name}")

    except Exception as e:
        logger.error(f"[ERROR] Task {task_id} failed: {e}", exc_info=True)
        db.update_task_status(task_id, "FAILED", message=str(e))
        raise