from flask import Flask, jsonify, request, send_file, send_from_directory, current_app
from werkzeug.exceptions import RequestEntityTooLarge
from pathlib import Path
import uuid
import json

from app.src.Config import settings as config
from app.src.Database import core as db
from app.src.Utils.http import ffprobe_info, secure_filename, is_filename_safe

OUTPUT_ROOT = Path("/workspace/output")


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
        if not is_filename_safe(upload.filename):
            return jsonify({"error": "invalid filename"}), 400

        task_id = uuid.uuid4().hex
        run_dir = OUTPUT_ROOT / f"run_{task_id}"
        run_dir.mkdir(parents=True, exist_ok=True)

        filename = secure_filename(upload.filename)
        input_type = request.form.get("input_type", "Video")
        model_name = request.form.get("model_name", "realesrgan-x4plus")
        upscale = int(request.form.get("upscale", 3))
        tile = int(request.form.get("tile", config.DEFAULT_SMART_TILE_SIZE))
        denoise = float(request.form.get("denoise_strength", 0.5))
        keep_audio = request.form.get("keep_audio", "true").lower() == "true"
        audio_enhance = request.form.get(
            "audio_enhance", str(config.ENABLE_AUDIO_ENHANCEMENT)
        ).lower() == "true"
        pre_denoise_mode = request.form.get("pre_denoise_mode", config.PRE_DENOISE_MODE)
        crf = int(request.form.get("crf", 18))
        tile_pad = int(request.form.get("tile_pad", config.DEFAULT_TILE_PADDING))
        fp16 = request.form.get("fp16", str(config.DEFAULT_FP16)).lower() == "true"

        input_path = run_dir / filename
        upload.save(input_path)

        size_mb = input_path.stat().st_size / (1024 * 1024)
        max_mb = config.MAX_VIDEO_SIZE_MB if input_type == "Video" else config.MAX_IMAGE_SIZE_MB
        if size_mb > max_mb:
            input_path.unlink(missing_ok=True)
            return jsonify({"error": f"file exceeds limit ({max_mb} MB)"}), 400

        if input_type == "Video":
            info = ffprobe_info(input_path)
        else:
            info = {"width": 0, "height": 0, "fps": 0, "duration": 0}

        video_info = {
            "size_mb": round(size_mb, 2),
            "filename": filename,
            **info,
        }

        task_params = {
            "model_name": model_name,
            "upscale": upscale,
            "tile": tile,
            "denoise_strength": denoise,
            "input_type": input_type,
            "keep_audio": keep_audio,
            "audio_enhance": audio_enhance,
            "pre_denoise_mode": pre_denoise_mode,
            "crf": crf,
            "filename": filename,
            "tile_pad": tile_pad,
            "fp16": fp16,
        }

        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
        client_ip = client_ip.split(",")[0].strip()
        db.create_task(task_id, client_ip, task_params, video_info)
        return jsonify({"task_id": task_id}), 201

    @app.get("/api/tasks/<task_id>")
    def get_task(task_id):
        task = db.get_task(task_id)
        if not task:
            return jsonify({"error": "task not found"}), 404

        task["task_params"] = json.loads(task.get("task_params", "{}"))
        task["video_info"] = json.loads(task.get("video_info", "{}"))
        return jsonify(task)

    @app.get("/api/tasks/<task_id>/preview/<kind>")
    def get_preview(task_id, kind):
        run_dir = OUTPUT_ROOT / f"run_{task_id}"
        if kind == "original":
            path = run_dir / "preview_original.jpg"
        elif kind == "upscaled":
            path = run_dir / "preview_upscaled.jpg"
        else:
            return jsonify({"error": "invalid preview type"}), 400

        if not path.exists():
            return jsonify({"error": "preview not ready"}), 404
        resp = send_file(path, mimetype="image/jpeg")
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
