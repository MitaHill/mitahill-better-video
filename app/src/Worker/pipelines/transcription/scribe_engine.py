import logging
import mimetypes
from pathlib import Path

import requests


SCRIBE_URL = "https://api.elevenlabs.io/v1/speech-to-text"
USER_URL = "https://api.elevenlabs.io/v1/user"
MAX_FILE_BYTES = 3 * 1024 * 1024 * 1024

logger = logging.getLogger("SCRIBE_ENGINE")


def _load_multipart_classes():
    from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor

    return MultipartEncoder, MultipartEncoderMonitor


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_segments(payload, max_line_chars=42, max_duration=5.0):
    words = payload.get("words") if isinstance(payload, dict) else None
    if not isinstance(words, list):
        return []

    segments = []
    parts = []
    start = None
    end = None

    def flush():
        nonlocal parts, start, end
        text = "".join(parts).strip()
        if text and start is not None and end is not None and end >= start:
            segments.append({"start": start, "end": end, "text": text})
        parts = []
        start = None
        end = None

    # 只使用服务端给出的单词时间戳，避免自己估算字幕时间
    for item in words:
        if not isinstance(item, dict) or str(item.get("type") or "").lower() == "audio_event":
            continue
        text = str(item.get("text") or "")
        if not text:
            continue

        word_start = _number(item.get("start"))
        word_end = _number(item.get("end"))
        if word_start is not None and word_end is not None:
            if start is None:
                start = word_start
            end = word_end
        elif start is None:
            continue

        parts.append(text)
        current = "".join(parts).strip()
        sentence_end = current.endswith((".", "?", "!", "。", "？", "！"))
        too_long = bool(max_line_chars and len(current) >= int(max_line_chars))
        too_slow = bool(end is not None and start is not None and end - start >= float(max_duration))
        if sentence_end or too_long or too_slow:
            flush()

    flush()
    return segments


def _raise_api_error(response):
    status = int(getattr(response, "status_code", 0) or 0)
    if status == 401:
        raise RuntimeError("ElevenLabs API Key 无效")
    if status == 403:
        raise RuntimeError("ElevenLabs 拒绝访问，请检查 API Key 权限和 IP 白名单")
    if status == 413:
        raise RuntimeError("ElevenLabs 拒绝文件：文件体积超过服务限制")
    if status == 429:
        raise RuntimeError("ElevenLabs 额度不足或并发已达上限")
    if status >= 500:
        raise RuntimeError("ElevenLabs 服务暂时不可用")
    raise RuntimeError(f"ElevenLabs 转录请求失败（HTTP {status or '未知'}）")


def test_connection(api_key):
    safe_key = str(api_key or "").strip()
    if not safe_key:
        raise RuntimeError("ElevenLabs API Key 尚未配置")
    try:
        response = requests.get(
            USER_URL,
            headers={"xi-api-key": safe_key},
            timeout=(10, 30),
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"无法连接 ElevenLabs：{exc}") from exc
    if not response.ok:
        _raise_api_error(response)
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("ElevenLabs 返回了无效响应") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("ElevenLabs 返回了无效响应")
    subscription = payload.get("subscription") or {}
    return {
        "ok": True,
        "tier": str(subscription.get("tier") or "unknown"),
        "status": str(subscription.get("status") or "unknown"),
        "message": "ElevenLabs 连接正常",
    }


class ScribeEngine:
    def transcribe(self, media_path, *, api_key, language="auto", max_line_chars=42, progress_callback=None):
        path = Path(media_path)
        if not path.is_file():
            raise RuntimeError(f"待转录音频不存在: {path.name}")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise RuntimeError("ElevenLabs 单个转录文件不能超过 3GB")

        safe_key = str(api_key or "").strip()
        if not safe_key:
            raise RuntimeError("ElevenLabs API Key 尚未配置")

        MultipartEncoder, MultipartEncoderMonitor = _load_multipart_classes()
        fields = {
            "model_id": "scribe_v2",
            "tag_audio_events": "false",
            "diarize": "false",
            "timestamps_granularity": "word",
        }
        language_code = str(language or "auto").strip().lower()
        if language_code != "auto":
            fields["language_code"] = language_code

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as source:
            fields["file"] = (path.name, source, content_type)
            encoder = MultipartEncoder(fields=fields)

            def on_upload(monitor):
                if not progress_callback or monitor.len <= 0:
                    return
                uploaded = min(monitor.bytes_read, monitor.len)
                # 上传只占转录阶段前 10%，云端计算期间不伪造进度
                if uploaded >= monitor.len:
                    progress_callback(
                        {
                            "ratio": 0.1,
                            "stage": "transcribe_cloud",
                            "message": "ElevenLabs 云端转录中",
                        }
                    )
                    return
                progress_callback(
                    {
                        "ratio": uploaded / monitor.len * 0.1,
                        "stage": "transcribe_upload",
                        "message": f"上传到 ElevenLabs {uploaded}/{monitor.len} 字节",
                        "unit_done": uploaded,
                        "unit_total": monitor.len,
                        "unit_label": "字节",
                    }
                )

            monitor = MultipartEncoderMonitor(encoder, on_upload)
            logger.info("Sending %s to ElevenLabs Scribe v2", path.name)
            try:
                response = requests.post(
                    SCRIBE_URL,
                    headers={
                        "xi-api-key": safe_key,
                        "Content-Type": monitor.content_type,
                    },
                    data=monitor,
                    timeout=(30, None),
                    allow_redirects=False,
                )
            except requests.RequestException as exc:
                raise RuntimeError(f"ElevenLabs 转录连接失败：{exc}") from exc

        if not response.ok:
            _raise_api_error(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("ElevenLabs 返回了无效响应") from exc

        segments = build_segments(payload, max_line_chars=max_line_chars)
        if not segments:
            raise RuntimeError("ElevenLabs 没有返回有效的单词时间戳")
        if progress_callback:
            progress_callback({"ratio": 1.0, "stage": "transcribe", "message": "ElevenLabs 转录完成"})
        return {"segments": segments}

    def finalize_task(self):
        return None
