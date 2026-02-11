import logging
from typing import Callable, List, Optional

import requests


logger = logging.getLogger("TRANSCRIBE_TRANSLATION")


def translate_segments(segments, translator, target_language, progress_callback: Optional[Callable[[int, int], None]] = None):
    payload = segments or []
    if not translator:
        return list(payload)

    translated: List[dict] = []
    total = len(payload)
    timeout_circuit_open = False
    for idx, segment in enumerate(payload, start=1):
        current = dict(segment or {})
        text = " ".join(str(current.get("text", "")).split())

        if not text:
            current["text"] = text
            translated.append(current)
            if progress_callback:
                progress_callback(idx, total)
            continue

        if timeout_circuit_open:
            current["text"] = translator.fallback_text(text)
            translated.append(current)
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
            current["text"] = " ".join(str(current.get("text", "")).split())
        translated.append(current)
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
