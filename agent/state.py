from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timezone


DB_PATH = Path("/opt/technocore-command-center/data/technocore.db")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH, timeout=10.0)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout = 10000")

    db.execute("""
        CREATE TABLE IF NOT EXISTS agent_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            source_seq INTEGER,
            source_did TEXT,
            source_text TEXT,
            decision TEXT,
            score REAL,
            reason TEXT
        )
    """)

    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_events_seq
        ON agent_events(source_seq)
    """)

    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_events_type
        ON agent_events(event_type)
    """)

    db.commit()
    return db


def record_event(
    event_type: str,
    *,
    source_seq: int | None = None,
    source_did: str | None = None,
    source_text: str | None = None,
    decision: str | None = None,
    score: float | None = None,
    reason: str | None = None,
) -> None:
    db = connect()

    try:
        db.execute(
            """
            INSERT INTO agent_events (
                created_at,
                event_type,
                source_seq,
                source_did,
                source_text,
                decision,
                score,
                reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now(),
                event_type,
                source_seq,
                source_did,
                source_text,
                decision,
                score,
                reason,
            ),
        )

        db.commit()
    finally:
        db.close()


def already_seen(seq: int) -> bool:
    db = connect()

    try:
        row = db.execute(
            """
            SELECT 1
            FROM agent_events
            WHERE source_seq = ?
            LIMIT 1
            """,
            (seq,),
        ).fetchone()

        return row is not None
    finally:
        db.close()


def recent_publications(limit: int = 10) -> list[sqlite3.Row]:
    db = connect()

    try:
        return db.execute(
            """
            SELECT *
            FROM agent_events
            WHERE event_type = 'published'
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        db.close()
