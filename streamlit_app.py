import os
import sys
import shutil
import time
import subprocess
import uuid
import json
from pathlib import Path

import streamlit as st
from PIL import Image

import db
import config

# --- Worker Manager (Singleton) ---
@st.cache_resource
class WorkerManager:
    def __init__(self):
        self.process = None

    def ensure_worker_running(self):
        # Check if process exists and is running
        if self.process is None or self.process.poll() is not None:
            print("WorkerManager: Starting worker process...")
            # Use separate process group/detached logic if needed, but basic Popen is fine for supervision
            self.process = subprocess.Popen(
                [sys.executable, "/workspace/worker.py"],
                cwd="/workspace",
                # Log stdout/stderr to file for debugging
                stdout=open("/workspace/output/worker.log", "a"),
                stderr=subprocess.STDOUT
            )
        else:
            # Worker is healthy
            pass

# Initialize Manager and ensure worker is running
worker_mgr = WorkerManager()
worker_mgr.ensure_worker_running()

# Setup page
st.set_page_config(page_title="Real-ESRGAN Web App", page_icon="🚀", layout="wide")
st.image("Real-ESRGAN/assets/realesrgan_logo.png", width=320)

# Initialize DB
db.init_db()

# --- Helper Utils ---
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
    # Return duration and fps
    try:
        cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", 
               "-show_entries", "stream=r_frame_rate,duration", "-of", "default=nw=1", str(file_path)]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
        data = {}
        for line in res.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                data[k] = v.strip()
        
        # Parse FPS
        fps = 30.0
        if "r_frame_rate" in data:
            if "/" in data["r_frame_rate"]:
                n, d = data["r_frame_rate"].split("/")
                fps = float(n)/float(d)
            else:
                fps = float(data["r_frame_rate"])
        
        return float(data.get("duration", 0)), fps
    except:
        return 0.0, 30.0

# --- UI Layout ---
tab_create, tab_check = st.tabs(["🆕 Create Task", "🔍 Check Status"])

with tab_create:
    st.header("Create New Upscale Task")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Load default model from config if matches options
        opts = [
            "realesrgan-x4plus", "realesrnet-x4plus", "realesrgan-x4plus-anime",
            "realesr-animevideov3", "realesr-general-x4v3", "realesr-general-wdn-x4v3"
        ]
        def_idx = 0
        if config.DEFAULT_MODEL_NAME in opts:
            def_idx = opts.index(config.DEFAULT_MODEL_NAME)

        model_name = st.selectbox("Model", opts, index=def_idx)
        upscale = st.selectbox("Upscale factor", [2, 3, 4], index=opts.index(f"realesrgan-x4plus") if False else 1) # hard to map upscale to config default index cleanly, keep 2,3,4
        input_type = st.radio("Input type", ["Video", "Image"], index=0, horizontal=True)

    with col2:
        # Smart Tile Size
        tile = st.slider("Tile size (0=Auto)", 0, 512, config.DEFAULT_SMART_TILE_SIZE, step=64, help="Calculated based on VRAM")
        tile_pad = st.slider("Tile padding", 0, 64, config.DEFAULT_TILE_PADDING, step=2)
        fp16 = st.checkbox("Use FP16", config.DEFAULT_FP16)
        
        denoise_strength = 0.5
        if "general" in model_name:
            denoise_strength = st.slider("Denoise strength", 0.0, 1.0, 0.5, step=0.05)
            
        keep_audio = config.DEFAULT_KEEP_AUDIO
        crf = config.DEFAULT_CRF
        if input_type == "Video":
            keep_audio = st.checkbox("Keep audio", config.DEFAULT_KEEP_AUDIO)
            crf = st.slider("CRF (Quality)", 10, 30, config.DEFAULT_CRF)

    if input_type == "Video":
        uploaded_file = st.file_uploader("Upload Video", type=["mp4", "mov", "mkv", "webm"])
    else:
        uploaded_file = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg", "webp"])

    if st.button("🚀 Submit Task", type="primary"):
        if not uploaded_file:
            st.error("Please upload a file.")
        else:
            task_id = uuid.uuid4().hex
            output_root = Path("/workspace/output")
            run_dir = output_root / f"run_{task_id}"
            run_dir.mkdir(parents=True, exist_ok=True)
            
            filename = uploaded_file.name
            input_path = run_dir / filename
            with open(input_path, "wb") as f:
                f.write(uploaded_file.read())
            
            size_mb = input_path.stat().st_size / (1024*1024)
            duration, fps = 0.0, 0.0
            if input_type == "Video":
                duration, fps = ffprobe_info(input_path)
            
            video_info = {
                "size_mb": round(size_mb, 2),
                "duration": duration,
                "fps": fps,
                "filename": filename
            }
            
            task_params = {
                "model_name": model_name, "upscale": upscale, "tile": tile,
                "tile_pad": tile_pad, "fp16": fp16, "denoise_strength": denoise_strength,
                "input_type": input_type, "keep_audio": keep_audio, "crf": crf,
                "filename": filename, "fps": fps
            }
            
            db.create_task(task_id, get_client_ip(), task_params, video_info)
            
            st.success("Task Queued!")
            st.write("Your Task ID:")
            st.code(task_id, language=None)
            st.info("Worker process will pick this up automatically.")

with tab_check:
    st.header("Check Status")
    auto_refresh = st.toggle("Auto-refresh", value=True)
    query_id = st.text_input("Task ID")
    
    if query_id:
        task = db.get_task(query_id.strip())
        if not task:
            st.error("Task not found or expired.")
        else:
            st.metric("Status", task['status'], task['message'])
            st.progress(task['progress']/100)
            
            # Preview
            run_dir = Path(f"/workspace/output/run_{query_id}")
            p_orig = run_dir / "preview_original.jpg"
            p_ups = run_dir / "preview_upscaled.jpg"
            
            if p_orig.exists() and p_ups.exists():
                c1, c2 = st.columns(2)
                with c1: st.image(str(p_orig), caption="Original")
                with c2: st.image(str(p_ups), caption="Upscaled")
            
            if task['status'] == "COMPLETED":
                # Try to find output file from message
                msg = task['message']
                if "Output:" in msg:
                    out_name = msg.split("Output:")[1].strip()
                    out_path = Path("/workspace/output") / out_name
                    if out_path.exists():
                        with open(out_path, "rb") as f:
                            st.download_button("Download", f, file_name=out_name)

            if auto_refresh and task['status'] in ["PENDING", "PROCESSING"]:
                time.sleep(2)
                st.rerun()
