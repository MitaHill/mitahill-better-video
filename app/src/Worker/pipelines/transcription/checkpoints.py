import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

from app.src.Database import core as db


def _hash_text(text: str) -> str:
    raw = str(text or "").encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def _stable_hash(payload: Dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def normalize_segment_text(text: str) -> str:
    return " ".join(str(text or "").split())


def hash_segment_text(text: str) -> str:
    return _hash_text(normalize_segment_text(text))


def build_media_signature(media_path: Path) -> str:
    stat = media_path.stat()
    return _stable_hash(
        {
            "path": str(media_path),
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
        }
    )


def build_asr_signature(options: Dict) -> str:
    return _stable_hash(
        {
            "backend": str(options.get("transcription_backend") or "whisper").strip().lower(),
            "model": str(options.get("whisper_model") or "medium").strip().lower(),
            "language": str(options.get("language") or "auto").strip().lower(),
            "temperature": float(options.get("temperature") or 0.0),
            "beam_size": int(options.get("beam_size") or 5),
            "best_of": int(options.get("best_of") or 5),
        }
    )


def _translation_signature_payload(options: Dict, *, include_thinking_flag: bool) -> Dict:
    payload = {
        "target": str(options.get("translate_to") or "").strip().lower(),
        "provider": str(options.get("translator_provider") or "none").strip().lower(),
        "base_url": str(options.get("translator_base_url") or "").strip(),
        "model": str(options.get("translator_model") or "").strip(),
        "prompt": str(options.get("translator_prompt") or "").strip(),
        "fallback_mode": str(options.get("translator_fallback_mode") or "model_full_text").strip().lower(),
        "timeout_sec": float(options.get("translator_timeout_sec") or 120.0),
    }
    if include_thinking_flag:
        payload["enable_thinking"] = bool(options.get("translator_enable_thinking"))
    return payload


def build_translation_signature(options: Dict) -> str:
    # Canonical (backward compatible):
    # include `enable_thinking` only when enabled to keep old checkpoints resumable.
    include_thinking = bool(options.get("translator_enable_thinking"))
    return _stable_hash(_translation_signature_payload(options, include_thinking_flag=include_thinking))


def build_translation_signature_legacy(options: Dict) -> str:
    # Legacy signature (before thinking flag was introduced).
    return _stable_hash(_translation_signature_payload(options, include_thinking_flag=False))


def build_translation_signature_with_explicit_thinking(options: Dict) -> str:
    # Transitional signature used by previous implementation that always included thinking flag.
    return _stable_hash(_translation_signature_payload(options, include_thinking_flag=True))


def load_cached_source_segments(
    task_id: str,
    media_key: str,
    *,
    media_signature: str,
    asr_signature: str,
) -> Optional[List[Dict]]:
    state = db.get_transcription_media_state(task_id, media_key)
    if not state:
        return None
    if str(state.get("media_signature") or "") != str(media_signature or ""):
        return None
    if str(state.get("asr_signature") or "") != str(asr_signature or ""):
        return None
    segments = state.get("source_segments")
    if isinstance(segments, list) and segments:
        return segments
    return None


def save_source_segments(
    task_id: str,
    media_key: str,
    *,
    source_path: str,
    media_signature: str,
    asr_signature: str,
    source_segments: List[Dict],
):
    db.upsert_transcription_media_state(
        task_id,
        media_key,
        source_path=source_path,
        media_signature=media_signature,
        asr_signature=asr_signature,
        phase="asr_done",
        source_segments=source_segments,
    )


def load_cached_translation_map(
    task_id: str,
    media_key: str,
    source_segments: List[Dict],
    *,
    media_signature: str,
    translation_signature: str,
    compatible_translation_signatures: Optional[List[str]] = None,
) -> Dict[int, str]:
    accepted_signatures = {
        str(translation_signature or "").strip(),
        *(str(item or "").strip() for item in (compatible_translation_signatures or [])),
    }
    accepted_signatures.discard("")
    state = db.get_transcription_media_state(task_id, media_key)
    if state:
        media_mismatch = str(state.get("media_signature") or "") != str(media_signature or "")
        current_translation_signature = str(state.get("translation_signature") or "")
        translation_mismatch = bool(current_translation_signature and current_translation_signature not in accepted_signatures)
        if media_mismatch or translation_mismatch:
            db.clear_transcription_translation_segments(task_id, media_key)
        elif not current_translation_signature:
            db.upsert_transcription_media_state(
                task_id,
                media_key,
                media_signature=media_signature,
                translation_signature=translation_signature,
                phase="translation_running",
            )
            state = db.get_transcription_media_state(task_id, media_key)
    else:
        db.upsert_transcription_media_state(
            task_id,
            media_key,
            media_signature=media_signature,
            translation_signature=translation_signature,
            phase="translation_running",
        )
        state = db.get_transcription_media_state(task_id, media_key)

    rows = db.list_transcription_translation_segments(task_id, media_key)
    cached: Dict[int, str] = {}
    for row in rows:
        idx = int(row.get("segment_index") or 0)
        if idx <= 0 or idx > len(source_segments):
            continue
        status = str(row.get("status") or "").strip().lower()
        if status not in {"translated", "fallback", "skipped"}:
            continue
        source_text = normalize_segment_text((source_segments[idx - 1] or {}).get("text", ""))
        if hash_segment_text(source_text) != str(row.get("source_text_hash") or ""):
            continue
        cached[idx] = str(row.get("translated_text") or "")

    if cached:
        return cached

    if not state:
        return {}
    if str(state.get("media_signature") or "") != str(media_signature or ""):
        return {}
    if str(state.get("translation_signature") or "") not in accepted_signatures:
        return {}
    translated_segments = state.get("translated_segments")
    if not isinstance(translated_segments, list):
        return {}
    if len(translated_segments) != len(source_segments):
        return {}
    for idx, segment in enumerate(translated_segments, start=1):
        cached[idx] = normalize_segment_text((segment or {}).get("text", ""))
    return cached


def save_translation_segment(
    task_id: str,
    media_key: str,
    segment_index: int,
    source_text: str,
    translated_text: str,
    *,
    status: str = "translated",
    message: str = "",
):
    db.upsert_transcription_translation_segment(
        task_id,
        media_key,
        int(segment_index),
        source_text_hash=hash_segment_text(source_text),
        translated_text=normalize_segment_text(translated_text),
        status=str(status or "translated").strip().lower() or "translated",
        message=str(message or "").strip(),
    )


def save_translated_segments(
    task_id: str,
    media_key: str,
    *,
    media_signature: str,
    translation_signature: str,
    translated_segments: List[Dict],
):
    db.upsert_transcription_media_state(
        task_id,
        media_key,
        media_signature=media_signature,
        translation_signature=translation_signature,
        phase="translation_done",
        translated_segments=translated_segments,
    )


def mark_media_completed(
    task_id: str,
    media_key: str,
    *,
    media_signature: str,
    asr_signature: str,
    translation_signature: str,
):
    db.upsert_transcription_media_state(
        task_id,
        media_key,
        media_signature=media_signature,
        asr_signature=asr_signature,
        translation_signature=translation_signature,
        phase="completed",
    )
