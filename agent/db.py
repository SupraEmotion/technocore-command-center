from __future__ import annotations

import sqlite3
from pathlib import Path


DB_PATH = Path("/opt/technocore-command-center/data/technocore.db")


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    db_path = path if path is not None else DB_PATH
    db = sqlite3.connect(
        db_path,
        timeout=30.0,
    )
    db.row_factory = sqlite3.Row

    db.execute("PRAGMA busy_timeout = 30000")
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA synchronous = NORMAL")

    return db
