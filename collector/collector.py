from __future__ import annotations

from collector.database import Database
from collector.technocore_client import TechnocoreClient


def collect_once(
    room: str = "technocore",
    db_path: str = "data/technocore.db",
) -> tuple[int, int]:
    db = Database(db_path)
    client = TechnocoreClient()

    since = db.get_cursor(room)

    result = client.read_room(
        room=room,
        since=since,
        limit=200,
        wait=10,
    )

    saved = 0

    for message in result.messages:
        if db.save_message(room, message):
            saved += 1

    if result.last_seq > since:
        db.set_cursor(room, result.last_seq)

    db.close()

    return saved, result.last_seq


if __name__ == "__main__":
    saved, last_seq = collect_once()

    print(f"saved: {saved}")
    print(f"last_seq: {last_seq}")
