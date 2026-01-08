import streamlit as st
from pathlib import Path
import db
from src_ui.manager import WorkerManager
from src_ui.layout import render_create_tab, render_status_tab
import config

def app():
    # Init Config & DB
    config.initialize_context()
    db.init_db()
    
    # Configure Upload Limit (Global Max)
    # Streamlit requires this to be set before any upload interaction
    max_mb = max(config.MAX_VIDEO_SIZE_MB, config.MAX_IMAGE_SIZE_MB)
    try:
        st.set_option("server.maxUploadSize", max_mb)
    except:
        pass
    
    # Ensure worker
    mgr = WorkerManager()
    mgr.ensure_worker_running()
    
    st.set_page_config(page_title="Real-ESRGAN Web App", page_icon="🚀", layout="wide")
    root_dir = Path(__file__).resolve().parents[2]
    st.image(str(root_dir / "vendor/Real-ESRGAN/assets/realesrgan_logo.png"), width=320)
    
    tab1, tab2 = st.tabs(["🆕 Create Task", "🔍 Check Status"])
    with tab1:
        render_create_tab()
    with tab2:
        render_status_tab()

if __name__ == "__main__":
    app()
