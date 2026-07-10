import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

import requests


logger = logging.getLogger("TRANSCRIBE_TRANSLATION")


def _normalize_segment_text(text: str) -> str:
    return " ".join(str(text or "").split())


def _load_checkpoint(checkpoint_path):
    if not checkpoint_path:
        return {}
    path = Path(checkpoint_path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Translation checkpoint is not readable, ignore it: %s", path, exc_info=True)
        return {}
    segments = payload.get("segments") if isinstance(payload, dict) else {}
    return segments if isinstance(segments, dict) else {}


def _save_checkpoint(checkpoint_path, checkpoint_segments):
    if not checkpoint_path:
        return
    path = Path(checkpoint_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "segments": checkpoint_segments,
    }
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _read_cached_translation(checkpoint_segments, idx, source_text):
    item = checkpoint_segments.get(str(idx))
    if not isinstance(item, dict):
        return None
    if item.get("source_text") != source_text:
        return None
    if "translated_text" not in item:
        return None
    return str(item.get("translated_text") or "")


def _write_cached_translation(checkpoint_segments, idx, source_text, translated_text):
    checkpoint_segments[str(idx)] = {
        "source_text": source_text,
        "translated_text": str(translated_text or ""),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def translate_segments(
    segments,
    translator,
    target_language,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    checkpoint_path=None,
):
    payload = segments or []
    if not translator:
        return list(payload)

    translated: List[dict] = []
    total = len(payload)
    timeout_circuit_open = False
    checkpoint_segments = _load_checkpoint(checkpoint_path)
    for idx, segment in enumerate(payload, start=1):
        current = dict(segment or {})
        text = _normalize_segment_text(current.get("text", ""))

        cached_text = _read_cached_translation(checkpoint_segments, idx, text)
        if cached_text is not None:
            current["text"] = cached_text
            translated.append(current)
            if progress_callback:
                progress_callback(idx, total)
            continue

        if not text:
            current["text"] = text
            translated.append(current)
            _write_cached_translation(checkpoint_segments, idx, text, current["text"])
            _save_checkpoint(checkpoint_path, checkpoint_segments)
            if progress_callback:
                progress_callback(idx, total)
            continue

        if timeout_circuit_open:
            current["text"] = translator.fallback_text(text)
            translated.append(current)
            _write_cached_translation(checkpoint_segments, idx, text, current["text"])
            _save_checkpoint(checkpoint_path, checkpoint_segments)
            if progress_callback:
                progress_callback(idx, total)
            continue

        try:
            current["text"] = translator.translate_text(text, target_language)
        except requests.exceptions.ReadTimeout as exc:
            timeout_circuit_open = True
            logger.warning(
                "Translation timeout at segment %s/%s, switch to fallback for remaining segments: %s",
                idx,
                total,
                exc,
            )
            current["text"] = translator.fallback_text(text)
        except Exception as exc:
            logger.warning(
                "Translation failed at segment %s/%s, use fallback text: %s",
                idx,
                total,
                exc,
            )
            current["text"] = translator.fallback_text(text)
        else:
            current["text"] = _normalize_segment_text(current.get("text", ""))
        translated.append(current)
        _write_cached_translation(checkpoint_segments, idx, text, current["text"])
        _save_checkpoint(checkpoint_path, checkpoint_segments)
        if progress_callback:
            progress_callback(idx, total)
    return translated


def build_bilingual_segments(source_segments, translated_segments):
    source = source_segments or []
    translated = translated_segments or []
    merged = []
    for idx, source_item in enumerate(source):
        translated_item = translated[idx] if idx < len(translated) else {}
        original_text = " ".join(str((source_item or {}).get("text", "")).split())
        translated_text = " ".join(str((translated_item or {}).get("text", "")).split())
        merged_item = dict(source_item or {})
        if translated_text and original_text:
            merged_item["text"] = f"{translated_text}\\n{original_text}"
        else:
            merged_item["text"] = translated_text or original_text
        merged.append(merged_item)
    return merged
