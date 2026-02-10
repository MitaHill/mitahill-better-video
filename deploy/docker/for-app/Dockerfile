FROM node:20-alpine AS frontend-build

WORKDIR /frontend
COPY app/WebUI/package.json .
COPY app/WebUI/vite.config.js .
COPY app/WebUI/index.html .
COPY app/WebUI/src ./src
RUN npm install
RUN npm run build

FROM realesrgan-base:20260108-1353

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/workspace/app

WORKDIR /workspace

# --- CACHE BUSTER TO ENSURE SOURCE CODE IS ALWAYS RE-COPIED AND RE-VERIFIED ---
RUN echo "Triggering Re-build (Force Update 2026-01-08-1051)"

# 1. Copy Source Code (app-only)
COPY app/ /workspace/app/

# 2. Install web backend dependencies
RUN pip install --no-cache-dir \
    flask==2.3.3 \
    gunicorn==21.2.0 \
    flask-socketio==5.3.6 \
    eventlet==0.36.1 \
    openai-whisper==20231117 \
    voicefixer \
    deepfilternet \
    python-dotenv==1.0.1 \
    basicsr==1.4.2

# 3. Configure VoiceFixer cache (Symlink to pre-downloaded weights)
RUN mkdir -p /root/.cache/voicefixer/analysis_module/checkpoints && \
    ln -s /workspace/app/models/audio/voicefixer/analysis_module.ckpt /root/.cache/voicefixer/analysis_module/checkpoints/vf.ckpt && \
    ln -s /workspace/app/models/audio/voicefixer/model.ckpt-1490000_trimed.pt /root/.cache/voicefixer/model.ckpt-1490000_trimed.pt

# 3b. Pre-download DeepFilterNet2 weights to avoid runtime fetch
RUN mkdir -p /root/.cache/DeepFilterNet && \
    wget -q -O /root/.cache/DeepFilterNet/DeepFilterNet2.zip \
      https://github.com/Rikorose/DeepFilterNet/raw/main/models/DeepFilterNet2.zip && \
    unzip -q /root/.cache/DeepFilterNet/DeepFilterNet2.zip -d /root/.cache/DeepFilterNet && \
    rm /root/.cache/DeepFilterNet/DeepFilterNet2.zip

# 4. Copy built frontend assets
COPY --from=frontend-build /frontend/dist /workspace/app/WebUI/dist

EXPOSE 8501

CMD ["python3", "app/main.py"]
