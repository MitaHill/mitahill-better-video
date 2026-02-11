import datetime
import sqlite3

from .common import get_connection


def upsert_task_progress(task_id, total_frames, total_segments):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO task_progress (task_id, total_frames, total_segments, updated_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(task_id) DO UPDATE SET
             total_frames = excluded.total_frames,
             total_segments = excluded.total_segments,
             updated_at = excluded.updated_at""",
        (task_id, total_frames, total_segments, datetime.datetime.now()),
    )
    conn.commit()
    conn.close()


def get_task_progress(task_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM task_progress WHERE task_id = ?", (task_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_segment(task_id, segment_key, segment_index, start_frame, end_frame, total_frames):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO segment_progress
           (task_id, segment_key, segment_index, start_frame, end_frame, total_frames, last_done_frame, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(task_id, segment_key) DO UPDATE SET
             segment_index = excluded.segment_index,
             start_frame = excluded.start_frame,
             end_frame = excluded.end_frame,
             total_frames = excluded.total_frames""",
        (task_id, segment_key, segment_index, start_frame, end_frame, total_frames, 0, datetime.datetime.now()),
    )
    conn.commit()
    conn.close()


def update_segment_progress(task_id, segment_key, last_done_frame):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """UPDATE segment_progress
           SET last_done_frame = ?, updated_at = ?
           WHERE task_id = ? AND segment_key = ?""",
        (last_done_frame, datetime.datetime.now(), task_id, segment_key),
    )
    conn.commit()
    conn.close()


def get_segment_progress(task_id, segment_key):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT * FROM segment_progress WHERE task_id = ? AND segment_key = ?",
        (task_id, segment_key),
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_latest_segment_progress(task_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """SELECT * FROM segment_progress
           WHERE task_id = ?
           ORDER BY (start_frame + COALESCE(last_done_frame, 0)) DESC, updated_at DESC
           LIMIT 1""",
        (task_id,),
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None
