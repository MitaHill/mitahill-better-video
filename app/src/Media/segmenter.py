import shutil
import hashlib
import os
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from app.src.Utils.ffmpeg import run_ffmpeg, get_video_fps, get_gpu_utilization
from app.src.Utils.preview_cache import set_preview_from_path
from app.src.Database import core as db
from app.src.Config import settings as config
from app.src.Notifications.events import send_event

logger = logging.getLogger("SEGMENTER")

class ProgressRecorder:
    def __init__(
        self,
        task_id,
        segment_key,
        p_base,
        p_scale,
        total_frames,
        segment_start_frame,
        total_total_frames,
        segment_index,
        segment_count,
    ):
        self.task_id = task_id
        self.segment_key = segment_key
        self.p_base = p_base
        self.p_scale = p_scale
        self.total_frames = total_frames
        self.segment_start_frame = segment_start_frame
        self.total_total_frames = total_total_frames
        self.segment_index = segment_index
        self.segment_count = segment_count
        self._last_gpu_check = 0.0
        self._last_gpu_util = None
        self._last_flush = 0.0
        self._last_emit = 0.0
        self._pending_frame = None
        self._pending_message = None

    def record(self, frame_index, message):
        self._pending_frame = frame_index
        self._pending_message = message
        now = time.time()
        if now - self._last_flush >= config.PROGRESS_FLUSH_SECONDS:
            self.flush()

    def flush(self, force=False):
        if self._pending_frame is None:
            return
        if not force and (time.time() - self._last_flush) < config.PROGRESS_FLUSH_SECONDS:
            return
        progress = self.p_base + int((self._pending_frame / self.total_frames) * self.p_scale)
        db.update_task_status(self.task_id, "PROCESSING", progress, self._pending_message)
        db.update_segment_progress(self.task_id, self.segment_key, self._pending_frame)
        if self._pending_message:
            logger.info(
                "Task %s [%s] %s (%s/%s)",
                self.task_id,
                self.segment_key,
                self._pending_message,
                self._pending_frame,
                self.total_frames,
            )
        self._last_flush = time.time()

    def emit_frame(self, frame_index, preview_updated=False, preview_reset=False):
        total_done = self.segment_start_frame + frame_index - 1
        now = time.time()
        if not preview_updated and config.EVENT_FLUSH_SECONDS > 0:
            if now - self._last_emit < config.EVENT_FLUSH_SECONDS:
                return
        if now - self._last_gpu_check >= config.PROGRESS_FLUSH_SECONDS:
            self._last_gpu_util = get_gpu_utilization()
            self._last_gpu_check = now
        payload = {
            "task_id": self.task_id,
            "task_category": "enhance",
            "stage": "enhance",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "segment_key": self.segment_key,
            "item_index": self.segment_index,
            "item_count": self.segment_count,
            "item_label": "分段" if self.segment_count else "",
            "unit_done": frame_index,
            "unit_total": self.total_frames,
            "unit_label": "帧",
            "segment_index": self.segment_index,
            "segment_count": self.segment_count,
            "segment_frame": frame_index,
            "segment_total": self.total_frames,
            "total_frame": total_done,
            "total_total": self.total_total_frames,
            "progress": self.p_base + int((frame_index / self.total_frames) * self.p_scale),
            "gpu_util": self._last_gpu_util,
        }
        if preview_updated:
            payload["preview_frame"] = total_done
            if preview_reset:
                payload["preview_reset"] = True
        send_event(payload)
        self._last_emit = now


def process_video_with_model(
    input_path,
    output_path,
    upsampler,
    params,
    task_id=None,
    p_base=0,
    p_scale=100,
    segment_key=None,
    resume_from_frame=1,
    preview_original_path=None,
    preview_upscaled_path=None,
    segment_start_frame=1,
    total_total_frames=0,
    segment_index=0,
    segment_count=0,
):
    """
    Common logic to process a video file (or segment) using a provided upsampler model.
    Handles frame extraction, model inference, and ffmpeg recombination.
    """
    logger.info(f"Processing video: {input_path.name} -> {output_path.name}")

    def atomic_copy(src, dst):
        tmp_path = dst.with_name(f".{dst.name}.tmp")
        shutil.copyfile(src, tmp_path)
        os.replace(tmp_path, dst)

    # Create temp workspace inside the run directory
    temp_dir = input_path.parent / f"tmp_{input_path.stem}"
    frames_in = temp_dir / "in"
    frames_out = temp_dir / "out"
    audio_path = temp_dir / "audio.m4a"
    
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        frames_in.mkdir(parents=True, exist_ok=True)
        frames_out.mkdir(parents=True, exist_ok=True)

        # 1. Extract Audio
        if not audio_path.exists():
            try:
                run_ffmpeg(["ffmpeg", "-y", "-i", str(input_path), "-vn", "-acodec", "copy", str(audio_path)])
            except Exception:
                logger.warning(f"Audio extraction failed for {input_path.name}, continuing without audio.")

        # 2. Extract Frames (align with upstream pipeline)
        if not any(frames_in.glob("f_*.jpg")):
            hwaccel = ["-hwaccel", "cuda"] if config.FFMPEG_USE_GPU else []
            deinterlace = bool(params.get("deinterlace"))
            vf = None
            if deinterlace:
                vf = "yadif_cuda=mode=send_frame:parity=auto:deint=all" if config.FFMPEG_USE_GPU else "yadif=mode=send_frame:parity=auto:deint=all"
            cmd = [
                "ffmpeg", "-y", *hwaccel, "-i", str(input_path),
                "-vsync", "0", "-q:v", "2"
            ]
            if vf:
                cmd += ["-vf", vf]
            cmd += ["-f", "image2", str(frames_in / "f_%06d.jpg")]
            fallback = None
            if hwaccel or vf:
                fb_vf = "yadif=mode=send_frame:parity=auto:deint=all" if deinterlace else None
                fallback = ["ffmpeg", "-y", "-i", str(input_path), "-vsync", "0", "-q:v", "2"]
                if fb_vf:
                    fallback += ["-vf", fb_vf]
                fallback += ["-f", "image2", str(frames_in / "f_%06d.jpg")]
            run_ffmpeg(cmd, fallback_args=fallback)

        # 3. Inference
        frame_list = sorted(list(frames_in.glob("*.jpg")))
        total = len(frame_list)
        if total == 0:
            raise RuntimeError(f"No frames extracted for {input_path.name}")

        if resume_from_frame > 1:
            check_path = frames_out / f"f_{resume_from_frame - 1:06d}.jpg"
            if not check_path.exists():
                resume_from_frame = 1

        if task_id and segment_key:
            recorder = ProgressRecorder(
                task_id,
                segment_key,
                p_base,
                p_scale,
                total,
                segment_start_frame,
                total_total_frames=total_total_frames or (segment_start_frame + total - 1),
                segment_index=segment_index,
                segment_count=segment_count,
            )
        else:
            recorder = None

        def seed_preview(frame_index):
            if not (preview_original_path and preview_upscaled_path):
                return False
            in_path = frames_in / f"f_{frame_index:06d}.jpg"
            if not in_path.exists():
                return False
            try:
                total_done = segment_start_frame + frame_index - 1
                atomic_copy(in_path, preview_original_path)
                if task_id:
                    set_preview_from_path(task_id, "original", in_path, total_done)
                out_path = frames_out / f"f_{frame_index:06d}.jpg"
                if not out_path.exists() and frame_index > 1:
                    out_path = frames_out / f"f_{frame_index - 1:06d}.jpg"
                if out_path.exists():
                    atomic_copy(out_path, preview_upscaled_path)
                    if task_id:
                        set_preview_from_path(task_id, "upscaled", out_path, total_done)
                return True
            except Exception:
                return False
        
        if resume_from_frame > 1:
            seed_index = min(resume_from_frame, total)
            if seed_index >= 1 and seed_preview(seed_index) and recorder:
                recorder.emit_frame(seed_index, preview_updated=True, preview_reset=True)

        hash_to_first = {}
        frame_hashes = []
        for i, f_path in enumerate(frame_list):
            try:
                frame_hash = hashlib.md5(f_path.read_bytes()).hexdigest()
            except Exception:
                frame_hash = None
            frame_hashes.append(frame_hash)
            if frame_hash and frame_hash not in hash_to_first:
                hash_to_first[frame_hash] = i + 1

        unique_frames = len(set(hash_to_first.values()))
        if unique_frames != total:
            logger.info(
                "Dedup scan: %s unique / %s total frames in segment %s",
                unique_frames,
                total,
                segment_key or "full",
            )

        for i, f_path in enumerate(frame_list):
            frame_index = i + 1
            if frame_index < resume_from_frame:
                continue
            out_f = frames_out / f_path.name
            frame_hash = frame_hashes[i]
            first_index = hash_to_first.get(frame_hash) if frame_hash else None
            if out_f.exists():
                pass
            elif first_index and first_index != frame_index:
                src_out = frames_out / frame_list[first_index - 1].name
                if src_out.exists():
                    shutil.copyfile(src_out, out_f)
                else:
                    upsampler.enhance_to_file(f_path, out_f, params['upscale'])
            else:
                upsampler.enhance_to_file(f_path, out_f, params['upscale'])

            preview_updated = False
            if preview_original_path and preview_upscaled_path:
                try:
                    stride = config.PREVIEW_EVERY_N_FRAMES
                    should_write = True if stride is None else (frame_index % stride == 0)
                    if should_write:
                        total_done = segment_start_frame + frame_index - 1
                        atomic_copy(f_path, preview_original_path)
                        atomic_copy(out_f, preview_upscaled_path)
                        if task_id:
                            set_preview_from_path(task_id, "original", f_path, total_done)
                            set_preview_from_path(task_id, "upscaled", out_f, total_done)
                        preview_updated = True
                except Exception:
                    pass

            if recorder:
                recorder.emit_frame(frame_index, preview_updated=preview_updated)
                recorder.record(frame_index, f"Upscaling {input_path.name}: {frame_index}/{total} frames")
        if recorder:
            recorder.record(total, f"Upscaling {input_path.name}: {total}/{total} frames")
            recorder.flush(force=True)

        # 4. Recombine
        fps = get_video_fps(input_path)
        cmd = [
            "ffmpeg", "-y", "-framerate", str(fps), "-start_number", "1",
            "-i", str(frames_out / "f_%06d.jpg")
        ]
        
        if audio_path.exists() and params.get('keep_audio', True):
            cmd += ["-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0?", "-c:a", "copy"]
        
        output_codec = (params.get("output_codec") or "h264").lower()
        crf = params.get("crf", 18)
        if config.FFMPEG_USE_GPU:
            if output_codec in ("h265", "hevc"):
                nvenc_cmd = cmd + [
                    "-c:v", "hevc_nvenc", "-preset", "p4", "-rc:v", "vbr",
                    "-cq:v", str(crf), "-b:v", "0", "-pix_fmt", "yuv420p",
                    str(output_path)
                ]
                fallback_cmd = cmd + [
                    "-c:v", "libx265", "-crf", str(crf), "-pix_fmt", "yuv420p",
                    str(output_path)
                ]
            else:
                nvenc_cmd = cmd + [
                    "-c:v", "h264_nvenc", "-preset", "p4", "-rc:v", "vbr",
                    "-cq:v", str(crf), "-b:v", "0", "-pix_fmt", "yuv420p",
                    str(output_path)
                ]
                fallback_cmd = cmd + [
                    "-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p",
                    str(output_path)
                ]
            run_ffmpeg(nvenc_cmd, fallback_args=fallback_cmd)
        else:
            if output_codec in ("h265", "hevc"):
                cmd += ["-c:v", "libx265", "-crf", str(crf), "-pix_fmt", "yuv420p", str(output_path)]
            else:
                cmd += ["-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p", str(output_path)]
            run_ffmpeg(cmd)

    finally:
        pass

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
