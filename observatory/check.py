"""Snapshot and report changes in public Technocore protocol metadata."""

from __future__ import annotations

import argparse
import hashlib
import json

from collector.database import Database
from .diff import classify_endpoint, json_diff
from .impact import assess_changes, highest_priority
from .semantic import classify_changes, summarize_categories
from .protocol import DEFAULT_BASE_URL, parse_json, snapshot


def body_hash(body: str | None) -> str:
    return hashlib.sha256((body or "").encode("utf-8")).hexdigest()


def extract_version(observation) -> str | None:
    parsed = parse_json(observation)

    if not parsed:
        return None

    value = parsed.get("version")
    return str(value) if value is not None else None


def describe_changes(
    endpoint: str,
    old_body: str | None,
    new_body: str | None,
) -> tuple[int, str, str, list[dict]]:
    changes = json_diff(old_body, new_body)

    endpoint_category = classify_endpoint(endpoint)

    if changes:
        classified = classify_changes(endpoint, changes)
        categories = summarize_categories(classified)

        print(f"           category={endpoint_category}")
        print(f"           changes={len(classified)}")
        print(f"           semantic={categories}")

        lines = []

        for change in classified[:20]:
            line = (
                f"{change['type']} {change['path']}: "
                f"{change['old']!r} -> {change['new']!r} "
                f"[{change['category']}]"
            )
            lines.append(line)
            print(f"           {line}")

        if len(classified) > 20:
            print(f"           ... {len(classified) - 20} more changes")

        # Use the strongest semantic category when there is one dominant
        # category; otherwise retain the endpoint-level category.
        semantic_category = (
            max(categories, key=categories.get)
            if categories
            else endpoint_category
        )

        return (
            len(classified),
            "; ".join(lines),
            semantic_category,
            classified,
        )

    print(f"           category={endpoint_category}")
    print("           body changed but no structured JSON diff")

    return (
        1,
        "Response body changed; no structured JSON diff available.",
        endpoint_category,
        [],
    )


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
                (
                    change_count,
                    change_summary,
                    change_category,
                    classified_changes,
                ) = describe_changes(
                    observation.name,
                    previous["body"],
                    observation.body,
                )

                if saved is None:
                    raise RuntimeError(
                        f"Expected a new snapshot for changed endpoint "
                        f"{observation.name}"
                    )

                impact_results = assess_changes(classified_changes)

                if impact_results:
                    severity = max(
                        (item["severity"] for item in impact_results),
                        key=lambda value: {
                            "low": 1,
                            "medium": 2,
                            "high": 3,
                            "critical": 4,
                        }.get(value, 0),
                    )

                    directions = {
                        item["direction"]
                        for item in impact_results
                        if item["direction"] != "neutral"
                    }

                    direction = (
                        next(iter(directions))
                        if len(directions) == 1
                        else "mixed"
                    )

                    research_priority = highest_priority(impact_results)
                else:
                    severity = "low"
                    direction = "neutral"
                    research_priority = "low"

                print(f"           severity={severity}")
                print(f"           direction={direction}")
                print(f"           research_priority={research_priority}")

                change_id = db.save_protocol_change(
                    endpoint=observation.name,
                    category=change_category,
                    previous_snapshot_id=int(previous["id"]),
                    current_snapshot_id=int(saved),
                    change_count=change_count,
                    summary=change_summary,
                    severity=severity,
                    direction=direction,
                    research_priority=research_priority,
                )

                print(f"           research_change_id={change_id}")

        print()
        print(f"changes_detected={changes_detected}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
