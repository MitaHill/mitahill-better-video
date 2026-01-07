import json
import shutil
import os
from pathlib import Path
from PIL import Image
import numpy as np

import db
import config
from .utils import run_ffmpeg, get_video_codec, get_video_duration
from .upscaler import build_model
from .segmenter import process_segment

def process_single_task(task):
    task_id = task['task_id']
    print(f"Processing task: {task_id}")
    
    try:
        db.update_task_status(task_id, "PROCESSING", 0, "Initializing...")
        params = json.loads(task['task_params'])
        
        output_root = Path("/workspace/output")
        run_dir = output_root / f"run_{task_id}"
        weights_dir = output_root / "models"
        
        input_type = params.get('input_type', 'Video')
        filename = params.get('filename')
        input_path = run_dir / filename
        
        if not input_path.exists():
            raise FileNotFoundError("Input file missing")

        # Codec check
        if input_type == "Video":
            codec = get_video_codec(input_path)
            if codec in ['vp9', 'av1']:
                raise ValueError(f"Unsupported codec: {codec}. VP9 and AV1 are not supported.")

        if input_type == 'Video':
            duration = get_video_duration(input_path)
            
            # --- SEGMENTATION LOGIC ---
            if duration > config.SEGMENT_TIME_SECONDS:
                print(f"Long video detected ({duration}s). Using segmentation mode.")
                segments_dir = run_dir / "segments"
                segments_dir.mkdir(exist_ok=True)
                
                # Split video
                db.update_task_status(task_id, "PROCESSING", 1, "Splitting video into chunks...")
                
                existing_segs = sorted(list(segments_dir.glob("seg_*.mp4")))
                if not existing_segs:
                    run_ffmpeg([
                        "ffmpeg", "-i", str(input_path), 
                        "-c", "copy", "-map", "0",
                        "-segment_time", str(config.SEGMENT_TIME_SECONDS), 
                        "-f", "segment", "-reset_timestamps", "1",
                        str(segments_dir / "seg_%03d.mp4")
                    ])
                    existing_segs = sorted(list(segments_dir.glob("seg_*.mp4")))
                
                total_segs = len(existing_segs)
                concat_list_path = run_dir / "concat_list.txt"
                with open(concat_list_path, "w") as f:
                    for idx, seg_path in enumerate(existing_segs):
                        sr_seg_name = f"{seg_path.stem}_sr.mp4"
                        sr_seg_path = segments_dir / sr_seg_name
                        
                        # Process if SR segment doesn't exist
                        if not sr_seg_path.exists():
                            p_start = 5 + int((idx / total_segs) * 90)
                            p_end = 5 + int(((idx + 1) / total_segs) * 90)
                            p_scale = p_end - p_start
                            
                            process_segment(seg_path, sr_seg_path, params, weights_dir, task_id, p_start, p_scale)
                        
                        f.write(f"file '{sr_seg_path.name}'\n")
                
                # Concat
                db.update_task_status(task_id, "PROCESSING", 98, "Merging segments...")
                video_out_name = f"sr_{Path(filename).stem}.mp4"
                video_out = output_root / video_out_name
                
                run_ffmpeg([
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(concat_list_path), "-c", "copy", str(video_out)
                ])
                
                shutil.rmtree(segments_dir, ignore_errors=True)
                db.update_task_status(task_id, "COMPLETED", 100, f"Output: {video_out_name}")
                
            else:
                # --- SINGLE PASS ---
                video_out_name = f"sr_{Path(filename).stem}.mp4"
                process_segment(input_path, output_root / video_out_name, params, weights_dir, task_id, 0, 100)
                db.update_task_status(task_id, "COMPLETED", 100, f"Output: {video_out_name}")

        elif input_type == 'Image':
            db.update_task_status(task_id, "PROCESSING", 10, "Upscaling image...")
            upsampler = build_model(
                params['model_name'], params['upscale'], params['tile'], params['tile_pad'],
                params['fp16'], weights_dir, params.get('denoise_strength')
            )
            img = Image.open(input_path).convert("RGB")
            output, _ = upsampler.enhance(np.array(img)[:,:,::-1], outscale=params['upscale'])
            out_img = Image.fromarray(output[:,:,::-1])
            out_name = f"sr_{Path(filename).stem}.png"
            out_path = output_root / out_name
            out_img.save(out_path)
            
            img.save(run_dir / "preview_original.jpg")
            out_img.save(run_dir / "preview_upscaled.jpg")
            
            db.update_task_status(task_id, "COMPLETED", 100, f"Output: {out_name}")

    except Exception as e:
        print(f"Task {task_id} failed: {e}")
        db.update_task_status(task_id, "FAILED", 0, str(e))
        if "Unsupported codec" in str(e):
            db.delete_task(task_id)
