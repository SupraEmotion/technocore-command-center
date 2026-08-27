from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from agent.db import DB_PATH, connect as db_connect


def connect() -> sqlite3.Connection:
    return db_connect(DB_PATH)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
