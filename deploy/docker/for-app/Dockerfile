FROM node:20-alpine AS frontend-build

# Keep this Dockerfile compatible with the legacy docker builder:
# no BuildKit-only syntax, heredocs, cache mounts, or frontend directives.

WORKDIR /frontend
COPY app/WebUI/package.json .
COPY app/WebUI/package-lock.json .
COPY app/WebUI/vite.config.js .
COPY app/WebUI/index.html .
COPY app/WebUI/public ./public
COPY app/WebUI/src ./src
RUN npm ci
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.8.13 AS uv

FROM base_better_video:20260210-2330

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    PYTHONPATH=/workspace/app

WORKDIR /workspace

COPY --from=uv /uv /uvx /usr/local/bin/

# --- CACHE BUSTER TO ENSURE SOURCE CODE IS ALWAYS RE-COPIED AND RE-VERIFIED ---
RUN echo "Triggering Re-build (Force Update 2026-01-08-1051)"

RUN apt-get update && \
    apt-get install -y --no-install-recommends fonts-noto-cjk && \
    rm -rf /var/lib/apt/lists/*

# 1. Copy Source Code (app-only)
COPY app/ /workspace/app/

# 2. Install web backend dependencies
COPY pyproject.toml uv.lock /workspace/
RUN uv export --locked --no-emit-project --no-default-groups --group base --group app \
        --format requirements.txt --no-hashes --output-file /tmp/app-requirements.txt && \
    uv pip install --system setuptools==69.5.1 wheel==0.45.1 numpy==1.24.4 cython==0.29.36 && \
    uv pip install --system \
        --index https://download.pytorch.org/whl/cu116 \
        --index-strategy unsafe-best-match \
        --no-build-isolation-package openai-whisper \
        --no-build-isolation-package basicsr \
        --no-build-isolation-package facexlib \
        --no-build-isolation-package gfpgan \
        --requirements /tmp/app-requirements.txt && \
    rm -f /tmp/app-requirements.txt

# 3. Configure VoiceFixer cache from bundled weights when present.
RUN mkdir -p /root/.cache/voicefixer/analysis_module/checkpoints /root/.cache/voicefixer/synthesis_module/44100 && \
    if [ -f /workspace/app/models/audio/voicefixer/analysis_module.ckpt ]; then \
        ln -sf /workspace/app/models/audio/voicefixer/analysis_module.ckpt /root/.cache/voicefixer/analysis_module/checkpoints/vf.ckpt; \
    fi && \
    if [ -f /workspace/app/models/audio/voicefixer/synthesis_module/44100/model.ckpt-1490000_trimed.pt ]; then \
        ln -sf /workspace/app/models/audio/voicefixer/synthesis_module/44100/model.ckpt-1490000_trimed.pt /root/.cache/voicefixer/synthesis_module/44100/model.ckpt-1490000_trimed.pt; \
    fi

# 3b. Provide bundled DeepFilterNet2 weights to avoid runtime/build-time fetch
RUN mkdir -p /root/.cache/DeepFilterNet && \
    cp -a /workspace/app/models/audio/deepfilternet/DeepFilterNet2 /root/.cache/DeepFilterNet/

# 4. Copy built frontend assets
COPY --from=frontend-build /frontend/dist /workspace/app/WebUI/dist

EXPOSE 8501

CMD ["python3", "app/main.py"]
