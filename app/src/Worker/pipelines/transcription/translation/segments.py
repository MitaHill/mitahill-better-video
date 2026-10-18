import logging
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Callable, List, Optional

from .providers import TranslationFormatError, TranslationRequestError, TranslationServiceError


logger = logging.getLogger("TRANSCRIBE_TRANSLATION")


def _normalize_segment_text(text: str) -> str:
    return " ".join(str(text or "").split())


def _batches(items, size):
    batch, byte_count = [], 0
    for item in items:
        length = len(item["text"].encode("utf-8"))
        if batch and (len(batch) >= size or byte_count + length > 6000):
            yield batch
            batch, byte_count = [], 0
        batch.append(item)
        byte_count += length
    if batch:
        yield batch


def _translate_batch(translator, batch, target_language, items, offset):
    # 上下文只读且有界，不依赖其他线程尚未完成的译文。
    def context(rows):
        return [row["text"].encode("utf-8")[:1000].decode("utf-8", errors="ignore") for row in rows]

    try:
        return translator.translate_batch(
            batch, target_language,
            context_before=context(items[max(0, offset - 3):offset]),
            context_after=context(items[offset + len(batch):offset + len(batch) + 3]),
        )
    except TranslationFormatError:
        logger.warning("Invalid batch translation at ID %s; retry individual segments", batch[0]["id"])
    except TranslationRequestError:
        logger.warning("Batch request exhausted retries at ID %s; use fallback", batch[0]["id"])
        translator._record(fallbacks=len(batch))
        return {item["id"]: translator.fallback_text(item["text"]) for item in batch}

    result = {}
    for item in batch:
        try:
            result[item["id"]] = translator.translate_text(item["text"], target_language)
        except TranslationServiceError:
            raise
        except (TranslationRequestError, TranslationFormatError):
            logger.warning("Translation failed at ID %s; use fallback", item["id"])
            translator._record(fallbacks=1)
            result[item["id"]] = translator.fallback_text(item["text"])
    return result


def translate_segments(
    segments,
    translator,
    target_language,
    progress_callback: Optional[Callable[[int, int], None]] = None,
):
    payload = segments or []
    if not translator:
        return list(payload)

    translated: List[dict] = [dict(segment or {}) for segment in payload]
    items = []
    for idx, segment in enumerate(translated):
        segment["text"] = _normalize_segment_text(segment.get("text", ""))
        if segment["text"]:
            items.append({"id": idx, "text": segment["text"]})
    total = len(translated)
    done = total - len(items)
    batches = iter(_batches(items, translator.batch_size))
    offset, batch_count = 0, 0
    started = last_emit = time.monotonic()
    with ThreadPoolExecutor(max_workers=translator.concurrency, thread_name_prefix="translate") as pool:
        pending = {}

        def submit_next():
            nonlocal offset, batch_count
            batch = next(batches, None)
            if batch is None:
                return
            future = pool.submit(_translate_batch, translator, batch, target_language, items, offset)
            pending[future] = len(batch)
            offset += len(batch)
            batch_count += 1

        for _ in range(translator.concurrency):
            submit_next()
        try:
            while pending:
                completed, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in completed:
                    result = future.result()
                    for item_id, text in result.items():
                        translated[item_id]["text"] = _normalize_segment_text(text)
                    done += pending.pop(future)
                    now = time.monotonic()
                    if progress_callback and done < total and now - last_emit >= 1:
                        progress_callback(done, total)
                        last_emit = now
                for _ in completed:
                    submit_next()
        except BaseException:
            for future in pending:
                future.cancel()
            raise
    if progress_callback:
        progress_callback(total, total)
    logger.info(
        "Translation completed: segments=%s batches=%s concurrency=%s elapsed=%.3fs",
        len(items), batch_count, translator.concurrency, time.monotonic() - started,
    )
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
            merged_item["text"] = f"{translated_text}\n{original_text}"
        else:
            merged_item["text"] = translated_text or original_text
        merged.append(merged_item)
    return merged
