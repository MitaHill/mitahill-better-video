import json
import shutil
import os
import logging
from pathlib import Path
from PIL import Image
import numpy as np
import torch

from app.src.Database import core as db
from app.src.Config import settings as config
from app.src.Utils.ffmpeg import (
    run_ffmpeg,
    get_video_codec,
    get_video_duration,
    get_video_total_frames,
    get_video_fps,
)
from app.src.Media.upscaler import build_model
from app.src.Media.segmenter import process_segment
from app.src.Audio.enhancer import AudioEnhancer
from app.src.Audio.denoiser import apply_pre_denoise
from app.src.Audio.haas_effect import apply_haas_effect

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
            hwaccel = ["-hwaccel", "cuda"] if config.FFMPEG_USE_GPU else []
            cmd = [
                "ffmpeg", "-y", *hwaccel, "-i", str(input_path),
                "-ss", f"{seek_time:.2f}", "-vframes", "1",
                "-q:v", "2", str(p_orig)
            ]
            fallback = None
            if hwaccel:
                fallback = [
                    "ffmpeg", "-y", "-i", str(input_path),
                    "-ss", f"{seek_time:.2f}", "-vframes", "1",
                    "-q:v", "2", str(p_orig)
                ]
            run_ffmpeg(cmd, fallback_args=fallback)
        
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
        upsampler = build_model(
            params['model_name'], params['upscale'], params['tile'], 
            params.get('tile_pad', 10), params.get('fp16', True), 
            weights_dir, params.get('denoise_strength', 0.5)
        )
        logger.info("Model loaded: %s", params.get("model_name"))

        if params['input_type'] == 'Video':
            enable_audio = (
                config.ENABLE_AUDIO_ENHANCEMENT
                and params.get('keep_audio', True)
                and params.get('audio_enhance', False)
            )
            pre_denoise_mode = (params.get("pre_denoise_mode") or config.PRE_DENOISE_MODE).lower()
            haas_enabled = bool(params.get("haas_enabled")) and params.get("keep_audio", True)
            haas_delay_ms = int(params.get("haas_delay_ms") or 0)
            if haas_delay_ms < 0:
                haas_delay_ms = 0
            if haas_delay_ms > 3000:
                haas_delay_ms = 3000
            haas_lead = params.get("haas_lead", "left")
            video_params = dict(params)
            needs_audio_post = enable_audio or (pre_denoise_mode != "off") or haas_enabled
            if needs_audio_post:
                video_params["keep_audio"] = False

            final_out_name = f"sr_{input_path.stem}.mp4"
            video_out_name = final_out_name
            if enable_audio:
                video_out_name = f"sr_{input_path.stem}_video.mp4"
            video_only_path = output_root / video_out_name

            # 2. Previews
            generate_previews(input_path, run_dir, upsampler, params['upscale'])
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
                        
                        # Call process_segment but we need to pass the upsampler if we want real reuse
                        # For now, let's keep the upsampler reuse inside the segmenter or pass it
                        # Since upscaler logic is inside build_model, let's just use it
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
                out_name = video_out_name
                output_codec = (params.get("output_codec") or "h264").lower()
                crf = params.get("crf", 18)
                if output_codec in ("h265", "hevc"):
                    nvenc_cmd = [
                        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
                        "-c:v", "hevc_nvenc", "-preset", "p4", "-rc:v", "vbr",
                        "-cq:v", str(crf), "-b:v", "0", "-pix_fmt", "yuv420p",
                        str(output_root / out_name)
                    ]
                    fallback_cmd = [
                        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
                        "-c:v", "libx265", "-crf", str(crf), "-pix_fmt", "yuv420p",
                        str(output_root / out_name)
                    ]
                else:
                    nvenc_cmd = [
                        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
                        "-c:v", "h264_nvenc", "-preset", "p4", "-rc:v", "vbr",
                        "-cq:v", str(crf), "-b:v", "0", "-pix_fmt", "yuv420p",
                        str(output_root / out_name)
                    ]
                    fallback_cmd = [
                        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
                        "-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p",
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
                out_name = video_out_name
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

            if enable_audio:
                db.update_task_status(task_id, "PROCESSING", 96, "Enhancing Audio...")
                logger.info("Audio enhancement enabled.")
                audio_source = run_dir / "audio_source.wav"
                audio_input = audio_source
                audio_denoised = run_dir / "audio_denoised.wav"
                audio_enhanced = run_dir / "audio_enhanced.wav"
                audio_haas = run_dir / "audio_haas.wav"
                final_output = output_root / final_out_name
                try:
                    if audio_denoised.exists() and audio_denoised.is_dir():
                        shutil.rmtree(audio_denoised, ignore_errors=True)
                    run_ffmpeg([
                        "ffmpeg", "-y", "-i", str(input_path),
                        "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "1",
                        str(audio_source)
                    ])
                    if pre_denoise_mode != "off":
                        apply_pre_denoise(pre_denoise_mode, audio_source, audio_denoised)
                        audio_input = audio_denoised
                    enhancer = AudioEnhancer()
                    enhancer.process(audio_input, audio_enhanced)
                    audio_final = audio_enhanced
                    if haas_enabled:
                        apply_haas_effect(audio_final, audio_haas, haas_delay_ms, haas_lead)
                        audio_final = audio_haas
                    run_ffmpeg([
                        "ffmpeg", "-y", "-i", str(video_only_path), "-i", str(audio_final),
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        str(final_output)
                    ])
                except Exception:
                    logger.error("Audio enhancement failed", exc_info=True)
                    raise
                finally:
                    if video_only_path.exists() and video_only_path != final_output:
                        try:
                            video_only_path.unlink()
                        except Exception:
                            pass
                out_name = final_out_name
            elif pre_denoise_mode != "off" and params.get('keep_audio', True):
                db.update_task_status(task_id, "PROCESSING", 96, "Pre-denoising Audio...")
                logger.info("Audio pre-denoise mode: %s", pre_denoise_mode)
                audio_source = run_dir / "audio_source.wav"
                audio_denoised = run_dir / "audio_denoised.wav"
                audio_haas = run_dir / "audio_haas.wav"
                final_output = output_root / final_out_name
                try:
                    if audio_denoised.exists() and audio_denoised.is_dir():
                        shutil.rmtree(audio_denoised, ignore_errors=True)
                    run_ffmpeg([
                        "ffmpeg", "-y", "-i", str(input_path),
                        "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "1",
                        str(audio_source)
                    ])
                    apply_pre_denoise(pre_denoise_mode, audio_source, audio_denoised)
                    audio_final = audio_denoised
                    if haas_enabled:
                        apply_haas_effect(audio_final, audio_haas, haas_delay_ms, haas_lead)
                        audio_final = audio_haas
                    merge_output = final_output
                    if video_only_path == final_output:
                        merge_output = output_root / f"{input_path.stem}_denoised_tmp.mp4"
                    run_ffmpeg([
                        "ffmpeg", "-y", "-i", str(video_only_path), "-i", str(audio_final),
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        str(merge_output)
                    ])
                    if merge_output != final_output:
                        merge_output.replace(final_output)
                except Exception:
                    logger.error("Pre-denoise failed", exc_info=True)
                    raise
                finally:
                    if video_only_path.exists() and video_only_path != final_output:
                        try:
                            video_only_path.unlink()
                        except Exception:
                            pass
                out_name = final_out_name
            elif haas_enabled and params.get('keep_audio', True):
                db.update_task_status(task_id, "PROCESSING", 96, "Applying Haas effect...")
                logger.info("Haas effect enabled.")
                audio_source = run_dir / "audio_source.wav"
                audio_haas = run_dir / "audio_haas.wav"
                final_output = output_root / final_out_name
                try:
                    run_ffmpeg([
                        "ffmpeg", "-y", "-i", str(input_path),
                        "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "1",
                        str(audio_source)
                    ])
                    apply_haas_effect(audio_source, audio_haas, haas_delay_ms, haas_lead)
                    merge_output = final_output
                    if video_only_path == final_output:
                        merge_output = output_root / f"{input_path.stem}_haas_tmp.mp4"
                    run_ffmpeg([
                        "ffmpeg", "-y", "-i", str(video_only_path), "-i", str(audio_haas),
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        str(merge_output)
                    ])
                    if merge_output != final_output:
                        merge_output.replace(final_output)
                except Exception:
                    logger.error("Haas effect failed", exc_info=True)
                    raise
                finally:
                    if video_only_path.exists() and video_only_path != final_output:
                        try:
                            video_only_path.unlink()
                        except Exception:
                            pass
                out_name = final_out_name
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
