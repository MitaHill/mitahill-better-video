import gc
import json
import logging
import os
import shutil
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

from PIL import Image
from werkzeug.datastructures import FileStorage

from app.src.Api.services import create_enhance_task
from app.src.Config import settings as config
from app.src.Database import admin as db_admin
from app.src.Database import core as db
from app.src.Worker.gpu_model_coordinator import release_all_models
from app.src.Worker.pipelines.dispatch import process_task


logger = logging.getLogger("STARTUP_SELF_CHECK")


class StartupSelfCheckService:
    def __init__(self, *, config_payload):
        self.config_payload = config_payload or {}
        self.enabled = bool(((self.config_payload.get("runtime") or {}).get("startup_self_check_enabled")))
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.workspace = Path("/workspace/storage/selfcheck") / f"startup_{stamp}"

    @staticmethod
    def _cleanup_memory():
        import torch

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def run_if_enabled(self):
        if not self.enabled:
            logger.info("Startup self-check disabled, skip.")
            return
        logger.info("Startup self-check enabled, begin minimal GPU task check.")
        self.run()

    def run(self):
        task_id = ""
        try:
            self.workspace.mkdir(parents=True, exist_ok=True)
            self._check_nvidia_smi()
            task_id = self._create_probe_task()
            self._run_probe_task(task_id)
            logger.info("Startup self-check completed successfully, task_id=%s", task_id)
        except Exception as exc:
            logger.error("Startup self-check failed: %s", exc)
            logger.error("Startup self-check traceback:\n%s", traceback.format_exc())
            raise RuntimeError(f"启动自检失败: {exc}") from exc
        finally:
            release_all_models()
            self._cleanup_task(task_id)
            self.cleanup_workspace()
            self._cleanup_memory()

    def _check_nvidia_smi(self):
        logger.info("Self-check [GPU] running nvidia-smi...")
        result = subprocess.run(
            ["nvidia-smi"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"nvidia-smi failed: {detail}")
        logger.info("Self-check [GPU] nvidia-smi passed.")

    def _create_probe_image(self) -> Path:
        image_path = self.workspace / "startup_probe.png"
        Image.new("RGB", (32, 32), color=(12, 24, 48)).save(image_path)
        return image_path

    def _create_probe_task(self) -> str:
        image_path = self._create_probe_image()
        with image_path.open("rb") as handle:
            upload = FileStorage(stream=handle, filename=image_path.name, content_type="image/png")
            task_id, err = create_enhance_task(
                upload,
                {
                    "task_category": "enhance",
                    "input_type": "Image",
                    "model_name": "realesr-general-x4v3",
                    "upscale": 2,
                    "tile": 64,
                    "tile_pad": 10,
                    "fp16": True,
                    "denoise_strength": 0.5,
                    "crf": 18,
                    "output_codec": "h264",
                },
                client_ip="startup-self-check",
                output_root=Path("/workspace/storage/output"),
                upload_root=Path("/workspace/storage/upload"),
                max_video_mb=config.MAX_VIDEO_SIZE_MB,
                max_image_mb=config.MAX_IMAGE_SIZE_MB,
                logger=logger,
            )
        if err:
            raise RuntimeError(f"自检任务创建失败: {err}")
        if not task_id:
            raise RuntimeError("自检任务创建失败: 未返回 task_id")
        logger.info("Self-check [Task] created probe task: %s", task_id)
        return str(task_id)

    def _run_probe_task(self, task_id: str):
        task = db.get_task(task_id)
        if not task:
            raise RuntimeError(f"自检任务不存在: {task_id}")
        process_task(task)
        latest = db.get_task(task_id) or {}
        status = str(latest.get("status") or "").upper()
        if status != "COMPLETED":
            raise RuntimeError(f"自检任务失败: status={status}, message={latest.get('message') or '-'}")
        result_value = str(latest.get("result_path") or "").strip()
        if not result_value:
            raise RuntimeError("自检任务未记录结果文件路径")
        result_path = Path(result_value)
        if not result_path.exists():
            raise RuntimeError(f"自检任务未生成结果文件: {result_path}")
        logger.info("Self-check [Task] probe task completed: %s", result_path)

    def _cleanup_task(self, task_id: str):
        if not task_id:
            return
        try:
            latest = db.get_task(task_id)
            if latest and str(latest.get("status") or "").upper() not in {"COMPLETED", "FAILED"}:
                db.update_task_status(task_id, "FAILED", message="startup self-check cleanup")
            if db.get_task(task_id):
                db_admin.delete_task(task_id)
        except Exception:
            logger.warning("Failed to cleanup startup self-check task: %s", task_id, exc_info=True)

    def cleanup_workspace(self):
        try:
            shutil.rmtree(self.workspace, ignore_errors=True)
        except Exception:
            logger.warning("Failed to cleanup self-check workspace: %s", self.workspace, exc_info=True)


def run_startup_self_check_subprocess(*, config_payload):
    payload = config_payload or {}
    if not bool(((payload.get("runtime") or {}).get("startup_self_check_enabled"))):
        logger.info("Startup self-check disabled, skip.")
        return

    env = os.environ.copy()
    env["STARTUP_SELF_CHECK_CONFIG_JSON"] = json.dumps(payload, ensure_ascii=False)
    logger.info("Startup self-check enabled, run in isolated subprocess.")
    result = subprocess.run(
        [sys.executable, "-m", "app.src.Services.startup_self_check_service"],
        env=env,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"启动自检子进程失败，退出码: {result.returncode}")


def _main():
    from app.src.Config.logging_setup import configure_logging
    from app.src.Config import settings as config

    configure_logging(component="startup-self-check")
    config.initialize_context()
    db.init_db()
    raw = os.getenv("STARTUP_SELF_CHECK_CONFIG_JSON", "{}")
    try:
        payload = json.loads(raw) or {}
    except Exception:
        payload = {}
    StartupSelfCheckService(config_payload=payload).run_if_enabled()


if __name__ == "__main__":
    _main()
