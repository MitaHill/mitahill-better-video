import hashlib
import gc
import logging
import os
import tempfile
import time
import wave
from pathlib import Path
from typing import Dict

import requests

from app.src.Worker.gpu_model_coordinator import release_all_models

from .transcription_catalog import get_model_entry, get_storage_roots

logger = logging.getLogger("ADMIN_MODEL_CHECKS")


def _digest_of_file(path: Path, algo: str) -> str:
    safe_algo = str(algo or "").strip().lower()
    if safe_algo == "sha1":
        digest = hashlib.sha1()
    else:
        digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _speed_grade(latency_sec: float) -> str:
    if latency_sec <= 3.0:
        return "很快"
    if latency_sec <= 10.0:
        return "正常"
    if latency_sec <= 30.0:
        return "较慢"
    return "很慢"


def _extract_error_detail(resp) -> str:
    try:
        payload = resp.json() or {}
    except Exception:
        return (resp.text or "").strip()[:180]
    error = payload.get("error")
    if isinstance(error, dict):
        message = str(error.get("message") or "").strip()
        if message:
            return message
    return str(error or "").strip() or (resp.text or "").strip()[:180]


def verify_model_hashes(model_entry: Dict) -> Dict:
    backend = str(model_entry.get("backend") or "").strip().lower()

    if backend == "whisper":
        model_id = str(model_entry.get("model_id") or "").strip()
        local_path = Path(model_entry.get("local_path") or "")
        expected = str(model_entry.get("expected_sha256") or "").strip().lower()
        if not local_path.exists():
            return {
                "ok": False,
                "checks": [
                    {
                        "name": "hash",
                        "status": "failed",
                        "file": str(local_path),
                        "message": f"模型文件不存在: {local_path}",
                    }
                ],
            }

        if not expected:
            return {
                "ok": False,
                "checks": [
                    {
                        "name": "hash",
                        "status": "failed",
                        "file": str(local_path),
                        "message": "模型 URL 未提供 SHA256",
                    }
                ],
            }

        actual = _digest_of_file(local_path, "sha256")
        passed = actual == expected
        return {
            "ok": passed,
            "checks": [
                {
                    "name": "hash",
                    "status": "passed" if passed else "failed",
                    "algorithm": "sha256",
                    "file": str(local_path),
                    "expected": expected,
                    "actual": actual,
                    "message": "SHA256 校验通过" if passed else "SHA256 校验失败",
                }
            ],
            "model_id": model_id,
        }

    return {
        "ok": False,
        "checks": [
            {
                "name": "hash",
                "status": "failed",
                "message": f"不支持的后端: {backend}",
            }
        ],
    }


def _build_silent_wav() -> Path:
    fd, tmp_name = tempfile.mkstemp(prefix="transcribe_warmup_", suffix=".wav")
    path = Path(tmp_name)
    os.close(fd)
    sample_rate = 16000
    duration_sec = 5
    frame_count = sample_rate * duration_sec
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * frame_count)
    return path


def warmup_transcription_model(model_entry: Dict) -> Dict:
    backend = str(model_entry.get("backend") or "").strip().lower()
    model_id = str(model_entry.get("model_id") or "").strip()
    local_path = Path(model_entry.get("local_path") or "")
    started = time.time()

    import torch

    device = "cuda" if torch.cuda.is_available() else ""

    wav_path = _build_silent_wav()
    model = None
    try:
        if backend != "whisper":
            raise RuntimeError(f"Unsupported backend: {backend}")
        if not device:
            raise RuntimeError("CUDA not available. NVIDIA GPU required for transcription.")

        import whisper

        release_all_models()
        fp16 = True
        model = whisper.load_model(model_id, device=device, download_root=str(local_path.parent))
        model.transcribe(str(wav_path), beam_size=1, language="en", fp16=fp16)

        elapsed = time.time() - started
        return {
            "ok": True,
            "backend": backend,
            "model_id": model_id,
            "device": device,
            "fp16": fp16,
            "elapsed_sec": round(elapsed, 3),
            "message": "热身成功，模型可调用",
        }
    except Exception as exc:
        elapsed = time.time() - started
        logger.error("Warmup failed for %s/%s: %s", backend, model_id, exc)
        return {
            "ok": False,
            "backend": backend,
            "model_id": model_id,
            "device": device,
            "fp16": locals().get("fp16", False),
            "elapsed_sec": round(elapsed, 3),
            "message": str(exc),
        }
    finally:
        try:
            del model
        except Exception:
            pass
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        try:
            wav_path.unlink(missing_ok=True)
        except Exception:
            pass


def test_translation_provider(translation_config: Dict) -> Dict:
    provider = str(translation_config.get("provider") or "none").strip().lower()
    if provider in {"openai", "ollama"}:
        provider = "openai_compatible"
    base_url = str(translation_config.get("base_url") or "").strip().rstrip("/")
    model = str(translation_config.get("model") or "").strip()
    api_key = str(translation_config.get("api_key") or "").strip()
    timeout_sec = float(translation_config.get("timeout_sec") or 60.0)

    if provider == "none":
        return {"ok": False, "provider": provider, "error": "翻译提供器未启用"}
    if provider != "openai_compatible":
        return {"ok": False, "provider": provider, "error": f"不支持的翻译提供器: {provider}"}
    if not base_url:
        return {"ok": False, "provider": provider, "error": "未配置翻译服务地址"}
    if not model:
        return {"ok": False, "provider": provider, "error": "未配置翻译模型名"}

    return _test_openai_compatible(
        base_url=base_url,
        model=model,
        api_key=api_key,
        timeout_sec=max(1.0, min(timeout_sec, 60.0)),
    )


def _normalize_openai_base_url(base_url: str) -> str:
    raw = str(base_url or "").strip().rstrip("/")
    if raw.endswith("/responses"):
        raw = raw[: -len("/responses")]
    if raw.endswith("/chat/completions"):
        raw = raw[: -len("/chat/completions")]
    return raw


def _test_openai_compatible(base_url: str, model: str, api_key: str, timeout_sec: float) -> Dict:
    endpoint = _normalize_openai_base_url(base_url)
    endpoint = endpoint if endpoint.endswith("/chat/completions") else f"{endpoint}/chat/completions"

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    started = time.time()
    try:
        resp = requests.post(
            endpoint,
            headers=headers,
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Hello.What's Your Name"}],
                "temperature": 0.2,
                "stream": False,
            },
            timeout=timeout_sec,
        )
        if resp.status_code >= 400:
            detail = _extract_error_detail(resp)
            mapping = {
                401: "Token 无效或未授权",
                403: "权限不足",
                404: "接口或模型不存在",
                429: "触发限流",
                500: "服务端内部错误",
                502: "上游网关错误",
                503: "服务暂不可用",
                504: "网关超时",
            }
            reason = mapping.get(resp.status_code, f"HTTP {resp.status_code}")
            return {
                "ok": False,
                "provider": "openai_compatible",
                "error": reason,
                "http_status": resp.status_code,
                "detail": detail,
            }

        payload = resp.json() or {}
        choices = payload.get("choices") or []
        content = ""
        if choices:
            content = str(((choices[0] or {}).get("message") or {}).get("content") or "").strip()
        latency = time.time() - started
        return {
            "ok": True,
            "provider": "openai_compatible",
            "elapsed_sec": round(latency, 3),
            "speed_grade": _speed_grade(latency),
            "reply_preview": content[:120],
        }
    except requests.Timeout:
        return {
            "ok": False,
            "provider": "openai_compatible",
            "error": f"请求超时（>{timeout_sec:.0f}s）",
        }
    except requests.ConnectionError as exc:
        return {
            "ok": False,
            "provider": "openai_compatible",
            "error": f"连接已重置或不可达: {exc}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "provider": "openai_compatible",
            "error": f"调用失败: {exc}",
        }


def resolve_model_entry(backend: str, model_id: str) -> Dict:
    entry = get_model_entry(backend, model_id)
    if not entry:
        raise ValueError(f"Unknown model: backend={backend}, model_id={model_id}")
    return entry
