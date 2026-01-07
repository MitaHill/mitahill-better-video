import sys
import os
import shutil
import urllib.request
from pathlib import Path

# Path setup for Real-ESRGAN submodule
repo_root = "/workspace/Real-ESRGAN"
if os.path.isdir(os.path.join(repo_root, "realesrgan")):
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

try:
    import torch
    from realesrgan import RealESRGANer
    from realesrgan.archs.srvgg_arch import SRVGGNetCompact
    from basicsr.archs.rrdbnet_arch import RRDBNet
except ImportError:
    pass

def ensure_weights(model_name, weights_dir):
    weights_dir = Path(weights_dir)
    weights_dir.mkdir(parents=True, exist_ok=True)
    
    default_files = {
        "realesrgan-x4plus": "RealESRGAN_x4plus.pth",
        "realesrnet-x4plus": "RealESRNet_x4plus.pth",
        "realesr-animevideov3": "realesr-animevideov3.pth",
        "realesrgan-x4plus-anime": "RealESRGAN_x4plus_anime_6B.pth",
        "realesr-general-x4v3": "realesr-general-x4v3.pth",
        "realesr-general-wdn-x4v3": "realesr-general-wdn-x4v3.pth",
    }
    urls = {
        "realesrgan-x4plus": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        "realesrnet-x4plus": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.1/RealESRNet_x4plus.pth",
        "realesr-animevideov3": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth",
        "realesrgan-x4plus-anime": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
        "realesr-general-x4v3": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
        "realesr-general-wdn-x4v3": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-wdn-x4v3.pth",
    }
    
    fname = default_files.get(model_name, f"{model_name}.pth")
    local_path = weights_dir / fname
    
    if not local_path.exists():
        # Check pre-downloaded
        pre_downloaded = Path("/workspace/weights") / fname
        if pre_downloaded.exists():
            shutil.copy(pre_downloaded, local_path)
            return local_path

        url = urls.get(model_name)
        if url:
            print(f"Downloading {fname}...")
            try:
                urllib.request.urlretrieve(url, local_path)
            except Exception as e:
                print(f"Download failed: {e}")
    return local_path

def build_model(model_name, scale, tile, tile_pad, fp16, weights_dir, denoise_strength):
    weights_dir = Path(weights_dir)
    
    if model_name == "realesr-general-x4v3" and denoise_strength is not None and denoise_strength != 1.0:
        main_path = ensure_weights("realesr-general-x4v3", weights_dir)
        wdn_path = ensure_weights("realesr-general-wdn-x4v3", weights_dir)
        model_path = [str(main_path), str(wdn_path)]
        dni_weight = [float(denoise_strength), float(1.0 - denoise_strength)]
    else:
        model_path = str(ensure_weights(model_name, weights_dir))
        dni_weight = None
    
    if model_name in ("realesrgan-x4plus", "realesrnet-x4plus"):
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    elif model_name == "realesrgan-x4plus-anime":
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    elif model_name in ("realesr-animevideov3", "realesr-general-x4v3"):
        model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4, act_type='prelu')
    else:
        # Fallback
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)

    upsampler = RealESRGANer(
        scale=4,
        model_path=model_path,
        dni_weight=dni_weight,
        model=model,
        tile=tile,
        tile_pad=tile_pad,
        pre_pad=0,
        half=fp16 and torch.cuda.is_available(),
        gpu_id=0 if torch.cuda.is_available() else None 
    )
    return upsampler
