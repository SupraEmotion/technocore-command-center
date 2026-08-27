"""Snapshot and report changes in public Technocore protocol metadata."""

from __future__ import annotations

import argparse
import hashlib
import json

from collector.database import Database
from .diff import classify_endpoint, json_diff
from .protocol import DEFAULT_BASE_URL, parse_json, snapshot


def body_hash(body: str | None) -> str:
    return hashlib.sha256((body or "").encode("utf-8")).hexdigest()


def extract_version(observation) -> str | None:
    parsed = parse_json(observation)

    if not parsed:
        return None

    value = parsed.get("version")
    return str(value) if value is not None else None


def describe_changes(endpoint: str, old_body: str | None, new_body: str | None):
    changes = json_diff(old_body, new_body)

    if changes:
        print(f"           category={classify_endpoint(endpoint)}")
        print(f"           changes={len(changes)}")

        for change in changes[:20]:
            print(
                f"           {change['type']:7} "
                f"{change['path']}: "
                f"{change['old']!r} -> {change['new']!r}"
            )

        if len(changes) > 20:
            print(f"           ... {len(changes) - 20} more changes")

    else:
        print(f"           category={classify_endpoint(endpoint)}")
        print("           body changed but no structured JSON diff")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Snapshot and detect Technocore protocol changes."
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

        changes_detected = 0

        for observation in observations:
            digest = body_hash(observation.body)
            version = extract_version(observation)

            previous = db.get_latest_protocol_snapshot(
                observation.name
            )

            if previous is None:
                state = "NEW"
            elif previous["body_hash"] == digest:
                state = "UNCHANGED"
            else:
                state = "CHANGED"
                changes_detected += 1

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

            if state == "CHANGED":
                describe_changes(
                    observation.name,
                    previous["body"],
                    observation.body,
                )

        print()
        print(f"changes_detected={changes_detected}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
