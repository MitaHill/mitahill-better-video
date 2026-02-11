import logging
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable, Dict, Optional

from app.src.Database import transcription_admin as db_transcription

from .model_checks import verify_model_hashes, warmup_transcription_model
from .transcription_catalog import fetch_hf_model_files, get_faster_required_files, get_model_entry
from .transcription_config import get_transcription_config

logger = logging.getLogger("ADMIN_MODEL_DOWNLOAD")

_PROGRESS_RE = re.compile(r"\((\d{1,3})%\)")
_active_threads: Dict[str, threading.Thread] = {}
_active_processes: Dict[str, subprocess.Popen] = {}
_cancel_requested: set[str] = set()
_lock = threading.Lock()


def _find_aria2c() -> str:
    path = shutil.which("aria2c")
    if not path:
        raise RuntimeError("未找到 aria2c，请先在基础镜像安装 aria2")
    return path


def _run_aria2(
    *,
    job_id: str,
    url: str,
    output_path: Path,
    aria2_config: Dict,
    progress_callback: Optional[Callable[[float, str], None]] = None,
):
    aria2 = _find_aria2c()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        aria2,
        "--continue=true",
        "--allow-overwrite=true",
        f"--split={int(aria2_config.get('split') or 16)}",
        f"--max-connection-per-server={int(aria2_config.get('max_connection_per_server') or 16)}",
        f"--max-tries={int(aria2_config.get('max_tries') or 10)}",
        f"--retry-wait={int(aria2_config.get('retry_wait') or 2)}",
        f"--connect-timeout={int(aria2_config.get('connect_timeout_sec') or 10)}",
        f"--timeout={int(aria2_config.get('timeout_sec') or 120)}",
        "--summary-interval=1",
        "--console-log-level=warn",
        "--dir",
        str(output_path.parent),
        "--out",
        output_path.name,
        str(url),
    ]

    proxy = str(aria2_config.get("proxy") or "").strip()
    if proxy:
        cmd.extend(["--all-proxy", proxy])

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    with _lock:
        _active_processes[job_id] = process

    try:
        for line in process.stdout or []:
            if _is_cancel_requested(job_id):
                try:
                    process.terminate()
                except Exception:
                    pass
            text = str(line or "").strip()
            match = _PROGRESS_RE.search(text)
            if progress_callback and match:
                try:
                    progress_callback(float(match.group(1)), text)
                except Exception:
                    pass
        code = process.wait()
    finally:
        with _lock:
            _active_processes.pop(job_id, None)
        if process.stdout:
            process.stdout.close()

    if _is_cancel_requested(job_id):
        raise RuntimeError("任务已取消")
    if code != 0:
        raise RuntimeError(f"aria2 下载失败，退出码: {code}")


def _run_openai_download(job_id: str, model_entry: Dict, aria2_config: Dict):
    target_path = Path(model_entry.get("local_path") or "")

    def on_progress(percent: float, _line: str):
        db_transcription.update_model_download_job(
            job_id,
            status="RUNNING",
            progress=max(0.0, min(95.0, percent * 0.95 / 100.0 * 100.0)),
            message=f"下载中: {percent:.0f}%",
        )

    _run_aria2(
        job_id=job_id,
        url=str(model_entry.get("download_url") or ""),
        output_path=target_path,
        aria2_config=aria2_config,
        progress_callback=on_progress,
    )


def _run_faster_download(job_id: str, model_entry: Dict, aria2_config: Dict):
    repo_id = str(model_entry.get("repo_id") or "").strip()
    if not repo_id:
        raise RuntimeError("faster-whisper 模型缺少 repo_id")

    remote = fetch_hf_model_files(repo_id)
    required_files = get_faster_required_files()
    local_dir = Path(model_entry.get("local_path") or "")
    local_dir.mkdir(parents=True, exist_ok=True)

    file_weights = []
    for name in required_files:
        size = int((remote.get(name) or {}).get("size") or 0)
        file_weights.append(max(size, 1))
    total_weight = float(sum(file_weights) or len(required_files) or 1)

    done_weight = 0.0
    for idx, filename in enumerate(required_files):
        meta = remote.get(filename) or {}
        url = str(meta.get("url") or "")
        if not url:
            raise RuntimeError(f"远程文件缺失: {filename}")

        weight = float(file_weights[idx])
        db_transcription.update_model_download_job(
            job_id,
            status="RUNNING",
            progress=min(98.0, done_weight / total_weight * 100.0),
            message=f"下载文件: {filename}",
        )

        def on_progress(percent: float, _line: str, done=done_weight, w=weight):
            overall = ((done + w * max(0.0, min(100.0, percent)) / 100.0) / total_weight) * 100.0
            db_transcription.update_model_download_job(
                job_id,
                status="RUNNING",
                progress=min(98.0, overall),
                message=f"下载文件: {filename} ({percent:.0f}%)",
            )

        _run_aria2(
            job_id=job_id,
            url=url,
            output_path=local_dir / filename,
            aria2_config=aria2_config,
            progress_callback=on_progress,
        )
        done_weight += weight


def _is_cancel_requested(job_id: str) -> bool:
    with _lock:
        return str(job_id or "") in _cancel_requested


def _request_cancel(job_id: str):
    safe_job_id = str(job_id or "")
    with _lock:
        _cancel_requested.add(safe_job_id)
        process = _active_processes.get(safe_job_id)
    if process and process.poll() is None:
        try:
            process.terminate()
        except Exception:
            pass


def _build_hash_failure_message(hash_result: Dict) -> str:
    checks = hash_result.get("checks") or []
    failed = next((item for item in checks if str(item.get("status") or "").lower() == "failed"), None)
    if not failed:
        return "HASH 校验失败"

    file_name = str(failed.get("file") or "").strip()
    msg = str(failed.get("message") or "HASH 校验失败").strip()
    expected = str(failed.get("expected") or "").strip()
    actual = str(failed.get("actual") or "").strip()
    parts = [msg]
    if file_name:
        parts.append(f"文件: {file_name}")
    if expected:
        parts.append(f"期望: {expected}")
    if actual:
        parts.append(f"实际: {actual}")
    return " | ".join(parts)


def _run_download_job(job_id: str, model_entry: Dict):
    backend = str(model_entry.get("backend") or "").strip().lower()
    model_id = str(model_entry.get("model_id") or "").strip()
    partial_result: Dict = {}

    try:
        config = get_transcription_config()
        aria2_cfg = ((config.get("download") or {}).get("aria2") or {})

        db_transcription.update_model_download_job(
            job_id,
            status="RUNNING",
            progress=0.1,
            message=f"准备下载模型 {backend}/{model_id}",
        )

        if _is_cancel_requested(job_id):
            raise RuntimeError("任务已取消")

        if backend == "whisper":
            _run_openai_download(job_id, model_entry, aria2_cfg)
        elif backend == "faster_whisper":
            _run_faster_download(job_id, model_entry, aria2_cfg)
        else:
            raise RuntimeError(f"不支持的后端: {backend}")

        if _is_cancel_requested(job_id):
            raise RuntimeError("任务已取消")

        db_transcription.update_model_download_job(
            job_id,
            status="RUNNING",
            progress=98.5,
            message="下载完成，开始 HASH 校验",
        )

        hash_result = verify_model_hashes(model_entry)
        partial_result["hash"] = hash_result
        if not hash_result.get("ok"):
            raise RuntimeError(_build_hash_failure_message(hash_result))

        db_transcription.update_model_download_job(
            job_id,
            status="RUNNING",
            progress=99.0,
            message="HASH 校验通过，开始热身",
        )

        if _is_cancel_requested(job_id):
            raise RuntimeError("任务已取消")

        warmup_result = warmup_transcription_model(model_entry)
        partial_result["warmup"] = warmup_result
        if not warmup_result.get("ok"):
            raise RuntimeError(f"模型热身失败: {warmup_result.get('message')}")

        db_transcription.update_model_download_job(
            job_id,
            status="COMPLETED",
            progress=100.0,
            message="下载、校验、热身全部完成",
            result={"hash": hash_result, "warmup": warmup_result, "model": model_entry},
            error="",
        )
    except Exception as exc:
        logger.error("Model download job failed (%s): %s", job_id, exc)
        failure_result = {"model": model_entry}
        if partial_result:
            failure_result.update(partial_result)
        db_transcription.update_model_download_job(
            job_id,
            status="FAILED",
            message=f"任务失败: {exc}",
            result=failure_result,
            error=str(exc),
        )
    finally:
        with _lock:
            _active_threads.pop(job_id, None)
            _active_processes.pop(job_id, None)
            _cancel_requested.discard(job_id)


def start_model_download(model_id: str, backend: str, request_payload: Optional[Dict] = None) -> Dict:
    backend = str(backend or "").strip().lower()
    model_id = str(model_id or "").strip().lower()
    model_entry = get_model_entry(backend, model_id)
    if not model_entry:
        raise ValueError(f"未找到模型: {backend}/{model_id}")

    job_id = db_transcription.create_model_download_job(
        model_id=model_id,
        backend=backend,
        request_payload=request_payload or {},
    )

    thread = threading.Thread(target=_run_download_job, args=(job_id, model_entry), daemon=True)
    with _lock:
        _active_threads[job_id] = thread
    thread.start()

    payload = db_transcription.get_model_download_job(job_id) or {}
    payload["model"] = model_entry
    return payload


def cancel_download_job(job_id: str) -> Dict:
    payload = db_transcription.get_model_download_job(job_id)
    if not payload:
        raise ValueError("job not found")

    status = str(payload.get("status") or "").strip().upper()
    if status in {"FAILED", "COMPLETED"}:
        return payload

    _request_cancel(job_id)
    db_transcription.update_model_download_job(
        job_id,
        status="FAILED",
        message="任务已取消",
        error="cancelled_by_admin",
    )
    return db_transcription.get_model_download_job(job_id) or payload


def delete_download_job(job_id: str) -> bool:
    payload = db_transcription.get_model_download_job(job_id)
    if not payload:
        raise ValueError("job not found")

    status = str(payload.get("status") or "").strip().upper()
    if status == "RUNNING":
        raise ValueError("RUNNING 状态任务请先取消")

    return db_transcription.delete_model_download_job(job_id)


def get_download_job(job_id: str) -> Optional[Dict]:
    return db_transcription.get_model_download_job(job_id)


def list_download_jobs(limit: int = 50):
    return db_transcription.list_model_download_jobs(limit=limit)
