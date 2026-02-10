import datetime
import json
import sqlite3
import uuid
from typing import Dict, List, Optional

from .core import get_connection

_SETTINGS_TRANSCRIPTION_CONFIG = "admin_transcription_config_v1"


def _now() -> datetime.datetime:
    return datetime.datetime.now()


def get_setting(key: str) -> Optional[str]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row["value"] if row else None


def set_setting(key: str, value: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO app_settings (key, value, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET
             value = excluded.value,
             updated_at = excluded.updated_at""",
        (key, value, _now()),
    )
    conn.commit()
    conn.close()


def get_transcription_config(default_factory) -> Dict:
    raw = get_setting(_SETTINGS_TRANSCRIPTION_CONFIG)
    if not raw:
        config = default_factory()
        set_transcription_config(config)
        return config
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    config = default_factory()
    set_transcription_config(config)
    return config


def set_transcription_config(payload: Dict):
    set_setting(_SETTINGS_TRANSCRIPTION_CONFIG, json.dumps(payload, ensure_ascii=False))


def create_model_download_job(model_id: str, backend: str, request_payload: Dict | None = None) -> str:
    job_id = uuid.uuid4().hex
    conn = get_connection()
    cur = conn.cursor()
    now = _now()
    cur.execute(
        """INSERT INTO model_download_jobs
           (job_id, model_id, backend, status, progress, downloaded_bytes, total_bytes,
            message, result_json, error, request_json, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job_id,
            str(model_id or ""),
            str(backend or ""),
            "PENDING",
            0.0,
            0,
            0,
            "等待下载",
            "{}",
            "",
            json.dumps(request_payload or {}, ensure_ascii=False),
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()
    return job_id


def update_model_download_job(
    job_id: str,
    *,
    status: Optional[str] = None,
    progress: Optional[float] = None,
    downloaded_bytes: Optional[int] = None,
    total_bytes: Optional[int] = None,
    message: Optional[str] = None,
    result: Optional[Dict] = None,
    error: Optional[str] = None,
):
    updates = ["updated_at = ?"]
    params: List = [_now()]
    if status is not None:
        updates.append("status = ?")
        params.append(str(status))
    if progress is not None:
        updates.append("progress = ?")
        params.append(max(0.0, min(100.0, float(progress))))
    if downloaded_bytes is not None:
        updates.append("downloaded_bytes = ?")
        params.append(max(0, int(downloaded_bytes)))
    if total_bytes is not None:
        updates.append("total_bytes = ?")
        params.append(max(0, int(total_bytes)))
    if message is not None:
        updates.append("message = ?")
        params.append(str(message))
    if result is not None:
        updates.append("result_json = ?")
        params.append(json.dumps(result, ensure_ascii=False))
    if error is not None:
        updates.append("error = ?")
        params.append(str(error))

    params.append(job_id)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"UPDATE model_download_jobs SET {', '.join(updates)} WHERE job_id = ?", tuple(params))
    conn.commit()
    conn.close()


def get_model_download_job(job_id: str) -> Optional[Dict]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM model_download_jobs WHERE job_id = ?", (job_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    payload = dict(row)
    for key in ["result_json", "request_json"]:
        raw = payload.get(key)
        try:
            payload[key] = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload[key] = {}
    return payload


def list_model_download_jobs(limit: int = 50) -> List[Dict]:
    safe_limit = min(max(int(limit or 50), 1), 500)
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM model_download_jobs ORDER BY created_at DESC LIMIT ?", (safe_limit,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    for payload in rows:
        for key in ["result_json", "request_json"]:
            raw = payload.get(key)
            try:
                payload[key] = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload[key] = {}
    return rows
