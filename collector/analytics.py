from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path


DB_PATH = Path("data/technocore.db")


def classify_message(text: str) -> str:
    value = text.lower()

    if "public contribution" in value or "research" in value:
        return "contribution"

    if "heartbeat" in value:
        return "heartbeat"

    if "signed and present" in value or "identity active" in value:
        return "presence"

    if "protocol engagement" in value or "protocol" in value:
        return "protocol"

    if "autonomous agent operational" in value:
        return "agent_status"

    if "continuous participation" in value:
        return "participation"

    return "other"


def did_summary(db_path: str | Path = DB_PATH) -> list[dict]:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    rows = db.execute(
        """
        SELECT
            did,
            COUNT(*) AS message_count,
            COUNT(DISTINCT text) AS unique_text_count,
            MIN(timestamp) AS first_seen,
            MAX(timestamp) AS last_seen
        FROM messages
        WHERE did IS NOT NULL
        GROUP BY did
        ORDER BY message_count DESC, last_seen DESC
        """
    ).fetchall()

    results = [dict(row) for row in rows]

    db.close()
    return results


def category_summary(db_path: str | Path = DB_PATH) -> Counter:
    db = sqlite3.connect(db_path)

    rows = db.execute(
        """
        SELECT text
        FROM messages
        """
    ).fetchall()

    db.close()

    return Counter(
        classify_message(row[0])
        for row in rows
    )


if __name__ == "__main__":
    summaries = did_summary()

    print("=== DID ACTIVITY ===")

    for item in summaries[:20]:
        print(
            f"{item['message_count']:>4} messages | "
            f"{item['unique_text_count']:>3} unique | "
            f"{item['did']}"
        )

    print("\n=== MESSAGE CATEGORIES ===")

    for category, count in category_summary().most_common():
        print(f"{category:16} {count}")
