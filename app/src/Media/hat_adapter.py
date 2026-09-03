import math
from importlib.metadata import distribution
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F

def _load_official_hat_class():
    """Load only HAT's official inference architecture."""
    # HAT's package import registers training architectures that collide with BasicSR
    arch_path = distribution("hat").locate_file("hat/archs/hat_arch.py")
    spec = spec_from_file_location("better_video_official_hat_arch", arch_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Official HAT architecture module is unavailable")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.HAT


class HATUpscaler:
    """Thin inference adapter around the official HAT architecture."""

    scale = 4
    window_size = 16

    def __init__(self, model_path, tile=128, tile_pad=32, variant="real"):
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model weight missing: {self.model_path}")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tile_size = self._align_tile(tile)
        self.tile_pad = self._align_tile_pad(tile_pad)
        self.model = self._load_model(variant)

    def _align_tile(self, value):
        value = max(self.window_size, int(value or 128))
        return max(self.window_size, (value // self.window_size) * self.window_size)

    def _align_tile_pad(self, value):
        value = max(self.window_size, int(value or self.window_size))
        return math.ceil(value / self.window_size) * self.window_size

    def _load_model(self, variant):
        depths = [6] * (12 if variant == "hat-l" else 6)
        model = _load_official_hat_class()(
            upscale=self.scale,
            in_chans=3,
            img_size=64,
            window_size=self.window_size,
            compress_ratio=3,
            squeeze_factor=30,
            conv_scale=0.01,
            overlap_ratio=0.5,
            img_range=1.0,
            depths=depths,
            embed_dim=180,
            num_heads=[6] * len(depths),
            mlp_ratio=2,
            upsampler="pixelshuffle",
            resi_connection="1conv",
        )
        checkpoint = torch.load(str(self.model_path), map_location="cpu")
        state = checkpoint.get("params_ema") or checkpoint.get("params") or checkpoint
        model.load_state_dict(state, strict=True)
        return model.eval().to(self.device)

    def _tensor_from_bgr(self, image):
        image = cv2.cvtColor(image.astype(np.float32) / 255.0, cv2.COLOR_BGR2RGB)
        tensor = torch.from_numpy(np.transpose(image, (2, 0, 1))).float().unsqueeze(0)
        return tensor.to(self.device)

    def _run_tiles(self, tensor):
        _, channels, height, width = tensor.shape
        output = tensor.new_zeros((1, channels, height * self.scale, width * self.scale))
        for y in range(math.ceil(height / self.tile_size)):
            for x in range(math.ceil(width / self.tile_size)):
                start_x, start_y = x * self.tile_size, y * self.tile_size
                end_x, end_y = min(start_x + self.tile_size, width), min(start_y + self.tile_size, height)
                pad_start_x, pad_start_y = max(start_x - self.tile_pad, 0), max(start_y - self.tile_pad, 0)
                pad_end_x, pad_end_y = min(end_x + self.tile_pad, width), min(end_y + self.tile_pad, height)
                tile = tensor[:, :, pad_start_y:pad_end_y, pad_start_x:pad_end_x]
                result = self.model(tile)
                output[:, :, start_y * self.scale:end_y * self.scale, start_x * self.scale:end_x * self.scale] = result[
                    :,
                    :,
                    (start_y - pad_start_y) * self.scale:(end_y - pad_start_y) * self.scale,
                    (start_x - pad_start_x) * self.scale:(end_x - pad_start_x) * self.scale,
                ]
        return output

    @torch.no_grad()
    def enhance(self, image, outscale=4):
        tensor = self._tensor_from_bgr(image)
        _, _, height, width = tensor.shape
        pad_h = (self.window_size - height % self.window_size) % self.window_size
        pad_w = (self.window_size - width % self.window_size) % self.window_size
        if pad_h or pad_w:
            tensor = F.pad(tensor, (0, pad_w, 0, pad_h), "reflect")

        output = self._run_tiles(tensor)
        if pad_h or pad_w:
            output = output[:, :, :height * self.scale, :width * self.scale]
        output = output.squeeze(0).float().cpu().clamp_(0, 1).numpy()
        output = cv2.cvtColor(np.transpose(output, (1, 2, 0)), cv2.COLOR_RGB2BGR)
        output = (output * 255.0).round().astype(np.uint8)
        if outscale is not None and float(outscale) != self.scale:
            output = cv2.resize(
                output,
                (int(width * outscale), int(height * outscale)),
                interpolation=cv2.INTER_LANCZOS4,
            )
        return output, "RGB"
