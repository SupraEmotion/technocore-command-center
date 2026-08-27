from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path("data/technocore.db")


class Database:
    def __init__(self, path: str | Path = DEFAULT_DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row

        self._create_schema()
        self._migrate_protocol_changes()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                room TEXT NOT NULL,
                seq INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                did TEXT,
                text TEXT NOT NULL,
                nonce TEXT,
                observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (room, seq)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_did
                ON messages(did);

            CREATE INDEX IF NOT EXISTS idx_messages_timestamp
                ON messages(timestamp);

            CREATE TABLE IF NOT EXISTS cursors (
                room TEXT PRIMARY KEY,
                last_seq INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS protocol_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                endpoint TEXT NOT NULL,
                path TEXT NOT NULL,
                status INTEGER,
                content_type TEXT,
                body_hash TEXT NOT NULL,
                body TEXT,
                version TEXT
            );

            CREATE TABLE IF NOT EXISTS protocol_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                endpoint TEXT NOT NULL,
                category TEXT NOT NULL,
                previous_snapshot_id INTEGER,
                current_snapshot_id INTEGER NOT NULL,
                change_count INTEGER NOT NULL DEFAULT 0,
                summary TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'detected'
            );

            CREATE INDEX IF NOT EXISTS idx_protocol_changes_endpoint
                ON protocol_changes(endpoint, detected_at);

            CREATE INDEX IF NOT EXISTS idx_protocol_changes_status
                ON protocol_changes(status, detected_at);

            CREATE INDEX IF NOT EXISTS idx_protocol_snapshots_endpoint
                ON protocol_snapshots(endpoint, observed_at);

            CREATE INDEX IF NOT EXISTS idx_protocol_snapshots_hash
                ON protocol_snapshots(endpoint, body_hash);
            """
        )

        self.connection.commit()

    def _migrate_protocol_changes(self) -> None:
        columns = {
            row["name"]
            for row in self.connection.execute(
                "PRAGMA table_info(protocol_changes)"
            )
        }

        additions = {
            "severity": "TEXT NOT NULL DEFAULT 'low'",
            "direction": "TEXT NOT NULL DEFAULT 'neutral'",
            "research_priority": "TEXT NOT NULL DEFAULT 'low'",
        }

        for name, definition in additions.items():
            if name not in columns:
                self.connection.execute(
                    f"ALTER TABLE protocol_changes "
                    f"ADD COLUMN {name} {definition}"
                )

        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS "
            "idx_protocol_changes_priority "
            "ON protocol_changes(research_priority, detected_at)"
        )

        self.connection.commit()

    def save_message(
        self,
        room: str,
        message: dict[str, Any],
    ) -> bool:
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO messages
            (room, seq, timestamp, did, text, nonce)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                room,
                message["seq"],
                message["ts"],
                message.get("from"),
                message["text"],
                str(message["nonce"]) if "nonce" in message else None,
            ),
        )

        return cursor.rowcount == 1

    def save_batch(
        self,
        room: str,
        messages: list[dict[str, Any]],
        last_seq: int,
    ) -> int:
        saved = 0

        try:
            self.connection.execute("BEGIN")

            for message in messages:
                if self.save_message(room, message):
                    saved += 1

            if messages and last_seq > self.get_cursor(room):
                self.connection.execute(
                    """
                    INSERT INTO cursors(room, last_seq)
                    VALUES (?, ?)
                    ON CONFLICT(room)
                    DO UPDATE SET last_seq = excluded.last_seq
                    """,
                    (room, last_seq),
                )

            self.connection.commit()

            return saved

        except Exception:
            self.connection.rollback()
            raise

    def get_cursor(self, room: str) -> int:
        row = self.connection.execute(
            """
            SELECT last_seq
            FROM cursors
            WHERE room = ?
            """,
            (room,),
        ).fetchone()

        return int(row["last_seq"]) if row else 0

    def set_cursor(self, room: str, last_seq: int) -> None:
        self.connection.execute(
            """
            INSERT INTO cursors(room, last_seq)
            VALUES (?, ?)
            ON CONFLICT(room)
            DO UPDATE SET last_seq = excluded.last_seq
            """,
            (room, last_seq),
        )

        self.connection.commit()

    def save_protocol_snapshot(
        self,
        endpoint: str,
        path: str,
        status: int | None,
        content_type: str | None,
        body_hash: str,
        body: str | None,
        version: str | None = None,
        observed_at: str | None = None,
    ) -> int | None:
        """
        Save a protocol observation only when its response hash differs
        from the most recent observation for the same endpoint.
        """

        previous = self.connection.execute(
            """
            SELECT body_hash
            FROM protocol_snapshots
            WHERE endpoint = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (endpoint,),
        ).fetchone()

        if previous and previous["body_hash"] == body_hash:
            return None

        self.connection.execute(
            """
            INSERT INTO protocol_snapshots
            (observed_at, endpoint, path, status, content_type,
             body_hash, body, version)
            VALUES (
                COALESCE(?, CURRENT_TIMESTAMP),
                ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                observed_at,
                endpoint,
                path,
                status,
                content_type,
                body_hash,
                body,
                version,
            ),
        )

        self.connection.commit()
        return int(self.connection.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0])

    def get_latest_protocol_snapshot(
        self,
        endpoint: str,
    ) -> sqlite3.Row | None:
        return self.connection.execute(
            """
            SELECT *
            FROM protocol_snapshots
            WHERE endpoint = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (endpoint,),
        ).fetchone()

    def save_protocol_change(
        self,
        endpoint: str,
        category: str,
        previous_snapshot_id: int | None,
        current_snapshot_id: int,
        change_count: int,
        summary: str,
        status: str = "detected",
        severity: str = "low",
        direction: str = "neutral",
        research_priority: str = "low",
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO protocol_changes (
                endpoint,
                category,
                previous_snapshot_id,
                current_snapshot_id,
                change_count,
                summary,
                status,
                severity,
                direction,
                research_priority
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                endpoint,
                category,
                previous_snapshot_id,
                current_snapshot_id,
                change_count,
                summary,
                status,
                severity,
                direction,
                research_priority,
            ),
        )

        self.connection.commit()
        return int(cursor.lastrowid)

    def get_protocol_changes(
        self,
        endpoint: str | None = None,
        limit: int = 50,
    ) -> list[sqlite3.Row]:
        if endpoint is None:
            return self.connection.execute(
                """
                SELECT *
                FROM protocol_changes
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return self.connection.execute(
            """
            SELECT *
            FROM protocol_changes
            WHERE endpoint = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (endpoint, limit),
        ).fetchall()

    def close(self) -> None:
        self.connection.close()
