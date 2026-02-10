from typing import Callable, List, Optional


def translate_segments(segments, translator, target_language, progress_callback: Optional[Callable[[int, int], None]] = None):
    payload = segments or []
    if not translator:
        return list(payload)

    translated: List[dict] = []
    total = len(payload)
    for idx, segment in enumerate(payload, start=1):
        current = dict(segment or {})
        text = " ".join(str(current.get("text", "")).split())
        if text:
            current["text"] = translator.translate_text(text, target_language)
        else:
            current["text"] = text
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
