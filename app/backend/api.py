from flask import Flask, jsonify, request, send_file, send_from_directory
from pathlib import Path
import uuid
import json

import config
import db
from .utils import ffprobe_info, secure_filename

OUTPUT_ROOT = Path("/workspace/output")


def create_app(worker_service=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = (
        max(config.MAX_VIDEO_SIZE_MB, config.MAX_IMAGE_SIZE_MB) * 1024 * 1024
    )

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
        return send_file(path, mimetype="image/jpeg")

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
        dist_dir = Path(__file__).resolve().parents[1] / "frontend/dist"
        assets_dir = dist_dir / "assets"
        return send_from_directory(assets_dir, filename)

    @app.get("/<path:_path>")
    def spa_fallback(_path):
        return _serve_frontend()

    def _serve_frontend():
        dist_dir = Path(__file__).resolve().parents[1] / "frontend/dist"
        index_path = dist_dir / "index.html"
        if not index_path.exists():
            return "Frontend build not found.", 503
        return send_file(index_path)

    return app
