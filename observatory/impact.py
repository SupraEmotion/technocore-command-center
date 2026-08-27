"""Assess the research impact of semantic Technocore changes."""

from __future__ import annotations

from typing import Any


SEVERITY_ORDER = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    return None


def assess_change(
    category: str,
    change: dict[str, Any],
) -> dict[str, str]:
    """Return conservative impact metadata for one classified change."""

    old = change.get("old")
    new = change.get("new")
    change_type = str(change.get("type", ""))

    severity = "low"
    direction = "neutral"
    priority = "low"

    if category == "authentication_changed":
        severity = "critical"
        priority = "critical"

    elif category == "identity_changed":
        severity = "high"
        priority = "high"

    elif category == "participation_changed":
        severity = "high"
        priority = "high"

    elif category == "capability_removed":
        severity = "high"
        priority = "high"

    elif category == "capability_added":
        severity = "medium"
        priority = "medium"

    elif category == "api_changed":
        severity = "medium"
        priority = "medium"

    elif category == "compute_changed":
        severity = "high"
        priority = "high"

    elif category == "interop_changed":
        severity = "medium"
        priority = "medium"

    elif category == "limit_changed":
        severity = "medium"
        priority = "medium"

        old_num = _number(old)
        new_num = _number(new)

        if old_num is not None and new_num is not None:
            if new_num > old_num:
                direction = "expanded"
            elif new_num < old_num:
                direction = "restricted"

            # Restrictive operational changes deserve extra research
            # attention because they can directly affect participation.
            if direction == "restricted":
                priority = "high"

    elif category == "documentation_changed":
        severity = "low"
        priority = "low"

    if change_type == "removed":
        direction = "removed"

    elif change_type == "added" and direction == "neutral":
        direction = "added"

    return {
        "severity": severity,
        "direction": direction,
        "research_priority": priority,
    }


def assess_changes(
    classified_changes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach impact metadata to classified changes."""

    result = []

    for change in classified_changes:
        category = str(change["category"])
        impact = assess_change(category, change)

        result.append({
            **change,
            **impact,
        })

    return result


def highest_priority(
    changes: list[dict[str, Any]],
) -> str:
    """Return the highest research priority present."""

    if not changes:
        return "low"

    return max(
        (
            str(change.get("research_priority", "low"))
            for change in changes
        ),
        key=lambda value: SEVERITY_ORDER.get(value, 0),
    )
