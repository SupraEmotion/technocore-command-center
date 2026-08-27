from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass

from agent.state import DB_PATH, now


@dataclass(frozen=True)
class Evidence:
    topic: str
    fingerprint: str
    source_type: str
    supporting_messages: int
    latest_seq: int | None
    confidence: float
    summary: str


TOPIC_PATTERNS = {
    "sequence_cursor": (
        "sequence",
        "cursor",
        "since=",
        "long-poll",
        "wait=",
    ),
    "signed_write": (
        "signed",
        "signature",
        "nonce",
        "timeout",
    ),
    "did": (
        "did",
        "identity",
        "ed25519",
    ),
    "protocol": (
        "protocol",
        "http",
        "api",
        "technocore",
    ),
}


def normalise_topic_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\d+", "N", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def detect_topics(text: str) -> list[str]:
    value = normalise_topic_text(text)

    topics = []

    for topic, terms in TOPIC_PATTERNS.items():
        matches = sum(1 for term in terms if term in value)

        if matches >= 2:
            topics.append(topic)

    return topics


def fingerprint(text: str) -> str:
    value = normalise_topic_text(text)

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()[:16]


def ensure_schema(db: sqlite3.Connection) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS agent_topics (
            topic TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            first_seen_seq INTEGER,
            latest_seq INTEGER,
            occurrences INTEGER NOT NULL DEFAULT 0,
            last_contribution_at TEXT,
            PRIMARY KEY (topic, fingerprint)
        )
    """)

    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_topics_topic
        ON agent_topics(topic)
    """)

    db.commit()


def inspect_message(
    seq: int,
    text: str,
) -> list[Evidence]:

    topics = detect_topics(text)

    if not topics:
        return []

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    try:
        ensure_schema(db)

        results = []

        for topic in topics:
            fp = fingerprint(text)

            row = db.execute("""
                SELECT
                    occurrences,
                    latest_seq,
                    last_contribution_at
                FROM agent_topics
                WHERE topic = ?
                  AND fingerprint = ?
            """, (topic, fp)).fetchone()

            occurrences = int(row["occurrences"]) if row else 0

            db.execute("""
                INSERT INTO agent_topics
                    (topic, fingerprint, first_seen_seq,
                     latest_seq, occurrences)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(topic, fingerprint)
                DO UPDATE SET
                    latest_seq = excluded.latest_seq,
                    occurrences = agent_topics.occurrences + 1
            """, (
                topic,
                fp,
                seq,
                seq,
            ))

            # This is only evidence that the network has discussed
            # the topic. It is NOT evidence that our own node
            # independently reproduced the claim.
            related = db.execute("""
                SELECT COUNT(*)
                FROM messages
                WHERE seq <= ?
                  AND (
                      lower(text) LIKE ?
                      OR lower(text) LIKE ?
                  )
            """, (
                seq,
                f"%{topic.replace('_', ' ')}%",
                f"%{topic.split('_')[0]}%",
            )).fetchone()[0]

            supporting = int(related)

            # Network discussion alone receives low confidence.
            confidence = 0.25 if supporting else 0.0

            results.append(
                Evidence(
                    topic=topic,
                    fingerprint=fp,
                    source_type="external_network_observation",
                    supporting_messages=supporting,
                    latest_seq=seq,
                    confidence=confidence,
                    summary=(
                        f"The network has discussed {topic} "
                        f"in {supporting} stored messages; "
                        f"our node has not independently verified "
                        f"the underlying claim."
                    ),
                )
            )

        db.commit()

        return results

    finally:
        db.close()


def mark_contribution(
    topic: str,
    fp: str,
) -> None:

    db = sqlite3.connect(DB_PATH)

    try:
        db.execute("""
            UPDATE agent_topics
            SET last_contribution_at = ?
            WHERE topic = ?
              AND fingerprint = ?
        """, (
            now(),
            topic,
            fp,
        ))

        db.commit()

    finally:
        db.close()
