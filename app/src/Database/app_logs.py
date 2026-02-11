import datetime
import json
import sqlite3
from typing import Dict, List

from .core import get_connection

_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_LEVEL_WEIGHT = {name: idx for idx, name in enumerate(_LEVELS)}


def _now() -> datetime.datetime:
    return datetime.datetime.now()


def _normalize_level(level: str) -> str:
    raw = str(level or "INFO").strip().upper()
    return raw if raw in _LEVEL_WEIGHT else "INFO"


def _allowed_levels(min_level: str) -> List[str]:
    level = _normalize_level(min_level)
    min_weight = _LEVEL_WEIGHT[level]
    return [name for name in _LEVELS if _LEVEL_WEIGHT[name] >= min_weight]


def insert_log(level: str, logger_name: str, message: str, extra: Dict | None = None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO app_logs (created_at, level, logger_name, message, extra_json)
           VALUES (?, ?, ?, ?, ?)""",
        (
            _now(),
            _normalize_level(level),
            str(logger_name or ""),
            str(message or ""),
            json.dumps(extra or {}, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()


def list_logs(
    min_level: str = "WARNING",
    limit: int = 200,
    offset: int = 0,
    logger_name: str = "",
    keyword: str = "",
) -> List[Dict]:
    safe_limit = min(max(int(limit or 200), 1), 1000)
    safe_offset = max(int(offset or 0), 0)
    levels = _allowed_levels(min_level)
    logger_name = str(logger_name or "").strip()
    keyword = str(keyword or "").strip()

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    filters = [f"level IN ({','.join('?' for _ in levels)})"]
    params = list(levels)

    if logger_name:
        filters.append("logger_name = ?")
        params.append(logger_name)
    if keyword:
        filters.append("(message LIKE ? OR logger_name LIKE ?)")
        like = f"%{keyword}%"
        params.extend([like, like])

    where_sql = " AND ".join(filters) if filters else "1=1"
    sql = (
        "SELECT id, created_at, level, logger_name, message, extra_json "
        "FROM app_logs "
        f"WHERE {where_sql} "
        "ORDER BY id DESC LIMIT ? OFFSET ?"
    )
    params.extend([safe_limit, safe_offset])
    cur.execute(sql, tuple(params))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    for row in rows:
        raw_extra = row.get("extra_json")
        try:
            row["extra"] = json.loads(raw_extra) if raw_extra else {}
        except json.JSONDecodeError:
            row["extra"] = {}
    return rows
