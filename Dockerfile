FROM realesrgan-base:20260108-0930

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/workspace/app

WORKDIR /workspace

# --- CACHE BUSTER TO ENSURE SOURCE CODE IS ALWAYS RE-COPIED AND RE-VERIFIED ---
RUN echo "Triggering Re-build (Force Update 2026-01-08-1051)"

# 1. Copy Source Code
COPY . .

# 2. Install Real-ESRGAN as a local library
RUN pip install -e vendor/Real-ESRGAN/

EXPOSE 8501

CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
