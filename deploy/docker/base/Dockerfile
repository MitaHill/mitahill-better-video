FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Core system dependencies and tooling
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3.10-dev python3.10-distutils python3.10-venv python3-pip \
    ffmpeg git wget curl ca-certificates build-essential pkg-config \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libxfixes3 libxkbcommon0 \
    nano vim less lsof htop tmux unzip zip rsync openssh-client \
    iputils-ping net-tools tzdata \
 && ln -s /usr/bin/python3.10 /usr/bin/python \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Python dependencies (heavy, rarely changes)
RUN python -m pip install --upgrade pip "setuptools<70" wheel "numpy<2" && \
    python -m pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cu116 \
        torch==1.13.1+cu116 torchvision==0.14.1+cu116 torchaudio==0.13.1+cu116 && \
    python -m pip install --no-cache-dir "setuptools<70" cython==0.29.36 && \
    python -m pip install --no-cache-dir --no-build-isolation openai-whisper==20231117 && \
    python -m pip install --no-cache-dir --no-build-isolation \
        basicsr==1.4.2 \
        facexlib==0.2.5 \
        gfpgan==1.3.5 && \
    python -m pip install --no-cache-dir \
        requests==2.31.0 \
        numpy==1.24.4 \
        opencv-python==4.8.0.76 \
        Pillow==9.5.0 \
        tqdm==4.65.0 \
        ffmpeg-python==0.2.0 \
        pyyaml==6.0 \
        flask==2.3.3 \
        gunicorn==21.2.0 \
        voicefixer \
        python-dotenv==1.0.1

# Pre-download weights (huge layer, fixed)
RUN mkdir -p /workspace/app/models/video /workspace/app/models/audio/voicefixer && \
    wget -q -P /workspace/app/models/video https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth && \
    wget -q -P /workspace/app/models/video https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.1/RealESRNet_x4plus.pth && \
    wget -q -P /workspace/app/models/video https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth && \
    wget -q -P /workspace/app/models/video https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth && \
    wget -q -P /workspace/app/models/video https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth && \
    wget -q -P /workspace/app/models/video https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-wdn-x4v3.pth && \
    # VoiceFixer weights
    wget -q -O /workspace/app/models/audio/voicefixer/analysis_module.ckpt https://huggingface.co/Diogodiogod/voicefixer-models/resolve/main/vf.ckpt && \
    wget -q -O /workspace/app/models/audio/voicefixer/model.ckpt-1490000_trimed.pt https://huggingface.co/Diogodiogod/voicefixer-models/resolve/main/model.ckpt-1490000_trimed.pt
