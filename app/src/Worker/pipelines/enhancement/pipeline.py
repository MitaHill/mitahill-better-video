import json
import shutil
import logging
from pathlib import Path
from PIL import Image
import numpy as np
import torch

from app.src.Database import core as db
from app.src.Config import settings as config
from app.src.Utils.ffmpeg import (
    run_ffmpeg,
    get_video_duration,
    get_video_total_frames,
    get_video_fps,
    get_video_encoder,
    normalize_output_codec,
)
from app.src.Utils.preview_cache import set_preview_from_path, clear_task as clear_preview_cache
from app.src.Media.upscaler import build_model
from app.src.Worker.gpu_model_coordinator import is_cuda_oom, prepare_model_load, register_release_hook
from .preview import generate_previews

logger = logging.getLogger("PROCESSOR")

def process_enhancement_task(task):
    task_id = task['task_id']
    logger.info(f"=== Starting Task Processor: {task_id} ===")
    model_holder = {}

    def _release_realesrgan():
        model_holder.pop("upsampler", None)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    register_release_hook("realesrgan", _release_realesrgan)
    
    try:
        db.update_task_status(task_id, "PROCESSING", 0, "Initializing...")
        params = json.loads(task['task_params'])
        video_info = json.loads(task.get('video_info') or "{}")
        output_root = Path("/workspace/storage/output")
        run_dir = output_root / f"run_{task_id}"
        weights_dir = Path("/workspace/app/models/video")
        logger.info("Task %s started (%s)", task_id, params.get("input_type"))
        
        input_path = Path(
            params.get("upload_path")
            or video_info.get("upload_path")
            or (run_dir / params['filename'])
        )
        if not input_path.exists():
            raise FileNotFoundError(f"Input missing: {params['filename']}")

        # 1. Load Model ONCE
        db.update_task_status(task_id, "PROCESSING", 5, "Loading Model...")
        prepare_model_load("realesrgan")
        try:
            upsampler = build_model(
                params['model_name'], params['upscale'], params['tile'],
                params.get('tile_pad', 10), params.get('fp16', True),
                weights_dir, params.get('denoise_strength', 0.5)
            )
            model_holder["upsampler"] = upsampler
        except RuntimeError as exc:
            if not is_cuda_oom(exc):
                raise
            logger.warning("CUDA OOM while loading Real-ESRGAN; releasing peer models and retrying once.")
            prepare_model_load("realesrgan")
            upsampler = build_model(
                params['model_name'], params['upscale'], params['tile'],
                params.get('tile_pad', 10), params.get('fp16', True),
                weights_dir, params.get('denoise_strength', 0.5)
            )
            model_holder["upsampler"] = upsampler
        logger.info("Model loaded: %s", params.get("model_name"))

        if params['input_type'] == 'Video':
            video_params = dict(params)

            out_name = f"sr_{input_path.stem}.mp4"

            # 2. Previews
            generate_previews(input_path, run_dir, upsampler, params['upscale'])
            if run_dir.joinpath("preview_original.jpg").exists():
                set_preview_from_path(task_id, "original", run_dir / "preview_original.jpg", 1)
            if run_dir.joinpath("preview_upscaled.jpg").exists():
                set_preview_from_path(task_id, "upscaled", run_dir / "preview_upscaled.jpg", 1)
            logger.info("Preview generation completed.")
            
            duration = get_video_duration(input_path)
            total_frames = get_video_total_frames(input_path)
            if total_frames <= 0:
                total_frames = max(1, int(round(get_video_duration(input_path) * get_video_fps(input_path))))
            db.upsert_task_progress(task_id, total_frames, 0)
            # 3. Process Video (reuse upsampler logic)
            if duration > config.SEGMENT_TIME_SECONDS:
                # Segmented processing
                db.update_task_status(task_id, "PROCESSING", 10, "Splitting Video...")
                logger.info("Segmenting video: %.2fs per segment", config.SEGMENT_TIME_SECONDS)
                segments_dir = run_dir / "segments"
                segments_dir.mkdir(exist_ok=True)
                
                segs = sorted([p for p in segments_dir.glob("seg_*.mp4") if not p.stem.endswith("_sr")])
                if not segs:
                    # Split
                    run_ffmpeg([
                        "ffmpeg", "-y", "-i", str(input_path), "-c", "copy", "-map", "0",
                        "-segment_time", str(config.SEGMENT_TIME_SECONDS), "-f", "segment",
                        "-reset_timestamps", "1", str(segments_dir / "seg_%03d.mp4")
                    ])
                
                segs = sorted([p for p in segments_dir.glob("seg_*.mp4") if not p.stem.endswith("_sr")])
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
                        start_sec = int(i * config.SEGMENT_TIME_SECONDS)
                        end_sec = int(min(duration, (i + 1) * config.SEGMENT_TIME_SECONDS))
                        segment_key = f"seg_{start_sec}_{end_sec}"
                        legacy_segment_key = f"seg_{start_frame}_{end_frame}"
                        segment_progress = db.get_segment_progress(task_id, segment_key)
                        if not segment_progress and legacy_segment_key != segment_key:
                            legacy_progress = db.get_segment_progress(task_id, legacy_segment_key)
                            if legacy_progress:
                                segment_key = legacy_segment_key
                                segment_progress = legacy_progress
                        db.upsert_segment(task_id, segment_key, i + 1, start_frame, end_frame, seg_frames)
                        out_s_path = segments_dir / f"{s_path.stem}_sr.mp4"
                        prog = 10 + int((i / len(segs)) * 80)
                        db.update_task_status(task_id, "PROCESSING", prog, f"Processing Part {i+1}/{len(segs)}...")
                        
                        from app.src.Media.segmenter import process_video_with_model
                        p_base = 10 + int(i * segment_scale)
                        p_scale = max(1, int(round(segment_scale)))
                        if not segment_progress:
                            segment_progress = db.get_segment_progress(task_id, segment_key)
                        last_done = (segment_progress or {}).get("last_done_frame") or 0
                        resume_frame = max(1, last_done - 2) if last_done else 1
                        if not (out_s_path.exists() and last_done >= seg_frames and seg_frames > 0):
                            process_video_with_model(
                                s_path,
                                out_s_path,
                                upsampler,
                                video_params,
                                task_id,
                                p_base,
                                p_scale,
                                segment_key=segment_key,
                                resume_from_frame=resume_frame,
                                preview_original_path=run_dir / "preview_original.jpg",
                                preview_upscaled_path=run_dir / "preview_upscaled.jpg",
                                segment_start_frame=start_frame,
                                total_total_frames=total_frames,
                                segment_index=i + 1,
                                segment_count=len(segs),
                            )
                        f.write(f"file 'segments/{out_s_path.name}'\n")
                        cumulative_frames += seg_frames
                
                db.update_task_status(task_id, "PROCESSING", 95, "Merging Parts...")
                logger.info("Merging %s segments with NVENC.", len(segs))
                output_codec = normalize_output_codec(params.get("output_codec"))
                if not output_codec:
                    raise RuntimeError("No available NVIDIA FFmpeg encoder.")
                crf = params.get("crf", 18)
                nvenc_cmd = [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
                    "-c:v", get_video_encoder(output_codec, prefer_gpu=True), "-preset", "p4", "-rc:v", "vbr",
                    "-cq:v", str(crf), "-b:v", "0", "-pix_fmt", "yuv420p", "-c:a", "copy",
                    str(output_root / out_name)
                ]
                fallback_cmd = [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
                    "-c:v", get_video_encoder(output_codec, prefer_gpu=False), "-crf", str(crf), "-pix_fmt", "yuv420p", "-c:a", "copy",
                    str(output_root / out_name)
                ]
                if config.FFMPEG_USE_GPU:
                    run_ffmpeg(nvenc_cmd, fallback_args=fallback_cmd)
                else:
                    run_ffmpeg(fallback_cmd)
                shutil.rmtree(segments_dir, ignore_errors=True)
            else:
                # Single pass video
                db.update_task_status(task_id, "PROCESSING", 20, "Upscaling Video...")
                logger.info("Processing video in a single pass.")
                from app.src.Media.segmenter import process_video_with_model
                segment_key = f"full_1_{total_frames}"
                db.upsert_task_progress(task_id, total_frames, 1)
                db.upsert_segment(task_id, segment_key, 1, 1, total_frames, total_frames)
                segment_progress = db.get_segment_progress(task_id, segment_key)
                last_done = (segment_progress or {}).get("last_done_frame") or 0
                resume_frame = max(1, last_done - 2) if last_done else 1
                output_path = output_root / out_name
                if not (output_path.exists() and last_done >= total_frames and total_frames > 0):
                    process_video_with_model(
                        input_path,
                        output_path,
                        upsampler,
                        video_params,
                        task_id,
                        20,
                        80,
                        segment_key=segment_key,
                        resume_from_frame=resume_frame,
                        preview_original_path=run_dir / "preview_original.jpg",
                        preview_upscaled_path=run_dir / "preview_upscaled.jpg",
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
            set_preview_from_path(task_id, "original", run_dir / "preview_original.jpg", 1)
            set_preview_from_path(task_id, "upscaled", run_dir / "preview_upscaled.jpg", 1)

        db.update_task_result(task_id, output_root / out_name)
        db.update_task_status(task_id, "COMPLETED", 100, f"Completed: {out_name}")

    except Exception as e:
        logger.error(f"Task failed: {e}", exc_info=True)
        db.update_task_status(task_id, "FAILED", message=str(e))
    finally:
        clear_preview_cache(task_id)
        model_holder.pop("upsampler", None)
        if 'upsampler' in locals():
            del upsampler
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
