"""Compare stored Technocore protocol snapshots."""

from __future__ import annotations

import json
from typing import Any


def _flatten(
    value: Any,
    prefix: str = "",
) -> dict[str, Any]:
    result: dict[str, Any] = {}

    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            result.update(_flatten(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            path = f"{prefix}[{index}]"
            result.update(_flatten(child, path))
    else:
        result[prefix] = value

    return result


def json_diff(
    old_body: str | None,
    new_body: str | None,
) -> list[dict[str, Any]]:
    if not old_body or not new_body:
        return []

    try:
        old = json.loads(old_body)
        new = json.loads(new_body)
    except json.JSONDecodeError:
        return []

    old_flat = _flatten(old)
    new_flat = _flatten(new)

    changes: list[dict[str, Any]] = []

    for key in sorted(set(old_flat) | set(new_flat)):
        if key not in old_flat:
            changes.append({
                "type": "added",
                "path": key,
                "old": None,
                "new": new_flat[key],
            })
        elif key not in new_flat:
            changes.append({
                "type": "removed",
                "path": key,
                "old": old_flat[key],
                "new": None,
            })
        elif old_flat[key] != new_flat[key]:
            changes.append({
                "type": "changed",
                "path": key,
                "old": old_flat[key],
                "new": new_flat[key],
            })

    return changes


def classify_endpoint(endpoint: str) -> str:
    if endpoint in {"config", "agent_manifest", "openapi"}:
        return "protocol"

    if endpoint in {"skill", "patterns", "interop"}:
        return "documentation"

    return "unknown"
