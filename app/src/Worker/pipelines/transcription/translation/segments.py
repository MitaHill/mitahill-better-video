import logging
from typing import Callable, Dict, List, Optional

import requests

from ..progress import TaskCancelledError

logger = logging.getLogger("TRANSCRIBE_TRANSLATION")


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").split())


def translate_segments(
    segments,
    translator,
    target_language,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cached_text_map: Optional[Dict[int, str]] = None,
    checkpoint_callback: Optional[Callable[[int, str, str, str, str], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
    raw_stream_callback: Optional[Callable[[int, str], None]] = None,
):
    payload = segments or []
    if not translator:
        return list(payload)

    cache = cached_text_map or {}
    total = len(payload)
    translated: List[Optional[dict]] = [None] * total
    done_count = 0
    timeout_circuit_open = False

    def _tick_progress():
        if progress_callback:
            progress_callback(done_count, total)

    def _commit(
        idx: int,
        current: dict,
        source_text: str,
        translated_text: str,
        *,
        status: Optional[str] = None,
        message: str = "",
        save_checkpoint: bool = True,
    ):
        nonlocal done_count
        safe_translated = _normalize_text(translated_text)
        current["text"] = safe_translated
        translated[idx - 1] = current
        if save_checkpoint and checkpoint_callback and status:
            checkpoint_callback(idx, source_text, safe_translated, status, message)
        done_count += 1
        _tick_progress()

    i = 1
    while i <= total:
        if should_cancel and should_cancel():
            raise TaskCancelledError("任务已取消")

        current = dict(payload[i - 1] or {})
        source_text = _normalize_text(current.get("text", ""))

        if i in cache:
            _commit(
                i,
                current,
                source_text,
                _normalize_text(cache.get(i) or ""),
                save_checkpoint=False,
            )
            i += 1
            continue

        if not source_text:
            _commit(i, current, source_text, source_text, status="skipped", message="empty segment")
            i += 1
            continue

        if timeout_circuit_open:
            fallback = translator.fallback_text(source_text)
            _commit(i, current, source_text, fallback, status="fallback", message="timeout circuit open")
            i += 1
            continue

        max_batch = max(1, int(getattr(translator, "batch_window_size", 10) or 10))
        max_chars = max(500, int(getattr(translator, "batch_max_chars", 2500) or 2500))

        batch_items = []
        char_count = 0
        j = i
        while j <= total and len(batch_items) < max_batch:
            item_idx = j
            if item_idx in cache:
                break
            item_current = dict(payload[item_idx - 1] or {})
            item_text = _normalize_text(item_current.get("text", ""))
            if not item_text:
                break
            next_count = char_count + len(item_text)
            if batch_items and next_count > max_chars:
                break
            batch_items.append({"segment_index": item_idx, "text": item_text})
            char_count = next_count
            j += 1

        if not batch_items:
            fallback = translator.fallback_text(source_text)
            _commit(i, current, source_text, fallback, status="fallback", message="empty batch after split")
            i += 1
            continue

        current_size = len(batch_items)
        translated_batch = None
        last_error = None

        while current_size >= 1:
            candidate_items = batch_items[:current_size]
            anchor_idx = int(candidate_items[0].get("segment_index") or i)

            def _on_raw_delta(delta_text: str):
                if raw_stream_callback:
                    raw_stream_callback(anchor_idx, str(delta_text or ""))

            try:
                if should_cancel and should_cancel():
                    raise TaskCancelledError("任务已取消")
                if current_size == 1:
                    only = candidate_items[0]
                    one_text = translator.translate_text(
                        str(only.get("text") or ""),
                        target_language,
                        stream_callback=_on_raw_delta,
                    )
                    translated_batch = [_normalize_text(one_text)]
                else:
                    translated_batch = translator.translate_batch(
                        candidate_items,
                        target_language,
                        stream_callback=_on_raw_delta,
                    )
                    if len(translated_batch or []) != len(candidate_items):
                        raise ValueError("batch translation size mismatch")
                    translated_batch = [_normalize_text(item) for item in (translated_batch or [])]
                break
            except TaskCancelledError:
                raise
            except requests.exceptions.ReadTimeout as exc:
                timeout_circuit_open = True
                last_error = exc
                logger.warning(
                    "Translation timeout at segment %s/%s, switch to fallback for remaining segments: %s",
                    i,
                    total,
                    exc,
                )
                break
            except Exception as exc:
                last_error = exc
                if current_size > 1:
                    reduced_size = max(1, current_size // 2)
                    logger.warning(
                        "Batch translation parse/exec failed for segments %s-%s, shrink window %s -> %s: %s",
                        i,
                        i + current_size - 1,
                        current_size,
                        reduced_size,
                        exc,
                    )
                    current_size = reduced_size
                    continue
                logger.warning(
                    "Translation failed at segment %s/%s, use fallback text: %s",
                    i,
                    total,
                    exc,
                )
                break

        effective_items = batch_items[:current_size]
        if translated_batch is not None:
            for k, item in enumerate(effective_items):
                idx = int(item.get("segment_index") or 0)
                if idx <= 0:
                    continue
                current_item = dict(payload[idx - 1] or {})
                src = _normalize_text(item.get("text") or "")
                out = _normalize_text((translated_batch[k] if k < len(translated_batch) else "") or "")
                _commit(idx, current_item, src, out, status="translated", message="")
            i = int(effective_items[-1].get("segment_index") or i) + 1
            continue

        error_text = str(last_error or "translation failed")
        for item in effective_items:
            idx = int(item.get("segment_index") or 0)
            if idx <= 0:
                continue
            current_item = dict(payload[idx - 1] or {})
            src = _normalize_text(item.get("text") or "")
            fallback = translator.fallback_text(src)
            status = "fallback"
            _commit(idx, current_item, src, fallback, status=status, message=error_text)
        i = int(effective_items[-1].get("segment_index") or i) + 1

    return [dict(item or {}) for item in translated]


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
