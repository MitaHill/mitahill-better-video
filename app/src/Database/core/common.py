import logging
import os
import sqlite3
from pathlib import Path


logger = logging.getLogger("DB")
DB_PATH = Path(os.getenv("DB_PATH", "/workspace/storage/data/tasks.db"))


def _apply_pragmas(conn):
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=30000;")


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    _apply_pragmas(conn)
    return conn
