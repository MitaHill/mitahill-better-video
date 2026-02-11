import datetime
import json
import sqlite3
from typing import Any, Dict, List

from .common import get_connection

_MAX_EVENTS_PER_TASK = 5000


def append_task_stream_event(
    task_id: str,
    channel: str,
    mode: str,
    text: str,
    *,
    file_index: int = 0,
    file_count: int = 0,
    segment_index: int = 0,
    line_key: str = "",
    meta: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    safe_task_id = str(task_id or "").strip()
    if not safe_task_id:
        raise ValueError("task_id required")

    now = datetime.datetime.now()
    safe_channel = str(channel or "").strip().lower() or "general"
    safe_mode = str(mode or "").strip().lower() or "line"
    safe_text = str(text or "")
    safe_line_key = str(line_key or "").strip()
    meta_json = json.dumps(meta or {}, ensure_ascii=False)

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO task_stream_events
           (task_id, created_at, channel, mode, line_key, text, file_index, file_count, segment_index, meta_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            safe_task_id,
            now,
            safe_channel,
            safe_mode,
            safe_line_key,
            safe_text,
            int(file_index or 0),
            int(file_count or 0),
            int(segment_index or 0),
            meta_json,
        ),
    )
    row_id = int(c.lastrowid or 0)
    c.execute(
        """DELETE FROM task_stream_events
           WHERE task_id = ?
             AND id NOT IN (
               SELECT id FROM task_stream_events
               WHERE task_id = ?
               ORDER BY id DESC
               LIMIT ?
             )""",
        (safe_task_id, safe_task_id, _MAX_EVENTS_PER_TASK),
    )
    conn.commit()
    conn.close()
    return {
        "id": row_id,
        "task_id": safe_task_id,
        "created_at": str(now),
        "channel": safe_channel,
        "mode": safe_mode,
        "line_key": safe_line_key,
        "text": safe_text,
        "file_index": int(file_index or 0),
        "file_count": int(file_count or 0),
        "segment_index": int(segment_index or 0),
        "meta": meta or {},
    }


def list_task_stream_events(task_id: str, limit: int = 300) -> List[Dict[str, Any]]:
    safe_task_id = str(task_id or "").strip()
    if not safe_task_id:
        return []
    safe_limit = max(1, min(int(limit or 300), 5000))

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT id, task_id, created_at, channel, mode, line_key, text, file_index, file_count, segment_index, meta_json
           FROM (
             SELECT id, task_id, created_at, channel, mode, line_key, text, file_index, file_count, segment_index, meta_json
             FROM task_stream_events
             WHERE task_id = ?
             ORDER BY id DESC
             LIMIT ?
           ) t
           ORDER BY id ASC""",
        (safe_task_id, safe_limit),
    )
    rows = c.fetchall()
    conn.close()

    out = []
    for row in rows:
        record = dict(row)
        try:
            record["meta"] = json.loads(record.get("meta_json") or "{}")
        except Exception:
            record["meta"] = {}
        record.pop("meta_json", None)
        out.append(record)
    return out
