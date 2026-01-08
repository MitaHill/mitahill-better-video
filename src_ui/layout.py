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
    try:
        cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", 
               "-show_entries", "stream=r_frame_rate,duration", "-of", "default=nw=1", str(file_path)]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
        data = {}
        for line in res.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                data[k] = v.strip()
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

def render_create_tab():
    # CSS to hide the default Streamlit file size limit text
    st.markdown("""
        <style>
        /* Hide the default limit text */
        section[data-testid="stFileUploader"] small {
            display: none !important;
        }
        /* Make our custom caption more prominent if needed */
        </style>
    """, unsafe_allow_html=True)

    st.header("Create New Upscale Task")
    col1, col2 = st.columns(2)
    
    with col1:
        opts = [
            "realesrgan-x4plus", "realesrnet-x4plus", "realesrgan-x4plus-anime",
            "realesr-animevideov3", "realesr-general-x4v3", "realesr-general-wdn-x4v3"
        ]
        
        # Descriptions map
        model_map = {
            "realesrgan-x4plus": "📸 通用 (画质优先/慢) - 适合真实照片",
            "realesrnet-x4plus": "🧹 通用 (去噪优先/慢) - 适合有噪点",
            "realesrgan-x4plus-anime": "🎨 动漫 (画质优先/慢) - 适合插画",
            "realesr-animevideov3": "🎬 动漫视频 (速度优先/快) - 适合长视频",
            "realesr-general-x4v3": "⚡ 通用 (速度优先/快) - 可调降噪",
            "realesr-general-wdn-x4v3": "🌫️ 通用 (强力降噪/快) - 速度优先"
        }
        
        def_idx = 0
        if config.DEFAULT_MODEL_NAME in opts:
            def_idx = opts.index(config.DEFAULT_MODEL_NAME)

        model_name = st.selectbox(
            "Model", opts, index=def_idx,
            format_func=lambda x: f"{x} - {model_map.get(x, '')}"
        )
        raw_model_name = model_name.split(" - ")[0]
        
        upscale = st.selectbox("Upscale factor", [2, 3, 4], index=1)
        input_type = st.radio("Input type", ["Video", "Image"], index=0, horizontal=True)

    with col2:
        tile = st.slider("Tile size (0=Auto)", 0, 512, config.DEFAULT_SMART_TILE_SIZE, step=64)
        tile_pad = st.slider("Tile padding", 0, 64, config.DEFAULT_TILE_PADDING, step=2)
        fp16 = st.checkbox("Use FP16", config.DEFAULT_FP16)
        
        denoise_strength = 0.5
        if "general" in raw_model_name:
            denoise_strength = st.slider("Denoise strength", 0.0, 1.0, 0.5, step=0.05)
            
        keep_audio = config.DEFAULT_KEEP_AUDIO
        crf = config.DEFAULT_CRF
        if input_type == "Video":
            keep_audio = st.checkbox("Keep audio", config.DEFAULT_KEEP_AUDIO)
            crf = st.slider("CRF (Quality)", 10, 30, config.DEFAULT_CRF)

    uploaded_file = None
    if input_type == "Video":
        uploaded_file = st.file_uploader(
            "Upload Video", 
            type=["mp4", "mov", "mkv", "webm"],
            help=f"Limit: {config.MAX_VIDEO_SIZE_MB} MB"
        )
        st.caption(f"Limit: {config.MAX_VIDEO_SIZE_MB} MB per file")
    else:
        uploaded_file = st.file_uploader(
            "Upload Image", 
            type=["png", "jpg", "jpeg", "webp"],
            help=f"Limit: {config.MAX_IMAGE_SIZE_MB} MB"
        )
        st.caption(f"Limit: {config.MAX_IMAGE_SIZE_MB} MB per file")

    if st.button("🚀 Submit Task", type="primary"):
        if not uploaded_file:
            st.error("Please upload a file.")
        else:
            # Check size logic
            file_size_mb = uploaded_file.size / (1024 * 1024)
            limit_mb = config.MAX_VIDEO_SIZE_MB if input_type == "Video" else config.MAX_IMAGE_SIZE_MB
            
            if file_size_mb > limit_mb:
                st.error(f"File too large! {file_size_mb:.2f} MB > {limit_mb} MB")
                return

            task_id = uuid.uuid4().hex
            output_root = Path("/workspace/output")
            run_dir = output_root / f"run_{task_id}"
            run_dir.mkdir(parents=True, exist_ok=True)
            
            filename = uploaded_file.name
            input_path = run_dir / filename
            with open(input_path, "wb") as f:
                f.write(uploaded_file.read())
            
            duration, fps = 0.0, 0.0
            if input_type == "Video":
                duration, fps = ffprobe_info(input_path)
            
            video_info = {
                "size_mb": round(file_size_mb, 2),
                "duration": duration,
                "fps": fps,
                "filename": filename
            }
            
            task_params = {
                "model_name": raw_model_name, "upscale": upscale, "tile": tile,
                "tile_pad": tile_pad, "fp16": fp16, "denoise_strength": denoise_strength,
                "input_type": input_type, "keep_audio": keep_audio, "crf": crf,
                "filename": filename, "fps": fps
            }
            
            db.create_task(task_id, get_client_ip(), task_params, video_info)
            
            st.success("Task Queued!")
            st.write("Your Task ID:")
            st.code(task_id, language=None)
            st.info("Worker process will pick this up automatically.")

def render_status_tab():

    st.header("Task Monitoring")

    

    # Auto-refresh toggle

    auto_refresh = st.toggle("Auto-refresh (every 3s)", value=True)

    

    # 1. Fetch all active tasks to show an overview

    active_tasks = db.get_unfinished_tasks()

    

    if active_tasks:

        st.subheader("Active Queue")

        for t in active_tasks:

            with st.container():

                # Display Task ID and Status

                c1, c2 = st.columns([1, 4])

                c1.write(f"**Task ID:** `{t['task_id'][:8]}...`")

                

                status = t['status']

                msg = t['message'] or "No message"

                

                if status == "PROCESSING":

                    c2.info(f"🔄 **{status}**: {msg}")

                else:

                    c2.warning(f"⏳ **{status}**: {msg}")

                

                # Progress Bar logic

                prog_val = t['progress'] if t['progress'] is not None else 0

                # Ensure it's 0-100 clamped, then to 0.0-1.0

                clamped_prog = max(0, min(100, prog_val))

                st.progress(clamped_prog / 100.0)

                st.write("---")

    else:

        st.info("No tasks are currently being processed.")



    # 2. Manual Query for Downloads/Full Details

    st.subheader("Query specific Task ID")

    query_id = st.text_input("Enter Full Task ID to download or view logs").strip()

    

    if query_id:

        task = db.get_task(query_id)

        if not task:

            st.error("Task not found.")

        else:

            st.write(f"### Full Details for `{query_id}`")

            st.write(f"**Status:** {task['status']}")

            st.write(f"**Last Message:** {task['message']}")

            

            # Details Expander

            with st.expander("Parameters & Info"):

                try:

                    v_info = json.loads(task['video_info'])

                    t_params = json.loads(task['task_params'])

                    st.json({"params": t_params, "video": v_info})

                except: pass



            if task['status'] == "COMPLETED":

                msg = task['message']

                if "Output:" in msg:

                    out_name = msg.split("Output:")[1].strip()

                    out_path = Path("/workspace/output") / out_name

                    if out_path.exists():

                        with open(out_path, "rb") as f:

                            st.download_button(f"📥 Download {out_name}", f, file_name=out_name)

                    else:

                        st.error("Result file not found on disk.")



    # 3. Handle Refresh

    if auto_refresh:

        # Only rerun if there are tasks in transition states

        if any(t['status'] in ["PENDING", "PROCESSING"] for t in active_tasks):

            time.sleep(3)

            st.rerun()
