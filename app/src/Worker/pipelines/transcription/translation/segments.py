import logging
from typing import Callable, List, Optional

import requests

from .providers import CONTEXT_WINDOW_SIZE


logger = logging.getLogger("TRANSCRIBE_TRANSLATION")


def _normalize_segment_text(text: str) -> str:
    return " ".join(str(text or "").split())


def _append_context(context_pairs, source_text, translated_text):
    source = str(source_text or "").strip()
    translated = str(translated_text or "").strip()
    if not source or not translated:
        return
    context_pairs.append({"source_text": source, "translated_text": translated})
    if len(context_pairs) > CONTEXT_WINDOW_SIZE:
        del context_pairs[1:-(CONTEXT_WINDOW_SIZE - 1)]


def translate_segments(
    segments,
    translator,
    target_language,
    progress_callback: Optional[Callable[[int, int], None]] = None,
):
    payload = segments or []
    if not translator:
        return list(payload)

    translated: List[dict] = []
    context_pairs = []
    total = len(payload)
    timeout_circuit_open = False
    for idx, segment in enumerate(payload, start=1):
        current = dict(segment or {})
        text = _normalize_segment_text(current.get("text", ""))

        if not text:
            current["text"] = text
            translated.append(current)
            if progress_callback:
                progress_callback(idx, total)
            continue

        if timeout_circuit_open:
            current["text"] = translator.fallback_text(text)
            translated.append(current)
            _append_context(context_pairs, text, current["text"])
            if progress_callback:
                progress_callback(idx, total)
            continue

        try:
            current["text"] = translator.translate_text(text, target_language, context_pairs=context_pairs)
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
        _append_context(context_pairs, text, current["text"])
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
