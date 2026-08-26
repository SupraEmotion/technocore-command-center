from __future__ import annotations

import logging
import signal
import time

from collector.database import Database
from collector.technocore_client import TechnocoreClient


ROOM = "technocore"
DB_PATH = "data/technocore.db"

RUNNING = True

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger("technocore-collector")


def stop_handler(signum: int, frame: object) -> None:
    global RUNNING
    RUNNING = False
    logger.info("shutdown signal received")


def collect_once(
    room: str = ROOM,
    db_path: str = DB_PATH,
) -> tuple[int, int]:
    db = Database(db_path)
    client = TechnocoreClient()

    try:
        since = db.get_cursor(room)

        result = client.read_room(
            room=room,
            since=since,
            limit=200,
            wait=10,
        )

        saved = db.save_batch(
            room=room,
            messages=result.messages,
            last_seq=result.last_seq,
        )

        return saved, result.last_seq

    finally:
        db.close()


def run_forever() -> None:
    logger.info("Technocore collector starting")

    while RUNNING:
        try:
            saved, last_seq = collect_once()

            logger.info(
                "collection complete saved=%s last_seq=%s",
                saved,
                last_seq,
            )

        except Exception:
            logger.exception("collection failed; retrying in 10 seconds")

            for _ in range(10):
                if not RUNNING:
                    break
                time.sleep(1)

    logger.info("Technocore collector stopped")


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)

    run_forever()
