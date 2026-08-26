from __future__ import annotations

import hashlib
import re
import sqlite3
from collections import Counter
from pathlib import Path


DB_PATH = Path("data/technocore.db")

URL_RE = re.compile(r"https?://[^\s<>\"']+")


def message_hash(
    room: str,
    seq: int,
    did: str | None,
    text: str,
) -> str:
    payload = f"{room}|{seq}|{did or ''}|{text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def classify_message(text: str) -> str:
    value = text.lower()

    if any(
        term in value
        for term in (
            "public contribution",
            "research report",
            "research",
            "tutorial",
            "guide",
            "documentation",
            "article",
        )
    ):
        return "contribution"

    if any(
        term in value
        for term in (
            "github.com/",
            "technocore.chat/r/",
            "http://",
            "https://",
        )
    ):
        return "public_resource"

    if "heartbeat" in value:
        return "heartbeat"

    if any(
        term in value
        for term in (
            "signed and present",
            "identity active",
            "node reporting in",
        )
    ):
        return "presence"

    if "continuous participation" in value:
        return "participation"

    if any(
        term in value
        for term in (
            "autonomous agent operational",
            "agent operational",
        )
    ):
        return "agent_status"

    if "protocol" in value or "sequence" in value or "long-poll" in value:
        return "protocol"

    if any(
        term in value
        for term in (
            "task result",
            "task queue",
            "inference",
            "checkpoint",
            "peering",
            "coordination",
        )
    ):
        return "technical"

    return "other"


def extract_urls(text: str) -> list[str]:
    return URL_RE.findall(text)


def did_profiles(db_path: str | Path = DB_PATH) -> list[dict]:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    rows = db.execute(
        """
        SELECT
            did,
            COUNT(*) AS message_count,
            COUNT(DISTINCT text) AS unique_text_count,
            COUNT(DISTINCT room) AS rooms_seen,
            MIN(timestamp) AS first_seen,
            MAX(timestamp) AS last_seen
        FROM messages
        WHERE did IS NOT NULL
        GROUP BY did
        ORDER BY message_count DESC, last_seen DESC
        """
    ).fetchall()

    profiles = []

    for row in rows:
        message_count = row["message_count"]
        unique_text_count = row["unique_text_count"]

        profiles.append(
            {
                "did": row["did"],
                "message_count": message_count,
                "unique_text_count": unique_text_count,
                "rooms_seen": row["rooms_seen"],
                "first_seen": row["first_seen"],
                "last_seen": row["last_seen"],
                "duplicate_ratio": (
                    1 - (unique_text_count / message_count)
                    if message_count
                    else 0
                ),
            }
        )

    db.close()
    return profiles


def dataset_summary(db_path: str | Path = DB_PATH) -> dict:
    db = sqlite3.connect(db_path)

    total = db.execute(
        "SELECT COUNT(*) FROM messages"
    ).fetchone()[0]

    unique_dids = db.execute(
        """
        SELECT COUNT(DISTINCT did)
        FROM messages
        WHERE did IS NOT NULL
        """
    ).fetchone()[0]

    rows = db.execute(
        "SELECT text FROM messages"
    ).fetchall()

    db.close()

    categories = Counter(
        classify_message(row[0])
        for row in rows
    )

    urls = []
    for (text,) in rows:
        urls.extend(extract_urls(text))

    return {
        "messages": total,
        "unique_dids": unique_dids,
        "categories": categories,
        "public_urls": len(urls),
        "unique_public_urls": len(set(urls)),
    }


def run(db_path: str | Path = DB_PATH) -> None:
    summary = dataset_summary(db_path)

    print("=== DATASET SUMMARY ===")
    print("Messages:", summary["messages"])
    print("Unique DIDs:", summary["unique_dids"])
    print("Public URLs:", summary["public_urls"])
    print("Unique URLs:", summary["unique_public_urls"])

    print("\n=== CATEGORIES ===")
    for category, count in summary["categories"].most_common():
        print(f"{category:18} {count}")

    print("\n=== TOP DID PROFILES ===")

    for profile in did_profiles(db_path)[:20]:
        print(
            f"{profile['message_count']:>3} messages | "
            f"{profile['unique_text_count']:>2} unique | "
            f"duplicate={profile['duplicate_ratio']:.2f} | "
            f"{profile['did']}"
        )


if __name__ == "__main__":
    run()
