import sys
import os
import time
import json
import shutil
import subprocess
import argparse
from pathlib import Path
import sqlite3
import numpy as np
from PIL import Image

# Setup paths
repo_root = "/workspace/Real-ESRGAN"
if os.path.isdir(os.path.join(repo_root, "realesrgan")):
    sys.path.insert(0, repo_root)

# Try imports
try:
    import torch
    from realesrgan import RealESRGANer
    from realesrgan.archs.srvgg_arch import SRVGGNetCompact
    from basicsr.archs.rrdbnet_arch import RRDBNet
except ImportError:
    pass

import db

def run_ffmpeg(args):
    """Run ffmpeg and raise error on failure."""
    print(f"Running: {' '.join(args)}")
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr}")

def get_video_duration(file_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 0.0

def ensure_weights(model_name, weights_dir):
    """Ensure weights exist, download if needed."""
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
        # Check pre-downloaded weights
        pre_downloaded = Path("/workspace/weights") / fname
        if pre_downloaded.exists():
            print(f"Found pre-downloaded model: {pre_downloaded}")
            # Symlink or Copy? Copy is safer for permissions/modification
            shutil.copy(pre_downloaded, local_path)
            return local_path

        url = urls.get(model_name)
        if url:
            print(f"Downloading {fname} from {url}...")
            import urllib.request
            try:
                urllib.request.urlretrieve(url, local_path)
                print(f"Download complete: {local_path}")
            except Exception as e:
                print(f"Failed to download {model_name}: {e}")
                # Don't raise yet, maybe the user has it elsewhere? 
                # But realistically this will fail later.
        else:
            print(f"No URL found for model {model_name}, assuming local file exists.")
            
    return local_path

def build_model(model_name, scale, tile, tile_pad, fp16, weights_dir, denoise_strength):
    weights_dir = Path(weights_dir)
    # Ensure weights logic called here
    # For general-x4v3 we might need two files
    if model_name == "realesr-general-x4v3" and denoise_strength is not None and denoise_strength != 1.0:
        main_path = ensure_weights("realesr-general-x4v3", weights_dir)
        wdn_path = ensure_weights("realesr-general-wdn-x4v3", weights_dir)
        model_path = [str(main_path), str(wdn_path)]
        dni_weight = [float(denoise_strength), float(1.0 - denoise_strength)]
    else:
        # Standard model
        model_path = ensure_weights(model_name, weights_dir)
        dni_weight = None
        model_path = str(model_path)
    
    if model_name in ("realesrgan-x4plus", "realesrnet-x4plus"):
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    elif model_name == "realesrgan-x4plus-anime":
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    elif model_name == "realesr-animevideov3":
        model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4, act_type='prelu')
    elif model_name == "realesr-general-x4v3":
        model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4, act_type='prelu')
    else:
        raise ValueError(f"Unknown model {model_name}")

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

def process_task(task_id):
    print(f"Starting worker for task {task_id}")
    
    try:
        task = db.get_task(task_id)
        if not task:
            print("Task not found")
            return

        db.update_task_status(task_id, "PROCESSING", 0, "Initializing...")
        
        params = json.loads(task['task_params'])
        
        output_root = Path("/workspace/output")
        run_dir = output_root / f"run_{task_id}"
        weights_dir = output_root / "models"
        
        input_type = params.get('input_type', 'Video')
        filename = params.get('filename')
        input_path = run_dir / filename
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        if input_type == 'Video':
            in_frames = run_dir / "frames_in"
            out_frames = run_dir / "frames_out"
            in_frames.mkdir(exist_ok=True)
            out_frames.mkdir(exist_ok=True)

            db.update_task_status(task_id, "PROCESSING", 5, "Extracting frames...")
            extract_cmd = ["ffmpeg", "-y"]
            if torch.cuda.is_available():
                extract_cmd.extend(["-hwaccel", "cuda"])
            extract_cmd.extend([
                "-i", str(input_path), "-vsync", "0",
                "-q:v", "2", str(in_frames / "f_%06d.jpg")
            ])
            run_ffmpeg(extract_cmd)

            frames = sorted(list(in_frames.glob("*.jpg")) + list(in_frames.glob("*.png")))
            total_frames = len(frames)
            if total_frames == 0:
                raise RuntimeError("No frames extracted")

            db.update_task_status(task_id, "PROCESSING", 10, "Loading model...")
            upsampler = build_model(
                model_name=params['model_name'],
                scale=params['upscale'],
                tile=params['tile'],
                tile_pad=params['tile_pad'],
                fp16=params['fp16'],
                weights_dir=weights_dir,
                denoise_strength=params.get('denoise_strength')
            )

            db.update_task_status(task_id, "PROCESSING", 10, f"Upscaling {total_frames} frames...")
            
            preview_original = run_dir / "preview_original.jpg"
            preview_upscaled = run_dir / "preview_upscaled.jpg"

            for i, fpath in enumerate(frames, 1):
                img = Image.open(fpath).convert("RGB")
                img_np = np.array(img)[:, :, ::-1]
                
                output, _ = upsampler.enhance(img_np, outscale=params['upscale'])
                out_rgb = output[:, :, ::-1]
                out_img = Image.fromarray(out_rgb)
                
                out_img.save(out_frames / fpath.name)

                if i == 1:
                    img.save(preview_original)
                    out_img.save(preview_upscaled)

                if i % 10 == 0 or i == total_frames:
                    pct = 10 + int((i / total_frames) * 80)
                    db.update_task_status(task_id, "PROCESSING", pct, f"Upscaling frame {i}/{total_frames}")

            db.update_task_status(task_id, "PROCESSING", 90, "Encoding video...")
            audio_path = run_dir / "audio.m4a"
            
            has_audio = False
            if params.get('keep_audio'):
                try:
                    run_ffmpeg(["ffmpeg", "-y", "-i", str(input_path), "-vn", "-acodec", "copy", str(audio_path)])
                    has_audio = audio_path.exists() and audio_path.stat().st_size > 0
                except:
                    pass

            fps = params.get('fps', 30.0)
            
            video_out_name = f"sr_{Path(filename).stem}.mp4"
            video_out = output_root / video_out_name
            
            frame_ext = ".jpg" if any(out_frames.glob("*.jpg")) else ".png"
            
            encode_cmd = [
                "ffmpeg", "-y",
                "-framerate", str(fps),
                "-start_number", "1",
                "-i", str(out_frames / f"f_%06d{frame_ext}")
            ]
            if has_audio:
                encode_cmd.extend(["-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0?", "-c:a", "copy"])
            
            encode_cmd.extend([
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "medium", "-crf", str(params.get('crf', 18)),
                str(video_out)
            ])
            run_ffmpeg(encode_cmd)

            db.update_task_status(task_id, "COMPLETED", 100, f"Finished. Output: {video_out_name}")

        elif input_type == 'Image':
            db.update_task_status(task_id, "PROCESSING", 10, "Upscaling image...")
            upsampler = build_model(
                model_name=params['model_name'],
                scale=params['upscale'],
                tile=params['tile'],
                tile_pad=params['tile_pad'],
                fp16=params['fp16'],
                weights_dir=weights_dir,
                denoise_strength=params.get('denoise_strength')
            )
            
            img = Image.open(input_path).convert("RGB")
            img_np = np.array(img)[:, :, ::-1]
            output, _ = upsampler.enhance(img_np, outscale=params['upscale'])
            out_img = Image.fromarray(output[:, :, ::-1])
            
            out_name = f"sr_{Path(filename).stem}.png"
            out_path = output_root / out_name
            out_img.save(out_path)
            
            img.save(run_dir / "preview_original.jpg")
            out_img.save(run_dir / "preview_upscaled.jpg")
            
            db.update_task_status(task_id, "COMPLETED", 100, f"Finished. Output: {out_name}")

    except Exception as e:
        print(f"Task failed: {e}")
        import traceback
        traceback.print_exc()
        db.update_task_status(task_id, "FAILED", 0, str(e))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_id", required=True)
    args = parser.parse_args()
    process_task(args.task_id)
