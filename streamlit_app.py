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

# Add DB module
import db

# Setup page
st.set_page_config(page_title="Real-ESRGAN Web App", page_icon="🚀", layout="wide")

st.image("Real-ESRGAN/assets/realesrgan_logo.png", width=320)

# Initialize DB
db.init_db()

# Increase upload limit
try:
    st.set_option("server.maxUploadSize", 1024)
except:
    pass

# --- Helper Utils ---
def get_client_ip():
    # Try modern st.context.headers (Streamlit 1.38+)
    try:
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            return st.context.headers.get("X-Forwarded-For", "unknown")
    except:
        pass
    
    # Fallback to deprecated method if context not available
    try:
        from streamlit.web.server.websocket_headers import _get_websocket_headers
        headers = _get_websocket_headers()
        return headers.get("X-Forwarded-For", "unknown")
    except:
        return "unknown"

def ffprobe_value(file, stream_selector, entry):
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", stream_selector,
             "-show_entries", entry, "-of", "default=nw=1", str(file)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        for line in proc.stdout.splitlines():
            if "=" in line:
                return line.split("=", 1)[1].strip()
    except:
        pass
    return ""

def parse_fps(file_path):
    fps_frac = ffprobe_value(file_path, "v:0", "stream=r_frame_rate")
    if not fps_frac: return 30.0
    if "/" in fps_frac:
        num, den = fps_frac.split("/", 1)
        return float(num) / float(den)
    return float(fps_frac)

# --- UI Layout ---
tab_create, tab_check = st.tabs(["🆕 Create Task", "🔍 Check Status"])

with tab_create:
    st.header("Create New Upscale Task")
    
    col1, col2 = st.columns(2)
    
    with col1:
        model_name = st.selectbox(
            "Model",
            [
                "realesrgan-x4plus", 
                "realesrnet-x4plus", 
                "realesrgan-x4plus-anime", 
                "realesr-animevideov3", 
                "realesr-general-x4v3",
                "realesr-general-wdn-x4v3"
            ],
            index=0
        )
        upscale = st.selectbox("Upscale factor", [2, 3, 4], index=1)
        input_type = st.radio("Input type", ["Video", "Image"], index=0, horizontal=True)

    with col2:
        tile = st.slider("Tile size (0 = no tiling)", 0, 512, 256, step=64)
        tile_pad = st.slider("Tile padding", 0, 64, 8, step=4)
        fp16 = st.checkbox("Use FP16 (half precision)", True)
        
        denoise_strength = 0.5
        if model_name == "realesr-general-x4v3":
            denoise_strength = st.slider("Denoise strength", 0.0, 1.0, 0.5, step=0.05)
            
        keep_audio = True
        crf = 18
        if input_type == "Video":
            keep_audio = st.checkbox("Keep original audio", True)
            crf = st.slider("CRF (Quality)", 14, 28, 18)

    uploaded_file = None
    if input_type == "Video":
        uploaded_file = st.file_uploader("Upload Video", type=["mp4", "mov", "mkv", "webm"])
    else:
        uploaded_file = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg", "webp"])

    if st.button("🚀 Submit Task", type="primary"):
        if not uploaded_file:
            st.error("Please upload a file first.")
        else:
            # 1. Generate ID & Paths
            task_id = uuid.uuid4().hex
            output_root = Path("/workspace/output")
            run_dir = output_root / f"run_{task_id}"
            run_dir.mkdir(parents=True, exist_ok=True)
            
            # 2. Save File
            filename = uploaded_file.name
            input_path = run_dir / filename
            with open(input_path, "wb") as f:
                f.write(uploaded_file.read())
            
            # 3. Gather Metadata
            file_size_mb = input_path.stat().st_size / (1024 * 1024)
            video_info = {
                "size_mb": round(file_size_mb, 2),
                "filename": filename
            }
            
            fps = 30.0
            if input_type == "Video":
                duration = ffprobe_value(input_path, "v:0", "format=duration")
                fps = parse_fps(input_path)
                video_info["duration"] = duration
                video_info["fps"] = fps
            
            # 4. Prepare Parameters
            task_params = {
                "model_name": model_name,
                "upscale": upscale,
                "tile": tile,
                "tile_pad": tile_pad,
                "fp16": fp16,
                "denoise_strength": denoise_strength,
                "input_type": input_type,
                "keep_audio": keep_audio,
                "crf": crf,
                "filename": filename,
                "fps": fps
            }
            
            # 5. Create Database Entry
            client_ip = get_client_ip()
            db.create_task(task_id, client_ip, task_params, video_info)
            
            # 6. Spawn Background Worker
            # Use subprocess.Popen to detach from Streamlit process
            cmd = ["python", "worker.py", "--task_id", task_id]
            subprocess.Popen(cmd, close_fds=True)
            
            st.success(f"Task created successfully!")
            st.write("Click to copy Task ID:")
            st.code(task_id, language=None)
            st.warning("⚠️ Please copy this Task ID to track your progress.")

with tab_check:
    st.header("Track Task Status")
    
    # Auto-refresh check
    auto_refresh = st.toggle("Auto-refresh previews (2s)", value=True)
    
    query_id = st.text_input("Enter Task ID", placeholder="e.g. c9e8fbbe...")
    
    if query_id:
        task_id = query_id.strip()
        task = db.get_task(task_id)
        
        if not task:
            st.error("Task not found.")
        else:
            # Display Status
            status = task['status']
            st.metric("Status", status, task['message'])
            
            progress = task['progress']
            st.progress(progress / 100.0)
            
            # Details (Tabular)
            with st.expander("Task Details"):
                try:
                    # Flatten JSONs for table view
                    v_info = json.loads(task['video_info'])
                    t_params = json.loads(task['task_params'])
                    
                    details = {
                        "Created At": str(task['created_at']),
                        "Client IP": task['client_ip'],
                        "Input File": v_info.get("filename"),
                        "Size (MB)": v_info.get("size_mb"),
                        "Duration (s)": v_info.get("duration", "N/A"),
                        "Model": t_params.get("model_name"),
                        "Upscale": t_params.get("upscale"),
                        "Tile Size": t_params.get("tile"),
                        "FP16": t_params.get("fp16")
                    }
                    st.table(details)
                except Exception as e:
                    st.error(f"Error parsing details: {e}")
            
            # Preview Images
            output_root = Path("/workspace/output")
            run_dir = output_root / f"run_{task_id}"
            
            prev_orig = run_dir / "preview_original.jpg"
            prev_ups = run_dir / "preview_upscaled.jpg"
            
            # Use columns for preview
            preview_container = st.container()
            
            if prev_orig.exists() and prev_ups.exists():
                with preview_container:
                    st.subheader("Preview (First Frame)")
                    c1, c2 = st.columns(2)
                    # Add a timestamp to URL to force browser cache reload
                    ts = int(time.time())
                    with c1:
                        st.image(str(prev_orig), caption="Original", use_container_width=True)
                    with c2:
                        st.image(str(prev_ups), caption="Upscaled", use_container_width=True)
            else:
                st.info("Previews will appear here once processing starts...")

            # Download Result
            if status == "COMPLETED":
                msg = task['message']
                if "Output:" in msg:
                    out_fname = msg.split("Output:")[1].strip()
                    out_path = output_root / out_fname
                    if out_path.exists():
                        st.success("Processing Complete!")
                        with open(out_path, "rb") as f:
                            st.download_button("Download Result", f, file_name=out_fname)
                    else:
                        st.warning("Output file not found on server.")
            
            # Auto-refresh logic
            if auto_refresh and status in ["PENDING", "PROCESSING"]:
                time.sleep(2)
                st.rerun()