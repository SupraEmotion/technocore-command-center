from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from agent.state import DB_PATH


@dataclass(frozen=True)
class Approval:
    id: int
    candidate_id: int
    status: str
    created_at: str
    decided_at: str | None
    decided_by: str | None
    reason: str | None


VALID_STATUSES = {
    "pending",
    "approved",
    "rejected",
    "published",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH, timeout=10.0)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout = 10000")

    db.execute("""
        CREATE TABLE IF NOT EXISTS agent_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL UNIQUE,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            decided_at TEXT,
            decided_by TEXT,
            reason TEXT,
            FOREIGN KEY(candidate_id)
                REFERENCES agent_candidates(id)
        )
    """)

    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_approvals_status
        ON agent_approvals(status)
    """)

    db.commit()
    return db


def create_pending(candidate_id: int) -> Approval:
    db = connect()

    try:
        existing = db.execute(
            """
            SELECT *
            FROM agent_approvals
            WHERE candidate_id = ?
            """,
            (candidate_id,),
        ).fetchone()

        if existing:
            return Approval(**dict(existing))

        created = now()

        cursor = db.execute(
            """
            INSERT INTO agent_approvals (
                candidate_id,
                status,
                created_at
            )
            VALUES (?, 'pending', ?)
            """,
            (candidate_id, created),
        )

        db.commit()

        row = db.execute(
            """
            SELECT *
            FROM agent_approvals
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

        return Approval(**dict(row))

    finally:
        db.close()


def get(candidate_id: int) -> Approval | None:
    db = connect()

    try:
        row = db.execute(
            """
            SELECT *
            FROM agent_approvals
            WHERE candidate_id = ?
            """,
            (candidate_id,),
        ).fetchone()

        if row is None:
            return None

        return Approval(**dict(row))

    finally:
        db.close()


def decide(
    candidate_id: int,
    status: str,
    *,
    decided_by: str = "human",
    reason: str | None = None,
) -> Approval:
    if status not in {"approved", "rejected"}:
        raise ValueError(
            "decision status must be 'approved' or 'rejected'"
        )

    db = connect()

    try:
        row = db.execute(
            """
            SELECT *
            FROM agent_approvals
            WHERE candidate_id = ?
            """,
            (candidate_id,),
        ).fetchone()

        if row is None:
            raise ValueError(
                f"candidate {candidate_id} has no approval record"
            )

        current = row["status"]

        if current != "pending":
            raise ValueError(
                f"candidate {candidate_id} is already {current}"
            )

        db.execute(
            """
            UPDATE agent_approvals
            SET
                status = ?,
                decided_at = ?,
                decided_by = ?,
                reason = ?
            WHERE candidate_id = ?
            """,
            (
                status,
                now(),
                decided_by,
                reason,
                candidate_id,
            ),
        )

        db.commit()

        updated = db.execute(
            """
            SELECT *
            FROM agent_approvals
            WHERE candidate_id = ?
            """,
            (candidate_id,),
        ).fetchone()

        return Approval(**dict(updated))

    finally:
        db.close()


def mark_published(candidate_id: int) -> Approval:
    db = connect()

    try:
        row = db.execute(
            """
            SELECT *
            FROM agent_approvals
            WHERE candidate_id = ?
            """,
            (candidate_id,),
        ).fetchone()

        if row is None:
            raise ValueError(
                f"candidate {candidate_id} has no approval record"
            )

        if row["status"] != "approved":
            raise ValueError(
                f"candidate {candidate_id} is not approved"
            )

        db.execute(
            """
            UPDATE agent_approvals
            SET
                status = 'published',
                decided_at = ?,
                decided_by = 'publisher'
            WHERE candidate_id = ?
            """,
            (now(), candidate_id),
        )

        db.commit()

        updated = db.execute(
            """
            SELECT *
            FROM agent_approvals
            WHERE candidate_id = ?
            """,
            (candidate_id,),
        ).fetchone()

        return Approval(**dict(updated))

    finally:
        db.close()


def pending() -> list[Approval]:
    db = connect()

    try:
        rows = db.execute(
            """
            SELECT *
            FROM agent_approvals
            WHERE status = 'pending'
            ORDER BY id ASC
            """
        ).fetchall()

        return [Approval(**dict(row)) for row in rows]

    finally:
        db.close()


if __name__ == "__main__":
    print("APPROVAL STATE")
    print("==============")

    for approval in pending():
        print()
        print("ID:", approval.id)
        print("CANDIDATE:", approval.candidate_id)
        print("STATUS:", approval.status)
        print("CREATED:", approval.created_at)
