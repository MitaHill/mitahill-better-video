ARG NPM_REGISTRY=https://registry.npmmirror.com
FROM node:20-alpine AS frontend-build

WORKDIR /frontend
RUN npm config set registry ${NPM_REGISTRY}
COPY app/frontend/package.json .
COPY app/frontend/vite.config.js .
COPY app/frontend/index.html .
COPY app/frontend/src ./src
RUN npm install
RUN npm run build

ARG PIP_INDEX_URL=https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
ARG PIP_TRUSTED_HOST=mirrors.tuna.tsinghua.edu.cn
ARG PYTORCH_WHL=https://mirrors.aliyun.com/pytorch-wheels/torch_stable.html

FROM realesrgan-base:20260108-0930

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST} \
    PYTHONPATH=/workspace/app

WORKDIR /workspace

# --- CACHE BUSTER TO ENSURE SOURCE CODE IS ALWAYS RE-COPIED AND RE-VERIFIED ---
RUN echo "Triggering Re-build (Force Update 2026-01-08-1051)"

# 1. Copy Source Code
COPY . .

# 2. Install Real-ESRGAN as a local library
RUN pip install -e vendor/Real-ESRGAN/

# 3. Install web backend dependencies
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} flask==2.3.3 gunicorn==21.2.0

# 4. Copy built frontend assets
COPY --from=frontend-build /frontend/dist /workspace/app/frontend/dist

EXPOSE 8501

CMD ["python3", "/workspace/app/backend/main.py"]
