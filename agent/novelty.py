from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass

from agent.state import DB_PATH, now


@dataclass(frozen=True)
class NoveltyResult:
    novel: bool
    reason: str


def normalize(text: str) -> str:
    value = text.lower()

    # URLs are evidence, not the substance of the contribution.
    value = re.sub(r"https?://\S+", "<url>", value)

    # Numbers that merely represent a changing observation should
    # not make every candidate appear new.
    value = re.sub(r"\b\d[\d,]*\b", "<number>", value)

    value = re.sub(r"\s+", " ", value).strip()

    return value


def fingerprint(topic: str, draft: str) -> str:
    value = f"{topic}:{normalize(draft)}"
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def ensure_schema(db: sqlite3.Connection) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS agent_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            topic TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            draft TEXT NOT NULL,
            source_seq INTEGER,
            score REAL
        )
    """)

    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_candidates_fp
        ON agent_candidates(fingerprint)
    """)

    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_candidates_topic
        ON agent_candidates(topic, created_at)
    """)

    db.commit()


def check_novelty(
    topic: str,
    draft: str,
    cooldown_seconds: int = 1800,
) -> NoveltyResult:

    fp = fingerprint(topic, draft)

    db = sqlite3.connect(DB_PATH)

    try:
        ensure_schema(db)

        exact = db.execute(
            """
            SELECT 1
            FROM agent_candidates
            WHERE fingerprint = ?
            LIMIT 1
            """,
            (fp,),
        ).fetchone()

        if exact:
            return NoveltyResult(
                False,
                "duplicate_candidate",
            )

        recent = db.execute(
            """
            SELECT created_at
            FROM agent_candidates
            WHERE topic = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (topic,),
        ).fetchone()

        if recent:
            from datetime import datetime, timezone

            previous = datetime.fromisoformat(
                recent[0].replace("Z", "+00:00")
            )

            elapsed = (
                datetime.now(timezone.utc) - previous
            ).total_seconds()

            if elapsed < cooldown_seconds:
                return NoveltyResult(
                    False,
                    "topic_cooldown",
                )

        return NoveltyResult(True, "new_candidate")

    finally:
        db.close()


def record_candidate(
    topic: str,
    draft: str,
    source_seq: int | None = None,
    score: float | None = None,
) -> int:

    fp = fingerprint(topic, draft)

    db = sqlite3.connect(DB_PATH)

    try:
        ensure_schema(db)

        cursor = db.execute(
            """
            INSERT INTO agent_candidates
            (
                created_at,
                topic,
                fingerprint,
                draft,
                source_seq,
                score
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                now(),
                topic,
                fp,
                draft,
                source_seq,
                score,
            ),
        )

        db.commit()

        return int(cursor.lastrowid)

    finally:
        db.close()
