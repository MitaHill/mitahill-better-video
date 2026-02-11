import hashlib
import logging
import os
import re
import socket
import tempfile
import time
import wave
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse

import requests

from .transcription_catalog import fetch_hf_model_files, get_model_entry, get_storage_roots

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


def _git_blob_sha1_of_file(path: Path) -> str:
    size = path.stat().st_size
    digest = hashlib.sha1()
    digest.update(f"blob {size}\0".encode("utf-8"))
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clean_etag_digest(etag_value: str) -> str:
    raw = str(etag_value or "").strip()
    if not raw:
        return ""
    cleaned = raw.replace("W/", "").strip().strip("\"")
    if "-" in cleaned:
        # multipart etag is not a stable file digest, skip it
        return ""
    return cleaned if re.fullmatch(r"[a-fA-F0-9]{40}|[a-fA-F0-9]{64}", cleaned) else ""


def _infer_hash_algo(digest: str) -> str:
    token = str(digest or "").strip().lower()
    if len(token) == 64 and re.fullmatch(r"[a-f0-9]{64}", token):
        return "sha256"
    if len(token) == 40 and re.fullmatch(r"[a-f0-9]{40}", token):
        return "sha1"
    return ""


def _fetch_hf_hash_via_head(repo_id: str, filename: str) -> Dict:
    resolve_url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}?download=true"
    response = requests.head(resolve_url, allow_redirects=True, timeout=30)
    response.raise_for_status()
    digest = _clean_etag_digest(response.headers.get("etag", ""))
    algo = _infer_hash_algo(digest)
    return {
        "url": resolve_url,
        "digest": digest.lower() if digest else "",
        "algo": algo,
    }


def _speed_grade(latency_sec: float) -> str:
    if latency_sec <= 3.0:
        return "很快"
    if latency_sec <= 10.0:
        return "正常"
    if latency_sec <= 30.0:
        return "较慢"
    return "很慢"


def verify_model_hashes(model_entry: Dict) -> Dict:
    backend = str(model_entry.get("backend") or "").strip().lower()
    out = {"ok": True, "checks": []}

    if backend == "whisper":
        local_path = Path(model_entry.get("local_path") or "")
        candidate_items = model_entry.get("local_candidates") or []
        candidate_paths: List[Path] = []
        for item in candidate_items:
            safe = str(item or "").strip()
            if safe:
                candidate_paths.append(Path(safe))
        if local_path and str(local_path):
            if str(local_path) not in {str(path) for path in candidate_paths}:
                candidate_paths.insert(0, local_path)
        if not candidate_paths:
            candidate_paths = [local_path]

        matched_path = next((path for path in candidate_paths if path.exists()), None)
        if not matched_path:
            looked_up = ", ".join(str(path) for path in candidate_paths if str(path)) or str(local_path)
            return {
                "ok": False,
                "checks": [
                    {
                        "name": "hash",
                        "status": "failed",
                        "message": f"模型文件不存在，请先下载模型。已检查路径: {looked_up}",
                    }
                ],
            }
        expected = str(model_entry.get("expected_sha256") or "").strip().lower()
        if not expected:
            return {
                "ok": False,
                "checks": [
                    {
                        "name": "hash",
                        "status": "failed",
                        "file": str(matched_path),
                        "message": "远程未提供可用 HASH",
                    }
                ],
            }
        actual = _digest_of_file(matched_path, "sha256")
        status = actual == expected
        out["checks"].append(
            {
                "name": "hash",
                "status": "passed" if status else "failed",
                "file": str(matched_path),
                "expected": expected,
                "actual": actual,
                "message": "SHA256 校验通过" if status else "SHA256 校验失败",
            }
        )
        out["ok"] = bool(status)
        return out

    if backend == "faster_whisper":
        repo_id = str(model_entry.get("repo_id") or "").strip()
        model_id = str(model_entry.get("model_id") or "").strip()
        local_dir = Path(model_entry.get("local_path") or "")
        if not local_dir.exists():
            return {
                "ok": False,
                "checks": [
                    {
                        "name": "hash",
                        "status": "failed",
                        "message": f"模型目录不存在: {local_dir}",
                    }
                ],
            }

        try:
            remote_meta = fetch_hf_model_files(repo_id)
        except Exception as exc:
            logger.error("Failed to fetch HF hash metadata for %s: %s", repo_id, exc)
            return {
                "ok": False,
                "checks": [
                    {
                        "name": "hash",
                        "status": "failed",
                        "message": f"无法拉取远程 HASH 数据: {exc}",
                    }
                ],
            }

        required_files: List[str] = model_entry.get("required_files") or []
        all_ok = True
        checks = []
        for filename in required_files:
            local_file = local_dir / filename
            if not local_file.exists():
                checks.append(
                    {
                        "name": "hash",
                        "status": "failed",
                        "file": str(local_file),
                        "message": "文件缺失",
                    }
                )
                all_ok = False
                continue

            remote_entry = remote_meta.get(filename) or {}
            expected = str(remote_entry.get("sha256") or "").strip().lower()
            algo = "sha256" if expected and _infer_hash_algo(expected) == "sha256" else ""

            if not expected or not algo:
                blob_id = str(remote_entry.get("blob_id") or "").strip().lower()
                if blob_id and _infer_hash_algo(blob_id) == "sha1":
                    expected = blob_id
                    algo = "git_blob_sha1"

            if not expected or not algo:
                try:
                    head_meta = _fetch_hf_hash_via_head(repo_id, filename)
                    expected = str(head_meta.get("digest") or "").strip().lower()
                    algo = str(head_meta.get("algo") or "").strip().lower()
                except Exception as exc:
                    logger.warning("Failed to fetch HEAD hash for %s/%s: %s", repo_id, filename, exc)
                    expected = ""
                    algo = ""

            if not expected or not algo:
                checks.append(
                    {
                        "name": "hash",
                        "status": "failed",
                        "file": str(local_file),
                        "message": "远程未提供可用 HASH",
                    }
                )
                all_ok = False
                continue

            if algo == "git_blob_sha1":
                actual = _git_blob_sha1_of_file(local_file)
            else:
                actual = _digest_of_file(local_file, algo)
            passed = actual == expected
            all_ok = all_ok and passed
            checks.append(
                {
                    "name": "hash",
                    "status": "passed" if passed else "failed",
                    "algorithm": algo,
                    "file": str(local_file),
                    "expected": expected,
                    "actual": actual,
                    "message": f"{algo.upper()} 校验通过" if passed else f"{algo.upper()} 校验失败",
                }
            )

        return {"ok": all_ok, "checks": checks, "model_id": model_id}

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

    try:
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        device = "cpu"

    wav_path = _build_silent_wav()
    try:
        if backend == "whisper":
            import whisper

            storage = get_storage_roots().get("openai")
            storage.mkdir(parents=True, exist_ok=True)
            model_ref = model_id
            if local_path.exists():
                model_ref = str(local_path)
            model = whisper.load_model(model_ref, download_root=str(storage), device=device)
            _ = model.transcribe(str(wav_path), language="en", temperature=0.0, fp16=(device == "cuda"))

        elif backend == "faster_whisper":
            from faster_whisper import WhisperModel

            model_ref = str(local_path) if local_path.exists() else model_id
            compute_type = "float16" if device == "cuda" else "int8"
            model = WhisperModel(model_ref, device=device, compute_type=compute_type)
            segments, _info = model.transcribe(str(wav_path), beam_size=1, language="en")
            list(segments)
        else:
            raise RuntimeError(f"Unsupported backend: {backend}")

        elapsed = time.time() - started
        return {
            "ok": True,
            "backend": backend,
            "model_id": model_id,
            "device": device,
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
            "elapsed_sec": round(elapsed, 3),
            "message": str(exc),
        }
    finally:
        try:
            wav_path.unlink(missing_ok=True)
        except Exception:
            pass


def test_translation_provider(translation_config: Dict) -> Dict:
    provider = str(translation_config.get("provider") or "none").strip().lower()
    base_url = str(translation_config.get("base_url") or "").strip().rstrip("/")
    model = str(translation_config.get("model") or "").strip()
    api_key = str(translation_config.get("api_key") or "").strip()
    enable_thinking = bool(translation_config.get("enable_thinking"))
    timeout_sec = float(translation_config.get("timeout_sec") or 60.0)

    if provider == "none":
        return {"ok": False, "provider": provider, "error": "翻译提供器未启用"}
    if not base_url:
        return {"ok": False, "provider": provider, "error": "未配置翻译服务地址"}

    if provider == "ollama":
        return _test_ollama(base_url=base_url, model=model, enable_thinking=enable_thinking)
    if provider == "openai_compatible":
        return _test_openai_compatible(
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout_sec=max(1.0, min(timeout_sec, 60.0)),
        )

    return {"ok": False, "provider": provider, "error": f"不支持的翻译提供器: {provider}"}


def _test_ollama(base_url: str, model: str, enable_thinking: bool = False) -> Dict:
    parsed = urlparse(base_url)
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not host:
        return {"ok": False, "provider": "ollama", "error": "无效的 Ollama 地址"}

    steps = []

    try:
        begin = time.time()
        with socket.create_connection((host, port), timeout=3):
            pass
        tcp_elapsed = time.time() - begin
        steps.append({"step": "tcp_ping", "status": "passed", "elapsed_sec": round(tcp_elapsed, 3)})
    except Exception as exc:
        return {
            "ok": False,
            "provider": "ollama",
            "steps": [{"step": "tcp_ping", "status": "failed", "message": str(exc)}],
            "error": f"TCP-PING 失败: {exc}",
        }

    try:
        tags_resp = requests.get(f"{base_url}/api/tags", timeout=10)
        tags_resp.raise_for_status()
        payload = tags_resp.json() or {}
        names = [str((item or {}).get("name") or "") for item in (payload.get("models") or [])]
        if model and not any(name == model or name.startswith(f"{model}:") for name in names):
            return {
                "ok": False,
                "provider": "ollama",
                "steps": steps + [{"step": "list_models", "status": "failed", "message": "未找到目标模型"}],
                "error": f"目标模型不存在: {model}",
                "available_models": names,
            }
        steps.append({"step": "list_models", "status": "passed", "count": len(names)})
    except Exception as exc:
        return {
            "ok": False,
            "provider": "ollama",
            "steps": steps + [{"step": "list_models", "status": "failed", "message": str(exc)}],
            "error": f"读取模型列表失败: {exc}",
        }

    try:
        started = time.time()
        steps.append(
            {
                "step": "thinking",
                "status": "passed",
                "enabled": bool(enable_thinking),
            }
        )
        resp = requests.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "stream": False,
                "think": bool(enable_thinking),
                "messages": [{"role": "user", "content": "Hello.What's Your Name"}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        payload = resp.json() or {}
        content = ((payload.get("message") or {}).get("content") or "").strip()
        latency = time.time() - started
        steps.append(
            {
                "step": "chat",
                "status": "passed",
                "elapsed_sec": round(latency, 3),
                "speed_grade": _speed_grade(latency),
                "reply_preview": content[:120],
            }
        )
        return {"ok": True, "provider": "ollama", "steps": steps}
    except requests.Timeout:
        return {
            "ok": False,
            "provider": "ollama",
            "steps": steps + [{"step": "chat", "status": "failed", "message": "超过 60 秒超时"}],
            "error": "对话超时（60秒）",
        }
    except Exception as exc:
        return {
            "ok": False,
            "provider": "ollama",
            "steps": steps + [{"step": "chat", "status": "failed", "message": str(exc)}],
            "error": f"对话测试失败: {exc}",
        }


def _test_openai_compatible(base_url: str, model: str, api_key: str, timeout_sec: float) -> Dict:
    endpoint = base_url
    if not endpoint.endswith("/chat/completions"):
        endpoint = f"{base_url}/chat/completions"

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
            detail = ""
            try:
                detail = str((resp.json() or {}).get("error") or "")
            except Exception:
                detail = (resp.text or "").strip()[:180]
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
