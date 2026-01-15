from flask import Flask, jsonify, request, send_file, send_from_directory, current_app
from werkzeug.exceptions import RequestEntityTooLarge
from pathlib import Path
import uuid
import json
import shutil

from app.src.Config import settings as config
from app.src.Database import core as db
from app.src.Utils.http import ffprobe_info, secure_filename, is_filename_safe

STORAGE_ROOT = Path("/workspace/storage")
OUTPUT_ROOT = STORAGE_ROOT / "output"
UPLOAD_ROOT = STORAGE_ROOT / "upload"

def _parse_task_params(form):
    input_type = form.get("input_type", "Video")
    model_name = form.get("model_name", "realesrgan-x4plus")
    upscale = int(form.get("upscale", 3))
    tile = int(form.get("tile", config.DEFAULT_SMART_TILE_SIZE))
    denoise = float(form.get("denoise_strength", 0.5))
    keep_audio = form.get("keep_audio", "true").lower() == "true"
    audio_enhance = form.get("audio_enhance", str(config.ENABLE_AUDIO_ENHANCEMENT)).lower() == "true"
    pre_denoise_mode = form.get("pre_denoise_mode", config.PRE_DENOISE_MODE)
    haas_enabled = form.get("haas_enabled", "false").lower() == "true"
    haas_delay_ms = int(form.get("haas_delay_ms", 0))
    haas_lead = form.get("haas_lead", "left")
    crf = int(form.get("crf", 18))
    output_codec = form.get("output_codec", "h264").lower()
    deinterlace = form.get("deinterlace", "false").lower() == "true"
    tile_pad = int(form.get("tile_pad", config.DEFAULT_TILE_PADDING))
    fp16 = form.get("fp16", str(config.DEFAULT_FP16)).lower() == "true"

    return {
        "input_type": input_type,
        "model_name": model_name,
        "upscale": upscale,
        "tile": tile,
        "denoise_strength": denoise,
        "keep_audio": keep_audio,
        "audio_enhance": audio_enhance,
        "pre_denoise_mode": pre_denoise_mode,
        "haas_enabled": haas_enabled,
        "haas_delay_ms": haas_delay_ms,
        "haas_lead": haas_lead,
        "crf": crf,
        "output_codec": output_codec,
        "deinterlace": deinterlace,
        "tile_pad": tile_pad,
        "fp16": fp16,
    }

def _handle_upload(upload, params, client_ip):
    if not upload.filename or not is_filename_safe(upload.filename):
        return None, "invalid filename"

    task_id = uuid.uuid4().hex
    run_dir = OUTPUT_ROOT / f"run_{task_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    upload_dir = UPLOAD_ROOT / f"run_{task_id}"
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = secure_filename(upload.filename)
    input_path = upload_dir / filename
    upload.save(input_path)

    input_type = params["input_type"]
    size_mb = input_path.stat().st_size / (1024 * 1024)
    max_mb = config.MAX_VIDEO_SIZE_MB if input_type == "Video" else config.MAX_IMAGE_SIZE_MB
    if size_mb > max_mb:
        input_path.unlink(missing_ok=True)
        db.create_task(task_id, client_ip, {**params, "filename": filename, "upload_path": str(input_path)}, {})
        db.update_task_status(task_id, "FAILED", progress=0, message=f"file exceeds limit ({max_mb} MB)")
        return task_id, f"file exceeds limit ({max_mb} MB)"

    if input_type == "Video":
        info = ffprobe_info(input_path)
    else:
        info = {"width": 0, "height": 0, "fps": 0, "duration": 0, "video_codec": None, "audio_codec": None}

    video_info = {
        "size_mb": round(size_mb, 2),
        "filename": filename,
        "upload_path": str(input_path),
        **info,
    }

    if input_type == "Video":
        video_codec = (video_info.get("video_codec") or "").lower()
        audio_codec = (video_info.get("audio_codec") or "").lower()
        if video_codec == "mpeg2video" and not params.get("deinterlace"):
            params["deinterlace"] = True
            params["mpeg2_adapted"] = True
        else:
            params["mpeg2_adapted"] = False
        if video_codec == "mpeg2video" and audio_codec == "mp2":
            current_app.logger.info(
                "MPEG2 + MP2 detected for task %s; allowing non-AAC audio.", task_id
            )

    task_params = {
        **params,
        "filename": filename,
        "upload_path": str(input_path),
        "source_video_codec": video_info.get("video_codec"),
    }

    db.create_task(task_id, client_ip, task_params, video_info)

    if input_type == "Video":
        video_codec = (video_info.get("video_codec") or "").lower()
        allowed_video = {"h264", "hevc", "h265", "mpeg2video"}

        reject_reason = None
        if not video_codec or video_codec not in allowed_video:
            reject_reason = "仅支持 H.264/H.265/MPEG2 视频编码（拒绝 AV1/VP9 等非主流编码）。"

        if reject_reason:
            db.update_task_status(task_id, "FAILED", progress=0, message=reject_reason)
            return task_id, reject_reason

    return task_id, None

def _read_cached_frame(cache_dir):
    try:
        path = cache_dir / "preview_last_frame.txt"
        if path.exists():
            return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        pass
    return 0

def _write_cached_frame(cache_dir, frame_number):
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "preview_last_frame.txt").write_text(str(int(frame_number)), encoding="utf-8")
    except Exception:
        pass

def _try_recover_preview(task_id, kind):
    progress = db.get_latest_segment_progress(task_id) or {}
    last_done = int(progress.get("last_done_frame") or 0)
    segment_index = int(progress.get("segment_index") or 0)
    start_frame = int(progress.get("start_frame") or 0)
    if not (segment_index and last_done and start_frame):
        return None
    segment_dir = OUTPUT_ROOT / f"run_{task_id}" / "segments"
    seg_path = segment_dir / f"seg_{segment_index - 1:03d}.mp4"
    temp_dir = seg_path.parent / f"tmp_{seg_path.stem}"
    frames_dir = temp_dir / ("out" if kind == "upscaled" else "in")
    frame_path = frames_dir / f"f_{last_done:06d}.jpg"
    if not frame_path.exists():
        return None
    cache_dir = Path("/workspace/storage/data/preview_images") / task_id / ("after" if kind == "upscaled" else "before")
    cache_path = cache_dir / "preview_last.jpg"
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = cache_dir / f".preview_last.tmp"
    shutil.copyfile(frame_path, tmp_path)
    tmp_path.replace(cache_path)
    total_done = start_frame + last_done - 1
    _write_cached_frame(cache_dir, total_done)
    return cache_path


def create_app(worker_service=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = (
        max(config.MAX_VIDEO_SIZE_MB, config.MAX_IMAGE_SIZE_MB) * 1024 * 1024
    )

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(_err):
        limit_mb = max(config.MAX_VIDEO_SIZE_MB, config.MAX_IMAGE_SIZE_MB)
        return jsonify({"error": f"file exceeds limit ({limit_mb} MB)"}), 413

    @app.get("/api/health")
    def health():
        db_status = "ok"
        try:
            conn = db.get_connection()
            conn.execute("SELECT 1")
            conn.close()
        except Exception:
            db_status = "error"
        worker_status = "unknown"
        if worker_service is not None:
            worker_status = worker_service.status()
        return jsonify({"status": "ok", "db": db_status, "worker": worker_status})

    @app.get("/api/config/recommendations")
    def config_recommendations():
        return jsonify(config.get_init_info())

    @app.post("/api/tasks")
    def create_task():
        if "file" not in request.files:
            return jsonify({"error": "file is required"}), 400

        upload = request.files["file"]
        if not upload.filename:
            return jsonify({"error": "filename is required"}), 400
        params = _parse_task_params(request.form)
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
        client_ip = client_ip.split(",")[0].strip()
        task_id, err = _handle_upload(upload, params, client_ip)
        if err:
            return jsonify({"error": err, "task_id": task_id}), 400
        return jsonify({"task_id": task_id}), 201

    @app.post("/api/tasks/batch")
    def create_tasks_batch():
        uploads = request.files.getlist("files")
        if not uploads:
            uploads = request.files.getlist("file")
        if not uploads:
            return jsonify({"error": "files are required"}), 400

        params = _parse_task_params(request.form)
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
        client_ip = client_ip.split(",")[0].strip()

        task_ids = []
        errors = []
        for upload in uploads:
            task_id, err = _handle_upload(upload, params, client_ip)
            if task_id:
                task_ids.append(task_id)
            if err:
                errors.append({"filename": upload.filename, "error": err, "task_id": task_id})

        return jsonify({"task_ids": task_ids, "errors": errors}), 201

    @app.get("/api/tasks/<task_id>")
    def get_task(task_id):
        task = db.get_task(task_id)
        if not task:
            return jsonify({"error": "task not found"}), 404

        task["task_params"] = json.loads(task.get("task_params", "{}"))
        task["video_info"] = json.loads(task.get("video_info", "{}"))
        task["task_progress"] = db.get_task_progress(task_id)
        task["segment_progress"] = db.get_latest_segment_progress(task_id)
        return jsonify(task)

    @app.get("/api/tasks/<task_id>/preview/<kind>")
    def get_preview(task_id, kind):
        run_dir = OUTPUT_ROOT / f"run_{task_id}"
        if kind == "original":
            path = run_dir / "preview_original.jpg"
            cache_dir = Path("/workspace/storage/data/preview_images") / task_id / "before"
            cache_path = cache_dir / "preview_last.jpg"
        elif kind == "upscaled":
            path = run_dir / "preview_upscaled.jpg"
            cache_dir = Path("/workspace/storage/data/preview_images") / task_id / "after"
            cache_path = cache_dir / "preview_last.jpg"
        else:
            return jsonify({"error": "invalid preview type"}), 400
        use_path = None
        latest_total = 0
        progress = db.get_latest_segment_progress(task_id) or {}
        last_done = int(progress.get("last_done_frame") or 0)
        start_frame = int(progress.get("start_frame") or 0)
        if last_done and start_frame:
            latest_total = start_frame + last_done - 1
        cached_total = _read_cached_frame(cache_dir)

        if latest_total and cached_total < latest_total:
            use_path = _try_recover_preview(task_id, kind)

        if not use_path:
            if path.exists():
                use_path = path
            elif cache_path.exists():
                use_path = cache_path
            else:
                use_path = _try_recover_preview(task_id, kind)

        if not use_path:
            return jsonify({"error": "preview not ready"}), 404
        resp = send_file(use_path, mimetype="image/jpeg")
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        return resp

    @app.post("/api/events")
    def ingest_events():
        payload = request.get_json(silent=True) or {}
        task_id = payload.get("task_id")
        if not task_id:
            return jsonify({"error": "task_id required"}), 400
        socketio = current_app.extensions.get("socketio")
        if socketio is not None:
            socketio.emit("frame", payload, to=task_id)
        return jsonify({"ok": True})

    @app.get("/api/tasks/<task_id>/result")
    def download_result(task_id):
        task = db.get_task(task_id)
        if not task or task.get("status") != "COMPLETED":
            return jsonify({"error": "result not available"}), 404

        params = json.loads(task.get("task_params", "{}"))
        filename = params.get("filename")
        if not filename:
            return jsonify({"error": "missing filename"}), 404

        stem = Path(filename).stem
        results = list(OUTPUT_ROOT.glob(f"sr_{stem}.*"))
        if not results:
            return jsonify({"error": "output missing"}), 404

        return send_file(results[0], as_attachment=True)

    @app.get("/")
    def index():
        return _serve_frontend()

    @app.get("/assets/<path:filename>")
    def assets(filename):
        dist_dir = Path(__file__).resolve().parents[3] / "app/src/Frontend/dist"
        assets_dir = dist_dir / "assets"
        return send_from_directory(assets_dir, filename)

    @app.get("/<path:_path>")
    def spa_fallback(_path):
        return _serve_frontend()

    def _serve_frontend():
        dist_dir = Path(__file__).resolve().parents[3] / "app/src/Frontend/dist"
        index_path = dist_dir / "index.html"
        if not index_path.exists():
            return "Frontend build not found.", 503
        return send_file(index_path)

    return app
