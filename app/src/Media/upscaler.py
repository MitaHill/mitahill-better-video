import logging
from pathlib import Path
from PIL import Image
import numpy as np
import torch
from basicsr.archs.rrdbnet_arch import RRDBNet

from .realesrgan_runtime import RealESRGANer, SRVGGNetCompact

logger = logging.getLogger("UPSCALER")

class Upscaler:
    def __init__(self, model_name, scale, tile, tile_pad, fp16, weights_dir, denoise_strength=None):
        logger.info(f"Initializing model {model_name} (scale: {scale}, fp16: {fp16})")
        self.model_name = model_name
        model_scale = 4
        dni_weight = None
        
        # Mapping models
        if model_name == 'realesrgan-x4plus':
            model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
            model_path = weights_dir / 'RealESRGAN_x4plus.pth'
        elif model_name == 'realesrnet-x4plus':
            model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
            model_path = weights_dir / 'RealESRNet_x4plus.pth'
        elif model_name == 'realesrgan-x4plus-anime':
            model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4)
            model_path = weights_dir / 'RealESRGAN_x4plus_anime_6B.pth'
        elif model_name == 'realesr-animevideov3':
            model = SRVGGNetCompact(
                num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=16, upscale=4, act_type='prelu'
            )
            model_path = weights_dir / 'realesr-animevideov3.pth'
        elif model_name == 'realesr-general-x4v3':
            model = SRVGGNetCompact(
                num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4, act_type='prelu'
            )
            model_path = weights_dir / 'realesr-general-x4v3.pth'
            if denoise_strength is None:
                denoise_strength = 0.5
            if denoise_strength != 1:
                wdn_model_path = weights_dir / 'realesr-general-wdn-x4v3.pth'
                if not wdn_model_path.exists():
                    logger.critical(f"[FAILED] Model weight file not found at {wdn_model_path}")
                    raise FileNotFoundError(f"Model weight missing: {wdn_model_path}")
                model_path = [str(model_path), str(wdn_model_path)]
                dni_weight = [denoise_strength, 1 - denoise_strength]
        else:
            logger.critical(f"Unknown model name: {model_name}")
            raise ValueError(f"Unknown model: {model_name}")

        if isinstance(model_path, Path):
            if not model_path.exists():
                logger.critical(f"[FAILED] Model weight file not found at {model_path}")
                raise FileNotFoundError(f"Model weight missing: {model_path}")
            model_path = str(model_path)

        logger.debug(f"Loading weights from {model_path}...")
        self.upsampler = RealESRGANer(
            scale=model_scale,
            model_path=model_path,
            dni_weight=dni_weight,
            model=model,
            tile=tile,
            tile_pad=tile_pad,
            pre_pad=0,
            half=fp16 and torch.cuda.is_available()
        )
        logger.info("Model loaded and ready.")

    def enhance(self, img_ndarray, outscale=2):
        """Enhances image ndarray (BGR)."""
        return self.upsampler.enhance(img_ndarray, outscale=outscale)

    def enhance_to_file(self, input_path, output_path, outscale=2):
        """Helper to enhance image file to another file directly."""
        try:
            img = Image.open(input_path).convert("RGB")
        except Exception as exc:
            logger.error(f"Failed to read image: {input_path} ({exc})")
            return
        img_bgr = np.array(img)[:, :, ::-1]
        output, _ = self.enhance(img_bgr, outscale=outscale)
        out_rgb = output[:, :, ::-1]
        Image.fromarray(out_rgb).save(output_path)

def build_model(model_name, scale, tile, tile_pad, fp16, weights_dir, denoise_strength=None):
    return Upscaler(model_name, scale, tile, tile_pad, fp16, weights_dir, denoise_strength)
