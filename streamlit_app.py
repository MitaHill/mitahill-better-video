# streamlit_app.py
import os
import sys
import math
import shutil
import tempfile
import subprocess
import sqlite3
import datetime
from pathlib import Path

import numpy as np
from PIL import Image
import streamlit as st

try:
    from tqdm import tqdm
except Exception:
    tqdm = None

import sys, os
repo_root = "/workspace/Real-ESRGAN"
if os.path.isdir(os.path.join(repo_root, "realesrgan")):
    sys.path.insert(0, repo_root)

from realesrgan import RealESRGANer
from realesrgan.archs.srvgg_arch import SRVGGNetCompact
from basicsr.archs.rrdbnet_arch import RRDBNet

# --- Database ---
DB_PATH = Path("/workspace/output/tasks.db")

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks
                 (run_token TEXT PRIMARY KEY, 
                  timestamp DATETIME,
                  input_type TEXT, 
                  filename TEXT, 
                  model TEXT, 
                  status TEXT)''')
    conn.commit()
    conn.close()

def log_task_start(run_token, input_type, filename, model):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO tasks (run_token, timestamp, input_type, filename, model, status) VALUES (?, ?, ?, ?, ?, ?)",
              (run_token, datetime.datetime.now(), input_type, filename, model, "RUNNING"))
    conn.commit()
    conn.close()

def update_task_status(run_token, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE tasks SET status = ? WHERE run_token = ?", (status, run_token))
    conn.commit()
    conn.close()

init_db()

st.image("Real-ESRGAN/assets/realesrgan_logo.png", width=320)
# Increase upload limit to 1 GB
try:
    st.set_option("server.maxUploadSize", 1024)
except Exception:
    pass


# Speed: let cuDNN autotune pick fastest algorithms for stable sizes
try:
    import torch
    torch.backends.cudnn.benchmark = True
except Exception:
    pass

# --- Session state  ---
def _init_state():
    ss = st.session_state
    ss.setdefault("run_token", None)         # unique token per run
    ss.setdefault("cancel", False)           # user-requested cancel
    ss.setdefault("worker_running", False)   # is a job active?
    ss.setdefault("last_config_hash", None)  # detect settings change
    ss.setdefault("ffmpeg_proc", None)       # handle to kill ffmpeg if needed

_init_state()

def config_hash(**kwargs) -> str:
    # Small stable fingerprint of current inputs/settings
    # Include anything that should invalidate a running job when changed.
    import hashlib, json
    return hashlib.md5(json.dumps(kwargs, sort_keys=True, default=str).encode()).hexdigest()

def new_run_token() -> str:
    import uuid
    tok = uuid.uuid4().hex
    st.session_state.run_token = tok
    return tok

def cancel_current_run():
    ss = st.session_state
    ss.cancel = True
    # Kill any running ffmpeg cleanly
    proc = ss.get("ffmpeg_proc", None)
    if proc and proc.poll() is None:
        try:
            import os, signal
            # Terminate the whole process group if started with setsid
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            try:
                proc.wait(timeout=1.0)
            except Exception:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    pass
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
    ss.ffmpeg_proc = None
    # Also invalidate the current run token so cooperative checks trip
    ss.run_token = None


# --------------------------
# Utilities
# --------------------------
def run_ffmpeg(args: list) -> None:
    """Cancellable ffmpeg: stores handle in session_state and checks cancel flag."""
    # Use a process group so we can kill child processes too
    import os, signal, time
    ss = st.session_state
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid  # create new process group
    )
    ss.ffmpeg_proc = proc
    # Poll so we can react to cancel quickly
    while True:
        if ss.cancel:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                # Give it a short grace period; then SIGKILL
                for _ in range(20):
                    if proc.poll() is not None:
                        break
                    time.sleep(0.05)
                if proc.poll() is None:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass
            ss.ffmpeg_proc = None
            raise RuntimeError("Cancelled")
        ret = proc.poll()
        if ret is not None:
            ss.ffmpeg_proc = None
            if ret != 0:
                err = (proc.stderr.read() or b"").decode("utf-8", errors="ignore")
                st.error(err)
                raise RuntimeError("ffmpeg failed")
            return
        time.sleep(0.1)

def ffmpeg_has_nvenc() -> bool:
    try:
        proc = subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-h", "encoder=h264_nvenc"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.returncode == 0
    except Exception:
        return False


def ffprobe_value(file: str, stream_selector: str, entry: str, default: str = "") -> str:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", stream_selector,
         "-show_entries", entry, "-of", "default=nw=1", file],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    for line in proc.stdout.splitlines():
        if "=" in line:
            return line.split("=", 1)[1].strip()
    return default

def parse_fraction(frac: str, fallback: float = 30.0) -> float:
    # "30000/1001" -> 29.97
    if not frac:
        return fallback
    if "/" in frac:
        num, den = frac.split("/", 1)
        try:
            return float(num) / float(den)
        except Exception:
            return fallback
    try:
        return float(frac)
    except Exception:
        return fallback

def ensure_weights(model_name: str, weights_dir: Path) -> Path:
    """
    Returns local ckpt path for a given built-in model name.
    If not found, attempts to download via URLs used by Real-ESRGAN releases.
    You can also just drop .pth files into ./data/models on the host.
    """
    weights_dir.mkdir(parents=True, exist_ok=True)
    # Common default filenames
    default_files = {
        "realesrgan-x4plus": "RealESRGAN_x4plus.pth",
        "realesrnet-x4plus": "RealESRNet_x4plus.pth",
        "realesr-animevideov3": "realesr-animevideov3.pth",
        "realesrgan-x4plus-anime": "RealESRGAN_x4plus_anime_6B.pth",
        "realesr-general-x4v3": "realesr-general-x4v3.pth",
        "realesr-general-wdn-x4v3": "realesr-general-wdn-x4v3.pth",
    }
    # Release URLs (stable as of public releases)
    urls = {
        "realesrgan-x4plus": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        "realesrnet-x4plus": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.1/RealESRNet_x4plus.pth",
        "realesr-animevideov3": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.3.0/realesr-animevideov3.pth",
        "realesrgan-x4plus-anime": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus_anime_6B.pth",
        "realesr-general-x4v3": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
        "realesr-general-wdn-x4v3": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-wdn-x4v3.pth",
    }
    fname = default_files.get(model_name, f"{model_name}.pth")
    local = weights_dir / fname
    if local.exists():
        return local

    # Try to fetch if internet is available in your environment; otherwise prompt user to place it manually.
    url = urls.get(model_name)
    if url:
        try:
            import urllib.request
            st.info(f"Downloading model weights: {fname}")
            urllib.request.urlretrieve(url, local)
            return local
        except Exception:
            st.warning(
                f"Could not download weights for '{model_name}'. "
                f"Please place '{fname}' in {weights_dir.resolve()} and retry."
            )
    else:
        st.warning(
            f"No known download URL for '{model_name}'. "
            f"Place its .pth into {weights_dir.resolve()}."
        )
    return local  # May not exist yet

def build_model(model_name: str, scale: int, tile: int, tile_pad: int, fp16: bool, weights_dir: Path, denoise_strength: float | None = None) -> RealESRGANer:
    # Pick arch by model_name
    if model_name in ("realesrgan-x4plus", "realesrnet-x4plus"):
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
        outscale = scale
    elif model_name == "realesrgan-x4plus-anime":
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
        outscale = scale
    elif model_name == "realesr-animevideov3":
        # compact VGG-style
        model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32,
                                upscale=4, act_type='prelu')
        outscale = scale
    elif model_name == "realesr-general-x4v3":
        # general model with adjustable denoise via DNI
        model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32,
                                upscale=4, act_type='prelu')
        outscale = scale
    else:
        raise ValueError(f"Unsupported model: {model_name}")

    # Resolve model paths; handle DNI if using general-x4v3 with denoise_strength
    dni_weight = None
    if model_name == "realesr-general-x4v3" and denoise_strength is not None and denoise_strength != 1.0:
        main_path = ensure_weights("realesr-general-x4v3", weights_dir)
        wdn_path = ensure_weights("realesr-general-wdn-x4v3", weights_dir)
        if not main_path.exists() or not wdn_path.exists():
            raise FileNotFoundError(
                "Weights not found for realesr-general-x4v3. Place both realesr-general-x4v3.pth and "
                "realesr-general-wdn-x4v3.pth in the models directory."
            )
        model_path = [str(main_path), str(wdn_path)]
        dni_weight = [float(denoise_strength), float(1.0 - denoise_strength)]
    else:
        model_path = ensure_weights(model_name, weights_dir)
        if not model_path.exists():
            raise FileNotFoundError(
                f"Weights not found for '{model_name}'. "
                f"Please place the .pth file at: {model_path}"
            )

    upsampler = RealESRGANer(
        scale=4,  # native model scale; we’ll use outscale to rescale again if needed
        model_path=model_path if isinstance(model_path, list) else str(model_path),
        dni_weight=dni_weight,
        model=model,
        tile=tile,
        tile_pad=tile_pad,
        pre_pad=0,
        half=fp16 and (torch_cuda_available()),
    )
    upsampler.model.name = model_name  # for logging
    return upsampler, outscale

def torch_cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False

def enhance_image(upsampler: RealESRGANer, img: Image.Image, outscale: int) -> Image.Image:
    img_np = np.array(img)[:, :, ::-1]  # RGB->BGR
    output, _ = upsampler.enhance(img_np, outscale=outscale)  # BGR
    out_rgb = output[:, :, ::-1]
    return Image.fromarray(out_rgb)

# --------------------------
# Sidebar controls
# --------------------------
with st.sidebar:
    st.header("Settings")
    model_name = st.selectbox(
        "Model",
        ["realesrgan-x4plus", "realesrnet-x4plus", "realesr-general-x4v3"],
        index=0
    )
    upscale = st.selectbox("Upscale factor", [2, 3, 4], index=1)
    # Balanced default for responsiveness (cancel between tiles)
    tile = st.slider("Tile size (0 = no tiling)", 0, 512, 256, step=64)
    tile_pad = st.slider("Tile padding", 0, 64, 8, step=4)
    fp16 = st.checkbox("Use FP16 (half precision)", True)

    # Denoise strength for general-x4v3 (0=more denoise, 1=less denoise)
    denoise_strength = None
    if model_name == "realesr-general-x4v3":
        denoise_strength = st.slider("Denoise strength (general-x4v3)", 0.0, 1.0, 0.5, step=0.05)

    # Input type selection
    input_type = st.radio("Input type", ["Video", "Image"], index=0, horizontal=True)

    # Video-only options
    keep_audio = st.checkbox("Keep original audio", True) if input_type == "Video" else False
    crf = st.slider("CRF (lower = higher quality, larger file)", 14, 28, 18) if input_type == "Video" else 18

    # History
    with st.expander("History"):
        try:
            conn = sqlite3.connect(DB_PATH)
            # Use pandas if available, else simple table
            import pandas as pd
            df = pd.read_sql_query("SELECT timestamp, input_type, filename, status FROM tasks ORDER BY timestamp DESC LIMIT 10", conn)
            st.dataframe(df)
            conn.close()
        except Exception:
            st.write("No history yet.")

# Uploaders by type
uploaded_video = None
uploaded_image = None
if 'input_type' in locals() and input_type == "Video":
    uploaded_video = st.file_uploader("Upload a video", type=["mp4", "mov", "mkv", "webm"])
else:
    uploaded_image = st.file_uploader(
        "Upload image(s)",
        type=["png", "jpg", "jpeg", "webp", "bmp", "tiff"],
        accept_multiple_files=True,
    )

start = st.button("Start upscaling")

with st.sidebar:
    st.caption("— Runtime —")
    stop_clicked = st.button("⛔ Stop current run", type="secondary")

if stop_clicked:
    cancel_current_run()
    st.rerun() 
    st.warning("Stopping current run…")

# Compute a hash of current settings + file name to auto-cancel on change
current_cfg = {
    "model_name": model_name,
    "upscale": upscale,
    "tile": tile,
    "tile_pad": tile_pad,
    "fp16": fp16,
    "denoise_strength": denoise_strength,
    "input_type": input_type,
    "keep_audio": keep_audio,
    "crf": crf,
    "filename": (
        uploaded_video.name if uploaded_video else (
            [f.name for f in uploaded_image] if uploaded_image else None
        )
    ),
}
cfg_hash = config_hash(**current_cfg)

# Auto-cancel if settings changed mid-run
if st.session_state.worker_running and st.session_state.last_config_hash and st.session_state.last_config_hash != cfg_hash:
    cancel_current_run()

# --------------------------
# Main flow
# --------------------------
if input_type == "Video" and uploaded_video and start and not st.session_state.worker_running:
    # Mark job as active
    st.session_state.worker_running = True
    st.session_state.cancel = False
    st.session_state.last_config_hash = cfg_hash
    run_token = new_run_token()
    log_task_start(run_token, "Video", uploaded_video.name, model_name)

    try:
        # Persistent output workspace under /workspace/output
        output_root = Path("/workspace/output")
        output_root.mkdir(parents=True, exist_ok=True)
        run_dir = output_root / f"run_{run_token}"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Prefer existing /workspace/data/models; else use /workspace/output/models
        data_models = Path("/workspace/data/models")
        weights_dir = data_models if data_models.exists() else (output_root / "models")
        weights_dir.mkdir(parents=True, exist_ok=True)

        in_path = run_dir / uploaded_video.name
        with open(in_path, "wb") as f:
            f.write(uploaded_video.read())

            # Before long ops, re-check token/cancel
            if st.session_state.cancel or st.session_state.run_token != run_token:
                raise RuntimeError("Cancelled")

            # Probe
            fps_frac = ffprobe_value(str(in_path), "v:0", "stream=r_frame_rate", "30/1")
            fps = parse_fraction(fps_frac, 30.0)
            has_audio = bool(ffprobe_value(str(in_path), "a", "stream=index", ""))
            st.write(f"Detected **FPS**: `{fps_frac}` ({fps:.3f})  |  **Audio**: {'Yes' if has_audio else 'No'}")

            # Extract frames
            in_frames = run_dir / "frames_in"
            out_frames = run_dir / "frames_out"
            in_frames.mkdir(parents=True, exist_ok=True)
            out_frames.mkdir(parents=True, exist_ok=True)

            st.info("Extracting frames…")
            run_ffmpeg([
                "ffmpeg", "-y", "-hwaccel", "cuda", "-i", str(in_path), "-vsync", "0",
                "-q:v", "2", str(in_frames / "f_%06d.jpg")
            ])

            if st.session_state.cancel or st.session_state.run_token != run_token:
                raise RuntimeError("Cancelled")

            audio_path = run_dir / "audio.m4a"
            if keep_audio and has_audio:
                run_ffmpeg(["ffmpeg", "-y", "-i", str(in_path), "-vn", "-acodec", "copy", str(audio_path)])

            # Load upsampler
            upsampler, outscale = build_model(model_name, upscale, tile, tile_pad, fp16, weights_dir, denoise_strength)

            # Process frames with live progress
            # Read JPEG frames (faster than PNG). Also include PNG for compatibility.
            frames = sorted(list(in_frames.glob("*.jpg")) + list(in_frames.glob("*.png")))
            n = len(frames)
            st.write(f"Processing **{n}** frames…")
            prog = st.progress(0)
            status = st.empty()

            iterator = frames if tqdm is None else tqdm(frames, desc="Upscaling frames", unit="frame")

            preview_before = st.empty()
            preview_after = st.empty()

            for i, fpath in enumerate(iterator, start=1):
                # Cooperative cancellation: token mismatch or cancel flag
                if st.session_state.cancel or st.session_state.run_token != run_token:
                    raise RuntimeError("Cancelled")

                img = Image.open(fpath).convert("RGB")
                try:
                    sr = enhance_image(upsampler, img, outscale=upscale)
                except RuntimeError as e:
                    # If OOM or other runtime issues, you can add auto-retry with smaller tiles here
                    raise

                sr.save(out_frames / fpath.name)
                status.write(f"Upscaled frame {i}/{n}")
                prog.progress(i / n)
                preview_before.image(img, caption=f"Original frame {i}", use_container_width=True)
                preview_after.image(sr, caption=f"Upscaled frame {i}", use_container_width=True)

            if st.session_state.cancel or st.session_state.run_token != run_token:
                raise RuntimeError("Cancelled")

            # Encode back to video
            st.info("Encoding final video…")
            video_out = output_root / f"sr_{in_path.stem}.mp4"

            # Determine frame pattern extension (prefer JPG)
            frame_ext = ".jpg" if any(out_frames.glob("*.jpg")) else ".png"
            frame_pattern = str(out_frames / f"f_%06d{frame_ext}")

            def base_encode_args():
                args = [
                    "ffmpeg", "-y",
                    "-framerate", f"{fps:.6f}",
                    "-start_number", "1",
                    "-i", frame_pattern,
                ]
                if keep_audio and has_audio and audio_path.exists():
                    args += ["-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0?", "-c:a", "copy"]
                return args

            def encode_with_libx264():
                args = base_encode_args() + [
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-preset", "medium", "-crf", str(crf),
                    str(video_out)
                ]
                run_ffmpeg(args)

            
            encode_with_libx264()

            update_task_status(run_token, "COMPLETED")
            st.success("Done!")
            st.video(str(video_out))
            with open(video_out, "rb") as f:
                st.download_button("Download upscaled video", f, file_name=video_out.name)

    except RuntimeError as e:
        if "Cancelled" in str(e):
            update_task_status(run_token, "CANCELLED")
            st.warning("Run cancelled.")
        else:
            update_task_status(run_token, "FAILED")
            st.error(str(e))
    finally:
        st.session_state.worker_running = False
        st.session_state.cancel = False
        st.session_state.ffmpeg_proc = None

# --------------------------
# Image flow
# --------------------------
elif input_type == "Image" and uploaded_image and start and not st.session_state.worker_running:
    st.session_state.worker_running = True
    st.session_state.cancel = False
    st.session_state.last_config_hash = cfg_hash
    run_token = new_run_token()
    # For multiple files, log the first one or a summary
    fname_log = uploaded_image[0].name if uploaded_image else "unknown"
    if len(uploaded_image) > 1:
        fname_log += f" (+{len(uploaded_image)-1} others)"
    log_task_start(run_token, "Image", fname_log, model_name)

    try:
        # Persistent output workspace under /workspace/output
        output_root = Path("/workspace/output")
        output_root.mkdir(parents=True, exist_ok=True)
        run_dir = output_root / f"run_{run_token}"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Prefer existing /workspace/data/models; else use /workspace/output/models
        data_models = Path("/workspace/data/models")
        weights_dir = data_models if data_models.exists() else (output_root / "models")
        weights_dir.mkdir(parents=True, exist_ok=True)

        # Load upsampler once
        upsampler, outscale = build_model(model_name, upscale, tile, tile_pad, fp16, weights_dir, denoise_strength)

        files = uploaded_image  # list of UploadedFile
        n = len(files)
        st.write(f"Processing {n} image(s)…")
        prog = st.progress(0)
        status = st.empty()
        preview_before = st.empty()
        preview_after = st.empty()

        out_paths = []

        for i, uf in enumerate(files, start=1):
            if st.session_state.cancel or st.session_state.run_token != run_token:
                raise RuntimeError("Cancelled")

            in_path = run_dir / uf.name
            with open(in_path, "wb") as f:
                f.write(uf.read())

            img = Image.open(in_path).convert("RGB")

            sr = enhance_image(upsampler, img, outscale=upscale)

            img_out = output_root / f"sr_{in_path.stem}.png"
            sr.save(img_out)
            out_paths.append(img_out)

            status.write(f"Upscaled {i}/{n}: {uf.name}")
            prog.progress(i / n)
            # Show rolling preview of last processed image
            preview_before.image(img, caption=f"Original — {uf.name}", use_container_width=True)
            preview_after.image(sr, caption=f"Upscaled — {img_out.name}", use_container_width=True)

        # Package results as a zip for easy download
        import zipfile
        zip_out = output_root / f"sr_images_{run_token}.zip"
        with zipfile.ZipFile(zip_out, 'w', compression=zipfile.ZIP_STORED) as zf:
            for p in out_paths:
                zf.write(p, arcname=p.name)

        update_task_status(run_token, "COMPLETED")
        st.success("Done!")
        with open(zip_out, "rb") as f:
            st.download_button("Download all upscaled images (ZIP)", f, file_name=zip_out.name)

    except RuntimeError as e:
        if "Cancelled" in str(e):
            update_task_status(run_token, "CANCELLED")
            st.warning("Run cancelled.")
        else:
            update_task_status(run_token, "FAILED")
            st.error(str(e))
    finally:
        st.session_state.worker_running = False
        st.session_state.cancel = False
        st.session_state.ffmpeg_proc = None
