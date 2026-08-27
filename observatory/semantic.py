"""Classify low-level protocol diffs into research-relevant changes."""

from __future__ import annotations

from typing import Any


def _path_lower(change: dict[str, Any]) -> str:
    return str(change.get("path", "")).lower()


def classify_change(
    endpoint: str,
    change: dict[str, Any],
) -> str:
    path = _path_lower(change)

    # Identity / cryptographic rules.
    if any(term in path for term in (
        "did",
        "identity",
        "signature",
        "signing",
        "nonce",
        "ed25519",
        "public_key",
    )):
        return "identity_changed"

    # Authentication / authorization.
    if any(term in path for term in (
        "auth",
        "permission",
        "authorization",
        "credential",
        "token",
    )):
        return "authentication_changed"

    # Operational limits.
    if any(term in path for term in (
        "limit",
        "rate",
        "per_minute",
        "per_day",
        "max_",
        "ttl",
        "retention",
        "timeout",
    )):
        return "limit_changed"

    # API surface.
    if endpoint == "openapi" or any(term in path for term in (
        "endpoint",
        "paths",
        "operations",
        "capabilities",
    )):
        if change.get("type") == "added":
            return "capability_added"
        if change.get("type") == "removed":
            return "capability_removed"
        return "api_changed"

    # Room / participation model.
    if any(term in path for term in (
        "room",
        "mailbox",
        "ephemeral",
        "ownership",
        "write",
        "read",
    )):
        return "participation_changed"

    # Inference / compute.
    if any(term in path for term in (
        "inference",
        "compute",
        "gpu",
        "model",
        "execution",
    )):
        return "compute_changed"

    # Interoperability.
    if endpoint == "interop" or any(term in path for term in (
        "interop",
        "matrix",
        "activitypub",
        "websub",
        "mcp",
        "a2a",
    )):
        return "interop_changed"

    # Documentation-only changes.
    if endpoint in {"skill", "patterns"}:
        return "documentation_changed"

    return "protocol_changed"


def classify_changes(
    endpoint: str,
    changes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return diffs enriched with semantic categories."""

    return [
        {
            **change,
            "category": classify_change(endpoint, change),
        }
        for change in changes
    ]


def summarize_categories(
    classified: list[dict[str, Any]],
) -> dict[str, int]:
    result: dict[str, int] = {}

    for change in classified:
        category = str(change["category"])
        result[category] = result.get(category, 0) + 1

    return dict(sorted(result.items()))
