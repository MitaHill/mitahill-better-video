import datetime
import json
import sqlite3

from .common import get_connection


def _json_dumps_or_empty(payload):
    if payload is None:
        return ""
    return json.dumps(payload, ensure_ascii=False)


def _json_loads_or_none(raw):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def upsert_transcription_media_state(
    task_id,
    media_key,
    *,
    source_path=None,
    media_signature=None,
    asr_signature=None,
    translation_signature=None,
    phase=None,
    source_segments=None,
    translated_segments=None,
):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO transcription_media_state
           (task_id, media_key, source_path, media_signature, asr_signature, translation_signature,
            phase, source_segments_json, translated_segments_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(task_id, media_key) DO UPDATE SET
             source_path = COALESCE(excluded.source_path, source_path),
             media_signature = COALESCE(excluded.media_signature, media_signature),
             asr_signature = COALESCE(excluded.asr_signature, asr_signature),
             translation_signature = COALESCE(excluded.translation_signature, translation_signature),
             phase = COALESCE(excluded.phase, phase),
             source_segments_json = CASE
               WHEN excluded.source_segments_json = '' THEN source_segments_json
               ELSE excluded.source_segments_json
             END,
             translated_segments_json = CASE
               WHEN excluded.translated_segments_json = '' THEN translated_segments_json
               ELSE excluded.translated_segments_json
             END,
             updated_at = excluded.updated_at""",
        (
            str(task_id),
            str(media_key),
            str(source_path) if source_path is not None else None,
            str(media_signature) if media_signature is not None else None,
            str(asr_signature) if asr_signature is not None else None,
            str(translation_signature) if translation_signature is not None else None,
            str(phase) if phase is not None else None,
            _json_dumps_or_empty(source_segments),
            _json_dumps_or_empty(translated_segments),
            datetime.datetime.now(),
        ),
    )
    conn.commit()
    conn.close()


def get_transcription_media_state(task_id, media_key):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT task_id, media_key, source_path, media_signature, asr_signature, translation_signature,
                  phase, source_segments_json, translated_segments_json, updated_at
           FROM transcription_media_state
           WHERE task_id = ? AND media_key = ?""",
        (str(task_id), str(media_key)),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    payload = dict(row)
    payload["source_segments"] = _json_loads_or_none(payload.pop("source_segments_json", ""))
    payload["translated_segments"] = _json_loads_or_none(payload.pop("translated_segments_json", ""))
    return payload


def upsert_transcription_translation_segment(
    task_id,
    media_key,
    segment_index,
    *,
    source_text_hash="",
    translated_text="",
    status="translated",
    message="",
):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO transcription_translation_state
           (task_id, media_key, segment_index, source_text_hash, translated_text, status, message, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(task_id, media_key, segment_index) DO UPDATE SET
             source_text_hash = excluded.source_text_hash,
             translated_text = excluded.translated_text,
             status = excluded.status,
             message = excluded.message,
             updated_at = excluded.updated_at""",
        (
            str(task_id),
            str(media_key),
            int(segment_index),
            str(source_text_hash or ""),
            str(translated_text or ""),
            str(status or "translated"),
            str(message or ""),
            datetime.datetime.now(),
        ),
    )
    conn.commit()
    conn.close()


def get_transcription_translation_segment(task_id, media_key, segment_index):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT task_id, media_key, segment_index, source_text_hash, translated_text, status, message, updated_at
           FROM transcription_translation_state
           WHERE task_id = ? AND media_key = ? AND segment_index = ?""",
        (str(task_id), str(media_key), int(segment_index)),
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def list_transcription_translation_segments(task_id, media_key):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT task_id, media_key, segment_index, source_text_hash, translated_text, status, message, updated_at
           FROM transcription_translation_state
           WHERE task_id = ? AND media_key = ?
           ORDER BY segment_index ASC""",
        (str(task_id), str(media_key)),
    )
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def clear_transcription_translation_segments(task_id, media_key):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "DELETE FROM transcription_translation_state WHERE task_id = ? AND media_key = ?",
        (str(task_id), str(media_key)),
    )
    conn.commit()
    conn.close()
