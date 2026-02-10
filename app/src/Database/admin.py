import datetime
import hashlib
import secrets
import sqlite3
from typing import Dict, List, Optional

from werkzeug.security import check_password_hash, generate_password_hash

from app.src.Utils.client_ip import describe_ip

from .core import get_connection


_SETTINGS_ADMIN_PASSWORD_HASH = "admin_password_hash"
_SETTINGS_REAL_IP_TRUSTED_PROXIES = "real_ip_trusted_proxies"


def _now():
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


def ensure_admin_password(initial_password: str):
    current = get_setting(_SETTINGS_ADMIN_PASSWORD_HASH)
    if current:
        return
    safe_initial = (initial_password or "").strip() or "change_me_please"
    set_setting(_SETTINGS_ADMIN_PASSWORD_HASH, generate_password_hash(safe_initial))


def verify_admin_password(password: str) -> bool:
    hashed = get_setting(_SETTINGS_ADMIN_PASSWORD_HASH)
    if not hashed:
        return False
    return check_password_hash(hashed, password or "")


def update_admin_password(new_password: str):
    set_setting(_SETTINGS_ADMIN_PASSWORD_HASH, generate_password_hash(new_password))


def ensure_real_ip_trusted_proxies(default_value: str):
    current = get_setting(_SETTINGS_REAL_IP_TRUSTED_PROXIES)
    if current is not None and str(current).strip() != "":
        return
    set_setting(_SETTINGS_REAL_IP_TRUSTED_PROXIES, (default_value or "").strip())


def get_real_ip_trusted_proxies(default_value: str = "") -> str:
    current = get_setting(_SETTINGS_REAL_IP_TRUSTED_PROXIES)
    if current is None or str(current).strip() == "":
        return (default_value or "").strip()
    return str(current).strip()


def update_real_ip_trusted_proxies(value: str):
    set_setting(_SETTINGS_REAL_IP_TRUSTED_PROXIES, (value or "").strip())


def _hash_token(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def prune_expired_sessions():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM admin_sessions WHERE expires_at <= ?", (_now(),))
    conn.commit()
    conn.close()


def create_admin_session(client_ip: str, user_agent: str, ttl_hours: float = 24.0) -> Dict[str, str]:
    prune_expired_sessions()
    token = secrets.token_urlsafe(48)
    session_id = secrets.token_hex(16)
    created_at = _now()
    expires_at = created_at + datetime.timedelta(hours=max(0.25, float(ttl_hours or 24.0)))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO admin_sessions
           (session_id, token_hash, created_at, expires_at, client_ip, user_agent)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (session_id, _hash_token(token), created_at, expires_at, client_ip, user_agent),
    )
    conn.commit()
    conn.close()
    return {
        "session_id": session_id,
        "token": token,
        "expires_at": expires_at.isoformat(),
    }


def get_admin_session_by_token(token: str):
    if not token:
        return None
    prune_expired_sessions()
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM admin_sessions WHERE token_hash = ?",
        (_hash_token(token),),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_session_by_token(token: str):
    if not token:
        return
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM admin_sessions WHERE token_hash = ?", (_hash_token(token),))
    conn.commit()
    conn.close()


def delete_all_sessions():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM admin_sessions")
    conn.commit()
    conn.close()


def get_task_counts() -> Dict[str, int]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT status, COUNT(1) FROM task_queue GROUP BY status")
    rows = cur.fetchall()
    cur.execute("SELECT COUNT(1) FROM task_queue")
    total = int(cur.fetchone()[0])
    conn.close()

    counts = {"PENDING": 0, "PROCESSING": 0, "COMPLETED": 0, "FAILED": 0, "TOTAL": total}
    for status, count in rows:
        counts[str(status)] = int(count)
    return counts


def list_tasks(limit: int = 200, offset: int = 0, status: str = "") -> List[Dict]:
    safe_limit = min(max(int(limit or 200), 1), 1000)
    safe_offset = max(int(offset or 0), 0)
    status = (status or "").strip().upper()

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if status:
        cur.execute(
            """SELECT task_id, created_at, updated_at, client_ip, task_category, status, progress, message
               FROM task_queue
               WHERE status = ?
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?""",
            (status, safe_limit, safe_offset),
        )
    else:
        cur.execute(
            """SELECT task_id, created_at, updated_at, client_ip, task_category, status, progress, message
               FROM task_queue
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?""",
            (safe_limit, safe_offset),
        )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    for row in rows:
        row["ip_info"] = describe_ip(row.get("client_ip") or "")
    return rows


def get_ip_access_stats(limit: int = 200) -> List[Dict]:
    safe_limit = min(max(int(limit or 200), 1), 2000)
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """SELECT client_ip, COUNT(1) AS visit_count,
                  SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) AS pending_count,
                  SUM(CASE WHEN status = 'PROCESSING' THEN 1 ELSE 0 END) AS processing_count,
                  SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) AS completed_count,
                  SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failed_count,
                  MAX(updated_at) AS last_seen
           FROM task_queue
           GROUP BY client_ip
           ORDER BY visit_count DESC, last_seen DESC
           LIMIT ?""",
        (safe_limit,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    for row in rows:
        row["ip_info"] = describe_ip(row.get("client_ip") or "")
    return rows
