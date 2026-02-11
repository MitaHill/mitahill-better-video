import datetime
import sqlite3
from typing import Dict, List

from .core import get_connection


def _now() -> datetime.datetime:
    return datetime.datetime.now()


def insert_gpu_samples(samples: List[Dict]):
    rows = []
    collected_at = _now()
    for item in samples or []:
        rows.append(
            (
                collected_at,
                int(item.get("gpu_index", 0)),
                str(item.get("gpu_name", "")).strip(),
                float(item.get("utilization_gpu", 0.0)),
                float(item.get("utilization_mem", 0.0)),
                float(item.get("memory_used_mb", 0.0)),
                float(item.get("memory_total_mb", 0.0)),
                float(item.get("temperature_c", 0.0)),
            )
        )
    if not rows:
        return
    conn = get_connection()
    cur = conn.cursor()
    cur.executemany(
        """INSERT INTO gpu_usage_samples
           (collected_at, gpu_index, gpu_name, utilization_gpu, utilization_mem, memory_used_mb, memory_total_mb, temperature_c)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    conn.close()


def prune_old_samples(retention_hours: int = 24):
    hours = max(int(retention_hours or 24), 1)
    cutoff = _now() - datetime.timedelta(hours=hours)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM gpu_usage_samples WHERE collected_at < ?", (cutoff,))
    conn.commit()
    conn.close()


def list_gpu_usage_series(seconds: int = 60) -> Dict:
    range_sec = max(min(int(seconds or 60), 24 * 3600), 10)
    start_at = _now() - datetime.timedelta(seconds=range_sec)

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """SELECT collected_at, gpu_index, gpu_name, utilization_gpu, utilization_mem,
                  memory_used_mb, memory_total_mb, temperature_c
           FROM gpu_usage_samples
           WHERE collected_at >= ?
           ORDER BY collected_at ASC, gpu_index ASC""",
        (start_at,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    by_gpu = {}
    for row in rows:
        gpu_index = int(row.get("gpu_index") or 0)
        key = str(gpu_index)
        item = by_gpu.get(key)
        if item is None:
            item = {
                "gpu_index": gpu_index,
                "gpu_name": row.get("gpu_name") or "",
                "samples": [],
            }
            by_gpu[key] = item
        item["samples"].append(
            {
                "ts": row.get("collected_at"),
                "utilization_gpu": float(row.get("utilization_gpu") or 0.0),
                "utilization_mem": float(row.get("utilization_mem") or 0.0),
                "memory_used_mb": float(row.get("memory_used_mb") or 0.0),
                "memory_total_mb": float(row.get("memory_total_mb") or 0.0),
                "temperature_c": float(row.get("temperature_c") or 0.0),
            }
        )

    series = sorted(by_gpu.values(), key=lambda item: item["gpu_index"])
    return {
        "range_seconds": range_sec,
        "series": series,
    }
