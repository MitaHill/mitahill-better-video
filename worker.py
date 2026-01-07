import sys
import os
import time
import json
import shutil
import subprocess
import argparse
from pathlib import Path
import sqlite3
from PIL import Image
import numpy as np
import gc

# Setup paths
repo_root = "/workspace/Real-ESRGAN"
if os.path.isdir(os.path.join(repo_root, "realesrgan")):
    sys.path.insert(0, repo_root)

try:
    import torch
    from realesrgan import RealESRGANer
    from realesrgan.archs.srvgg_arch import SRVGGNetCompact
    from basicsr.archs.rrdbnet_arch import RRDBNet
except ImportError:
    pass

import db
import config

def run_ffmpeg(args):
    """Run ffmpeg and raise error on failure."""
    print(f"Running: {' '.join(args)}")
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr}")

def get_video_codec(file_path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.stdout.strip().lower()

def get_video_duration(file_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 0.0

def ensure_weights(model_name, weights_dir):
    weights_dir = Path(weights_dir)
    weights_dir.mkdir(parents=True, exist_ok=True)
    
    default_files = {
        "realesrgan-x4plus": "RealESRGAN_x4plus.pth",
        "realesrnet-x4plus": "RealESRNet_x4plus.pth",
        "realesr-animevideov3": "realesr-animevideov3.pth",
        "realesrgan-x4plus-anime": "RealESRGAN_x4plus_anime_6B.pth",
        "realesr-general-x4v3": "realesr-general-x4v3.pth",
        "realesr-general-wdn-x4v3": "realesr-general-wdn-x4v3.pth",
    }
    urls = {
        "realesrgan-x4plus": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        "realesrnet-x4plus": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.1/RealESRNet_x4plus.pth",
        "realesr-animevideov3": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth",
        "realesrgan-x4plus-anime": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
        "realesr-general-x4v3": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
        "realesr-general-wdn-x4v3": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-wdn-x4v3.pth",
    }
    
    fname = default_files.get(model_name, f"{model_name}.pth")
    local_path = weights_dir / fname
    
    if not local_path.exists():
        # Check pre-downloaded
        pre_downloaded = Path("/workspace/weights") / fname
        if pre_downloaded.exists():
            shutil.copy(pre_downloaded, local_path)
            return local_path

        url = urls.get(model_name)
        if url:
            print(f"Downloading {fname}...")
            import urllib.request
            try:
                urllib.request.urlretrieve(url, local_path)
            except Exception as e:
                print(f"Download failed: {e}")
    return local_path

def build_model(model_name, scale, tile, tile_pad, fp16, weights_dir, denoise_strength):
    weights_dir = Path(weights_dir)
    
    if model_name == "realesr-general-x4v3" and denoise_strength is not None and denoise_strength != 1.0:
        main_path = ensure_weights("realesr-general-x4v3", weights_dir)
        wdn_path = ensure_weights("realesr-general-wdn-x4v3", weights_dir)
        model_path = [str(main_path), str(wdn_path)]
        dni_weight = [float(denoise_strength), float(1.0 - denoise_strength)]
    else:
        model_path = str(ensure_weights(model_name, weights_dir))
        dni_weight = None
    
    if model_name in ("realesrgan-x4plus", "realesrnet-x4plus"):
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    elif model_name == "realesrgan-x4plus-anime":
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    elif model_name in ("realesr-animevideov3", "realesr-general-x4v3"):
        model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4, act_type='prelu')
    else:
        # Fallback
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)

    upsampler = RealESRGANer(
        scale=4,
        model_path=model_path,
        dni_weight=dni_weight,
        model=model,
        tile=tile,
        tile_pad=tile_pad,
        pre_pad=0,
        half=fp16 and torch.cuda.is_available(),
        gpu_id=0 if torch.cuda.is_available() else None 
    )
    return upsampler

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
            if "preview_done" not in params and i==1 and "segment_000" in input_path.name:
                 img.save(run_dir.parent / f"run_{task_id}" / "preview_original.jpg")
                 out_img.save(run_dir.parent / f"run_{task_id}" / "preview_upscaled.jpg")
                 params['preview_done'] = True

            # Update DB Progress
            # Scale local progress (0-100) to global task progress
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
                
                # Check if already split (resume)
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
                            # Calculate progress range for this segment
                            # e.g., 2 segments. Seg 1: 5%-50%. Seg 2: 50%-95%.
                            p_start = 5 + int((idx / total_segs) * 90)
                            p_end = 5 + int(((idx + 1) / total_segs) * 90)
                            p_scale = p_end - p_start
                            
                            process_segment(seg_path, sr_seg_path, params, weights_dir, task_id, p_start, p_scale)
                            
                            # Delete source segment to save space? Optional. 
                            # Better keep source segment in case of retry, but frames are gone.
                        
                        f.write(f"file '{sr_seg_path.name}'\n")
                
                # Concat
                db.update_task_status(task_id, "PROCESSING", 98, "Merging segments...")
                video_out_name = f"sr_{Path(filename).stem}.mp4"
                video_out = output_root / video_out_name
                
                run_ffmpeg([
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(concat_list_path), "-c", "copy", str(video_out)
                ])
                
                # Cleanup segments
                shutil.rmtree(segments_dir, ignore_errors=True)
                
                db.update_task_status(task_id, "COMPLETED", 100, f"Output: {video_out_name}")
                
            else:
                # --- ORIGINAL SINGLE PASS ---
                process_segment(input_path, output_root / f"sr_{Path(filename).stem}.mp4", params, weights_dir, task_id, 0, 100)
                db.update_task_status(task_id, "COMPLETED", 100, f"Output: sr_{Path(filename).stem}.mp4")

        elif input_type == 'Image':
            # Reuse image logic (simplified for brevity, assume similar)
            upsampler = build_model(
                params['model_name'], params['upscale'], params['tile'], params['tile_pad'],
                params['fp16'], weights_dir, params.get('denoise_strength')
            )
            img = Image.open(input_path).convert("RGB")
            output, _ = upsampler.enhance(np.array(img)[:,:,::-1], outscale=params['upscale'])
            out_img = Image.fromarray(output[:,:,::-1])
            out_name = f"sr_{Path(filename).stem}.png"
            out_img.save(output_root / out_name)
            img.save(run_dir / "preview_original.jpg")
            out_img.save(run_dir / "preview_upscaled.jpg")
            db.update_task_status(task_id, "COMPLETED", 100, f"Output: {out_name}")

    except Exception as e:
        print(f"Task {task_id} failed: {e}")
        db.update_task_status(task_id, "FAILED", 0, str(e))
        if "Unsupported codec" in str(e):
            db.delete_task(task_id)

def recover_tasks():
    """Check for interrupted tasks on startup and reset or delete them."""
    print("Checking for interrupted tasks...")
    tasks = db.get_unfinished_tasks()
    output_root = Path("/workspace/output")
    
    for task in tasks:
        task_id = task['task_id']
        try:
            params = json.loads(task['task_params'])
            filename = params.get('filename')
            run_dir = output_root / f"run_{task_id}"
            input_path = run_dir / filename
            
            if input_path.exists():
                print(f"Recovering task {task_id}: Source exists, resetting to PENDING.")
                db.update_task_status(task_id, "PENDING", 0, "Recovered. Waiting to restart...")
            else:
                print(f"Cleaning task {task_id}: Source missing, deleting.")
                db.delete_task(task_id)
                if run_dir.exists():
                    shutil.rmtree(run_dir, ignore_errors=True)
        except Exception as e:
            print(f"Error recovering task {task_id}: {e}")
            db.delete_task(task_id)

def worker_loop():
    recover_tasks()
    print("Worker daemon started. Waiting for tasks...")
    while True:
        try:
            db.cleanup_old_tasks(config.TASK_TTL_HOURS)
        except Exception as e:
            print(f"Cleanup error: {e}")

        conn = sqlite3.connect(db.DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM task_queue WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT 1")
        row = c.fetchone()
        conn.close()

        if row:
            process_single_task(dict(row))
            # Force GC after task
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        else:
            time.sleep(2)

if __name__ == "__main__":
    worker_loop()
