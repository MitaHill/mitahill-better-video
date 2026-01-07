import cv2
import logging
from pathlib import Path
from realesrgan import RealESRGANer
from basicsr.archs.rrdbnet_arch import RRDBNet
from gfpgan import GFPGANer

logger = logging.getLogger("UPSCALER")

class Upscaler:
    def __init__(self, model_name, scale, tile, tile_pad, fp16, weights_dir, denoise_strength=None):
        logger.info(f"Initializing model {model_name} (scale: {scale}, fp16: {fp16})")
        self.model_name = model_name
        
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
            # scale is 4 for this model but can be used for 2/3 as well
            model = None # Handled by RealESRGANer internally for animevideo
            model_path = weights_dir / 'realesr-animevideov3.pth'
        else:
            logger.critical(f"Unknown model name: {model_name}")
            raise ValueError(f"Unknown model: {model_name}")

        if not model_path.exists():
            logger.critical(f"[FAILED] Model weight file not found at {model_path}")
            raise FileNotFoundError(f"Model weight missing: {model_path}")

        logger.debug(f"Loading weights from {model_path}...")
        self.upsampler = RealESRGANer(
            scale=scale,
            model_path=str(model_path),
            model=model,
            tile=tile,
            tile_pad=tile_pad,
            pre_pad=0,
            half=fp16
        )
        logger.info("Model loaded and ready.")

    def enhance(self, img_ndarray, outscale=2):
        """Enhances image ndarray (BGR)."""
        return self.upsampler.enhance(img_ndarray, outscale=outscale)

    def enhance_to_file(self, input_path, output_path, outscale=2):
        """Helper to enhance image file to another file directly."""
        img = cv2.imread(str(input_path))
        if img is None:
            logger.error(f"Failed to read image: {input_path}")
            return
        output, _ = self.enhance(img, outscale=outscale)
        cv2.imwrite(str(output_path), output)

def build_model(model_name, scale, tile, tile_pad, fp16, weights_dir, denoise_strength=None):
    return Upscaler(model_name, scale, tile, tile_pad, fp16, weights_dir, denoise_strength)