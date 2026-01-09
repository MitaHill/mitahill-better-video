import shutil
import os
import logging
import time
from pathlib import Path
from .utils import run_ffmpeg, get_video_fps
import db
import config
from .utils import get_gpu_utilization
from .notifier import send_event

logger = logging.getLogger("SEGMENTER")

class ProgressRecorder:
    def __init__(self, task_id, segment_key, p_base, p_scale, total_frames, segment_start_frame, total_total_frames):
        self.task_id = task_id
        self.segment_key = segment_key
        self.p_base = p_base
        self.p_scale = p_scale
        self.total_frames = total_frames
        self.segment_start_frame = segment_start_frame
        self.total_total_frames = total_total_frames
        self._last_gpu_check = 0.0
        self._last_gpu_util = None
        self._last_flush = 0.0
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
        self._last_flush = time.time()

    def emit_frame(self, frame_index):
        total_done = self.segment_start_frame + frame_index - 1
        now = time.time()
        if now - self._last_gpu_check >= config.PROGRESS_FLUSH_SECONDS:
            self._last_gpu_util = get_gpu_utilization()
            self._last_gpu_check = now
        send_event(
            {
                "task_id": self.task_id,
                "segment_key": self.segment_key,
                "segment_frame": frame_index,
                "segment_total": self.total_frames,
                "total_frame": total_done,
                "total_total": self.total_total_frames,
                "progress": self.p_base + int((frame_index / self.total_frames) * self.p_scale),
                "gpu_util": self._last_gpu_util,
            }
        )


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
    preview_path=None,
    segment_start_frame=1,
    total_total_frames=0,
):
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
            run_ffmpeg([
                "ffmpeg", "-y", "-i", str(input_path),
                "-vsync", "0", "-q:v", "2", "-f", "image2", str(frames_in / "f_%06d.jpg")
            ])

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
            )
        else:
            recorder = None
        
        for i, f_path in enumerate(frame_list):
            frame_index = i + 1
            if frame_index < resume_from_frame:
                continue
            out_f = frames_out / f_path.name
            upsampler.enhance_to_file(f_path, out_f, params['upscale'])
            if preview_path:
                try:
                    shutil.copyfile(out_f, preview_path)
                except Exception:
                    pass
            
            if recorder:
                recorder.emit_frame(frame_index)
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
        
        cmd += ["-c:v", "libx264", "-crf", str(params.get('crf', 18)), "-pix_fmt", "yuv420p", str(output_path)]
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
