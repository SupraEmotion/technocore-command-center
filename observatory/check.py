"""Snapshot public Technocore protocol metadata into SQLite."""

from __future__ import annotations

import argparse
import hashlib
import json

from collector.database import Database
from .protocol import DEFAULT_BASE_URL, snapshot, parse_json


def body_hash(body: str | None) -> str:
    data = (body or "").encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def extract_version(observation) -> str | None:
    parsed = parse_json(observation)

    if not parsed:
        return None

    value = parsed.get("version")

    return str(value) if value is not None else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Snapshot public Technocore protocol metadata."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    db = Database("data/technocore.db")

    try:
        observations = snapshot(
            base_url=args.base_url,
            timeout=args.timeout,
        )

        for observation in observations:
            digest = body_hash(observation.body)
            version = extract_version(observation)

            latest = db.get_latest_protocol_snapshot(
                observation.name
            )

            if latest is None:
                state = "NEW"
            elif latest["body_hash"] == digest:
                state = "UNCHANGED"
            else:
                state = "CHANGED"

            saved = db.save_protocol_snapshot(
                endpoint=observation.name,
                path=observation.path,
                status=observation.status,
                content_type=observation.content_type,
                body_hash=digest,
                body=observation.body,
                version=version,
            )

            print(
                f"{state:10} "
                f"{observation.name:16} "
                f"HTTP={observation.status} "
                f"bytes={len(observation.body or '')} "
                f"saved={saved}"
            )

            if version:
                print(f"           version={version}")

            if observation.error:
                print(f"           error={observation.error}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
