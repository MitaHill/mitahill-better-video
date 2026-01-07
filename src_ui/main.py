import streamlit as st
import db
from .manager import WorkerManager
from .layout import render_create_tab, render_status_tab

def app():
    # Init DB
    db.init_db()
    
    # Ensure worker
    mgr = WorkerManager()
    mgr.ensure_worker_running()
    
    st.set_page_config(page_title="Real-ESRGAN Web App", page_icon="🚀", layout="wide")
    st.image("Real-ESRGAN/assets/realesrgan_logo.png", width=320)
    
    tab1, tab2 = st.tabs(["🆕 Create Task", "🔍 Check Status"])
    with tab1:
        render_create_tab()
    with tab2:
        render_status_tab()

if __name__ == "__main__":
    app()
