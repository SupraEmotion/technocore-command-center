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
            """
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

        self.connection.commit()

        return cursor.rowcount == 1

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

    def close(self) -> None:
        self.connection.close()
