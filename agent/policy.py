from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Decision:
    publish: bool
    reason: str
    score: float


HEARTBEAT_PATTERNS = (
    r"\bheartbeat\b",
    r"\bpresence confirmed\b",
    r"\bagent (?:is )?online\b",
    r"\bagentic infrastructure running\b",
    r"\bsigned and present\b",
)

GENERIC_PATTERNS = (
    r"^technocore protocol engagement active\.?$",
    r"^autonomous agent operational on technocore\.?$",
    r"^continuous participation\.?$",
)


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def is_low_information(text: str) -> bool:
    value = normalize(text)

    if any(re.search(pattern, value) for pattern in HEARTBEAT_PATTERNS):
        return True

    if any(re.search(pattern, value) for pattern in GENERIC_PATTERNS):
        return True

    return len(value) < 24


def evaluate_message(text: str) -> Decision:
    value = normalize(text)

    if is_low_information(value):
        return Decision(
            publish=False,
            reason="low_information_or_presence_message",
            score=0.0,
        )

    score = 0.5

    if "?" in value:
        score += 0.2

    technical_terms = (
        "protocol",
        "did",
        "nonce",
        "signature",
        "signed",
        "sequence",
        "api",
        "http",
        "agent",
        "network",
        "contribution",
        "proof",
    )

    if any(term in value for term in technical_terms):
        score += 0.2

    if len(value) >= 80:
        score += 0.1

    return Decision(
        publish=True,
        reason="potentially_useful_technical_activity",
        score=min(score, 1.0),
    )
