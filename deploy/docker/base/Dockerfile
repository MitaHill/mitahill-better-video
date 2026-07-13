FROM ghcr.io/astral-sh/uv:0.8.13 AS uv

FROM python:3.10-slim-bookworm

# Keep this Dockerfile compatible with the legacy docker builder:
# no BuildKit-only syntax, heredocs, cache mounts, or frontend directives.

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    LD_LIBRARY_PATH=/usr/local/lib/python3.10/site-packages/torch/lib:/usr/local/lib/python3.10/dist-packages/torch/lib:/usr/local/nvidia/lib:/usr/local/nvidia/lib64

COPY --from=uv /uv /uvx /usr/local/bin/

ARG INSTALL_PREBUILT_FFMPEG=0
ARG FFMPEG_BUILD_URL=https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz
ARG FFMPEG_BUILD_SHA256=c5156dd8059afc7b42b4ea19ae0b7df67b8361036ccef110aa0078196ac00028

# Core system dependencies and tooling
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git wget curl ca-certificates xz-utils build-essential pkg-config \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libxfixes3 libxkbcommon0 \
    unzip aria2 tzdata \
 && rm -rf /var/lib/apt/lists/*

RUN if [ "$INSTALL_PREBUILT_FFMPEG" = "1" ]; then \
        mkdir -p /tmp/ffmpeg-build && \
        wget -q -O /tmp/ffmpeg.tar.xz "$FFMPEG_BUILD_URL" && \
        echo "$FFMPEG_BUILD_SHA256  /tmp/ffmpeg.tar.xz" | sha256sum -c - && \
        tar -xf /tmp/ffmpeg.tar.xz -C /tmp/ffmpeg-build --strip-components=1 && \
        install -m 0755 /tmp/ffmpeg-build/bin/ffmpeg /usr/local/bin/ffmpeg && \
        install -m 0755 /tmp/ffmpeg-build/bin/ffprobe /usr/local/bin/ffprobe && \
        rm -rf /tmp/ffmpeg-build /tmp/ffmpeg.tar.xz; \
    fi && \
    ffmpeg -hide_banner -version && \
    ffmpeg -hide_banner -encoders | grep -E "h264_nvenc|hevc_nvenc" >/dev/null

WORKDIR /workspace

# Python dependencies (heavy, rarely changes)
COPY pyproject.toml uv.lock /workspace/
RUN uv export --locked --no-emit-project --no-default-groups --group base \
        --format requirements.txt --no-hashes --output-file /tmp/base-requirements.txt && \
    uv pip install --system setuptools==69.5.1 wheel==0.45.1 numpy==1.24.4 cython==0.29.36 && \
    uv pip install --system \
        --index https://download.pytorch.org/whl/cu116 \
        --index-strategy unsafe-best-match \
        --no-build-isolation-package openai-whisper \
        --no-build-isolation-package basicsr \
        --no-build-isolation-package facexlib \
        --no-build-isolation-package gfpgan \
        --requirements /tmp/base-requirements.txt && \
    rm -f /tmp/base-requirements.txt

# Pre-download Real-ESRGAN weights (huge layer, fixed)
RUN mkdir -p /workspace/app/models/video && \
    wget -q -P /workspace/app/models/video https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth && \
    wget -q -P /workspace/app/models/video https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.1/RealESRNet_x4plus.pth && \
    wget -q -P /workspace/app/models/video https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth && \
    wget -q -P /workspace/app/models/video https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth && \
    wget -q -P /workspace/app/models/video https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth && \
    wget -q -P /workspace/app/models/video https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-wdn-x4v3.pth && \
    wget -q -O /workspace/app/models/video/Real_HAT_GAN_SRx4.pth https://huggingface.co/jaideepsingh/upscale_models/resolve/867e7c0ad519aba5d36b5bb4ef4a4a91781914c4/HAT/Real_HAT_GAN_SRx4.pth
