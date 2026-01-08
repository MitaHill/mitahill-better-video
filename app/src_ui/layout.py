import streamlit as st
import subprocess
import time
import json
import uuid
import shutil
from pathlib import Path
from PIL import Image

import db
import config

def get_client_ip():
    try:
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            return st.context.headers.get("X-Forwarded-For", "unknown")
    except:
        pass
    try:
        from streamlit.web.server.websocket_headers import _get_websocket_headers
        return _get_websocket_headers().get("X-Forwarded-For", "unknown")
    except:
        return "unknown"

def ffprobe_info(file_path):
    """Robustly extract video metadata using ffprobe."""
    try:
        # Use more standard format entries
        cmd = [
            "ffprobe", "-v", "quiet", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,duration",
            "-of", "json", str(file_path)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
        data = json.loads(res.stdout)
        stream = data.get("streams", [{}])[0]
        
        width = int(stream.get("width", 0))
        height = int(stream.get("height", 0))
        duration = float(stream.get("duration", 0))
        
        # FPS parsing
        fps_raw = stream.get("r_frame_rate", "30/1")
        if "/" in fps_raw:
            n, d = fps_raw.split("/")
            fps = float(n) / float(d) if float(d) != 0 else 30.0
        else:
            fps = float(fps_raw)
            
        return {"duration": duration, "fps": round(fps, 2), "width": width, "height": height}
    except Exception as e:
        print(f"ffprobe error: {e}")
        return {"duration": 0.0, "fps": 30.0, "width": 0, "height": 0}

def render_create_tab():
    st.header("🚀 Create New Task")
    col1, col2 = st.columns(2)
    
    with col1:
        opts = [
            "realesrgan-x4plus", "realesrnet-x4plus", "realesrgan-x4plus-anime",
            "realesr-animevideov3", "realesr-general-x4v3"
        ]
        model_map = {
            "realesrgan-x4plus": "📸 General (Slow) - Best for photos",
            "realesrnet-x4plus": "🧹 Denoise (Slow) - Good for noisy shots",
            "realesrgan-x4plus-anime": "🎨 Anime (Slow) - For illustrations",
            "realesr-animevideov3": "🎬 Anime Video (Fast) - Fast & smooth",
            "realesr-general-x4v3": "⚡ General (Fast) - Balanced speed"
        }
        model_name = st.selectbox("Model Selection", opts, format_func=lambda x: model_map[x])
        upscale = st.selectbox("Upscale Factor", [2, 3, 4], index=1)
        input_type = st.radio("Media Type", ["Video", "Image"], horizontal=True)

    with col2:
        tile = st.slider("Tile Size (0=Auto)", 0, 512, config.DEFAULT_SMART_TILE_SIZE, step=64)
        denoise = 0.5
        if "general" in model_name:
            denoise = st.slider("Denoise Strength", 0.0, 1.0, 0.5, 0.05)
        
        keep_audio = True
        crf = 18
        if input_type == "Video":
            keep_audio = st.checkbox("Preserve Audio Track", value=True)
            crf = st.slider("Quality (CRF: lower is better)", 10, 30, 18)

    uploaded_file = st.file_uploader(f"Upload {input_type}", type=["mp4", "mov", "png", "jpg", "jpeg", "webp"])

    if st.button("Submit to Queue", type="primary"):
        if not uploaded_file:
            st.error("Please select a file first.")
            return

        task_id = uuid.uuid4().hex
        run_dir = Path("/workspace/output") / f"run_{task_id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        
        input_path = run_dir / uploaded_file.name
        with open(input_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        info = ffprobe_info(input_path) if input_type == "Video" else {"width":0, "height":0, "fps":0, "duration":0}
        
        video_info = {
            "size_mb": round(uploaded_file.size / (1024*1024), 2),
            "filename": uploaded_file.name,
            **info
        }
        
        task_params = {
            "model_name": model_name, "upscale": upscale, "tile": tile,
            "denoise_strength": denoise, "input_type": input_type,
            "keep_audio": keep_audio, "crf": crf, "filename": uploaded_file.name,
            "tile_pad": config.DEFAULT_TILE_PADDING, "fp16": config.DEFAULT_FP16
        }
        
        db.create_task(task_id, get_client_ip(), task_params, video_info)
        st.success(f"Task submitted! ID: {task_id}")
        st.code(task_id)

def render_status_tab():
    st.header("🔍 Task Monitor")
    st.caption("Track progress, preview results, and download outputs once ready.")

    query_id = st.text_input(
        "Enter Task ID",
        placeholder="e.g. 884744db9e25435486a0e3d26fc5e634",
    ).strip()

    if not query_id:
        st.info("Paste a Task ID above to view live status updates.")
        return
    
    if query_id:
        task = db.get_task(query_id)
        if not task:
            st.warning("Task not found. It might be expired or the ID is incorrect.")
            return

        status_colors = {"PENDING": "gray", "PROCESSING": "blue", "COMPLETED": "green", "FAILED": "red"}
        color = status_colors.get(task["status"], "white")

        st.markdown(f"### Status: :{color}[{task['status']}]")
        status_cols = st.columns([2, 1])
        with status_cols[0]:
            st.code(query_id)
            if task["status"] == "PROCESSING":
                st.progress(task["progress"] / 100.0)
                st.caption(f"{task['progress']}% · {task['message']}")
            elif task["status"] == "FAILED":
                st.error(f"Error: {task['message']}")
            elif task["status"] == "COMPLETED":
                st.success("Processing complete. Download available below.")
        with status_cols[1]:
            st.metric("Progress", f"{task['progress']}%")
        
        # Display Info
        v_info = json.loads(task["video_info"])
        res_str = f"{v_info.get('width','?')}x{v_info.get('height','?')}"

        col1, col2, col3 = st.columns(3)
        col1.metric("File", v_info.get("filename", "Unknown")[:28])
        col2.metric("Resolution", res_str)
        col3.metric("Size", f"{v_info.get('size_mb', 0)} MB")

        # Previews
        run_dir = Path("/workspace/output") / f"run_{query_id}"
        p_orig = run_dir / "preview_original.jpg"
        p_ups = run_dir / "preview_upscaled.jpg"
        
        if p_orig.exists():
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.image(str(p_orig), caption="Original Sample")
            with c2: 
                if p_ups.exists():
                    st.image(str(p_ups), caption="Upscaled Preview")
                else:
                    st.info("Generating upscale preview...")
        
        # Download
        if task['status'] == "COMPLETED":
            out_name = f"sr_{Path(v_info['filename']).stem}"
            # Check for both mp4 and png/jpg
            results = list(Path("/workspace/output").glob(f"{out_name}.*"))
            if results:
                target = results[0]
                with open(target, "rb") as f:
                    st.download_button(f"📥 Download Result ({target.name})", f, file_name=target.name, type="primary")
            else:
                st.error("Output file disappeared from disk!")

        if task['status'] in ["PENDING", "PROCESSING"]:
            time.sleep(3)
            st.rerun()
