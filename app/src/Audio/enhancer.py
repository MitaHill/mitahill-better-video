import gc
import inspect
import logging
from pathlib import Path

import torch

logger = logging.getLogger("AUDIO_ENHANCER")


class AudioEnhancer:
    def __init__(self):
        self._model = None

    def _ensure_cache_links(self):
        cache_dir = Path("/root/.cache/voicefixer")
        analysis_cache = cache_dir / "analysis_module/checkpoints/vf.ckpt"
        synth_cache = cache_dir / "model.ckpt-1490000_trimed.pt"
        if analysis_cache.exists() and synth_cache.exists():
            logger.info("VoiceFixer cache ready: %s", cache_dir)
            return

        weights_dir = Path("/workspace/app/models/audio/voicefixer")
        analysis_src = weights_dir / "analysis_module.ckpt"
        synth_src = weights_dir / "model.ckpt-1490000_trimed.pt"
        if not (analysis_src.exists() and synth_src.exists()):
            logger.error("VoiceFixer packaged weights missing under %s", weights_dir)
            return

        (cache_dir / "analysis_module/checkpoints").mkdir(parents=True, exist_ok=True)
        try:
            if not analysis_cache.exists():
                analysis_cache.symlink_to(analysis_src)
                logger.info("VoiceFixer cache linked: %s", analysis_cache)
            if not synth_cache.exists():
                synth_cache.symlink_to(synth_src)
                logger.info("VoiceFixer cache linked: %s", synth_cache)
        except FileExistsError:
            pass

    def load_model(self):
        if self._model is None:
            self._ensure_cache_links()
            self._apply_torch_weight_norm_compat()
            required = [
                Path("/root/.cache/voicefixer/analysis_module/checkpoints/vf.ckpt"),
                Path("/root/.cache/voicefixer/model.ckpt-1490000_trimed.pt"),
            ]
            missing = [str(p) for p in required if not p.exists()]
            if missing:
                logger.error("VoiceFixer weights missing: %s", ", ".join(missing))
                logger.error(
                    "Expected cache under /root/.cache/voicefixer or packaged weights under /workspace/app/models/audio/voicefixer."
                )
                raise FileNotFoundError("VoiceFixer weights missing. Check image packaging.")
            from voicefixer import VoiceFixer
            self._model = VoiceFixer()
        return self._model

    @staticmethod
    def _apply_torch_weight_norm_compat():
        """VoiceFixer expects torch.nn.utils.parametrizations.weight_norm on old torch builds."""
        try:
            parametrizations = getattr(torch.nn.utils, "parametrizations", None)
            if parametrizations is None:
                return
            if hasattr(parametrizations, "weight_norm"):
                return
            legacy_weight_norm = getattr(torch.nn.utils, "weight_norm", None)
            if not callable(legacy_weight_norm):
                return

            def _compat_weight_norm(module, name="weight", dim=0):
                return legacy_weight_norm(module, name=name, dim=dim)

            setattr(parametrizations, "weight_norm", _compat_weight_norm)
            logger.info("Applied torch weight_norm compatibility patch for VoiceFixer.")
        except Exception:
            logger.warning("Failed to apply VoiceFixer weight_norm compatibility patch.", exc_info=True)

    def unload_model(self):
        if self._model is not None:
            del self._model
            self._model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _restore(self, model, input_path, output_path):
        restore = model.restore
        signature = inspect.signature(restore)
        params = signature.parameters
        args = []
        kwargs = {}

        input_keys = ("input", "input_path", "input_file", "input_wav", "input_filename")
        output_keys = ("output", "output_path", "output_file", "output_wav", "output_filename")

        for key in input_keys:
            if key in params:
                kwargs[key] = str(input_path)
                break
        else:
            args.append(str(input_path))

        for key in output_keys:
            if key in params:
                kwargs[key] = str(output_path)
                break
        else:
            args.append(str(output_path))

        if "cuda" in params:
            kwargs["cuda"] = True
        elif "use_cuda" in params:
            kwargs["use_cuda"] = True
        if "mode" in params:
            kwargs["mode"] = 0

        restore(*args, **kwargs)

    def process(self, input_path, output_path):
        input_path = Path(input_path)
        output_path = Path(output_path)
        logger.info("Audio enhancement started: %s", input_path.name)
        model = self.load_model()
        self._restore(model, input_path, output_path)
        self.unload_model()
        logger.info("Audio enhancement completed: %s", output_path.name)
