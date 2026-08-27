from __future__ import annotations

import re
from dataclasses import dataclass

from agent.contribution import ContributionCandidate


@dataclass(frozen=True)
class QualityDecision:
    publishable: bool
    score: float
    reasons: tuple[str, ...]


PROMOTION_PATTERNS = (
    r"\bi published\b",
    r"\bcheck out\b",
    r"\bmy thread\b",
    r"\bfollow me\b",
    r"\bdiscover technocore\b",
    r"\bshare(d)?\b",
)

VAGUE_PATTERNS = (
    r"\btracking activity\b",
    r"\bparticipation\b",
    r"\bagentic infrastructure\b",
    r"\bprotocol activity\b",
)

USEFUL_TERMS = (
    "sequence",
    "cursor",
    "long-poll",
    "nonce",
    "signature",
    "signed",
    "verification",
    "timeout",
    "reliability",
    "did",
    "proof",
    "api",
    "protocol",
)


def evaluate_quality(
    candidate: ContributionCandidate,
) -> QualityDecision:

    text = candidate.draft.lower()

    score = 0.0
    reasons: list[str] = []

    # Strong independent evidence.
    if candidate.internal_evidence.confidence >= 0.9:
        score += 0.30
        reasons.append("strong_internal_evidence")
    elif candidate.internal_evidence.confidence >= 0.75:
        score += 0.20
        reasons.append("moderate_internal_evidence")
    else:
        reasons.append("weak_internal_evidence")

    # External evidence must exist and have reasonable confidence.
    if candidate.external_evidence.confidence >= 0.75:
        score += 0.20
        reasons.append("strong_external_support")
    elif candidate.external_evidence.confidence >= 0.50:
        score += 0.10
        reasons.append("moderate_external_support")
    else:
        reasons.append("weak_external_support")

    # Candidate's own evidence-backed score.
    if candidate.score >= 0.80:
        score += 0.15
        reasons.append("high_evidence_score")
    elif candidate.score >= 0.65:
        score += 0.10
        reasons.append("acceptable_evidence_score")

    # Concrete technical language.
    useful_hits = sum(
        1 for term in USEFUL_TERMS
        if term in text
    )

    if useful_hits >= 2:
        score += 0.15
        reasons.append("specific_technical_content")
    elif useful_hits == 1:
        score += 0.05
        reasons.append("limited_technical_content")
    else:
        reasons.append("no_specific_technical_content")

    # Reproducibility signals.
    reproducibility_terms = (
        "observed",
        "collector",
        "independently",
        "sequence",
        "verified",
        "measured",
        "evidence",
    )

    reproducibility_hits = sum(
        1 for term in reproducibility_terms
        if term in text
    )

    if reproducibility_hits >= 2:
        score += 0.10
        reasons.append("reproducible_observation")

    # Penalise generic status reporting.
    if any(re.search(pattern, text) for pattern in VAGUE_PATTERNS):
        score -= 0.15
        reasons.append("too_generic")

    # Penalise promotional language.
    if any(re.search(pattern, text) for pattern in PROMOTION_PATTERNS):
        score -= 0.30
        reasons.append("promotional_language")

    # Very short drafts are unlikely to contain useful evidence.
    if len(text) < 90:
        score -= 0.10
        reasons.append("too_short")

    score = max(0.0, min(1.0, score))

    # Conservative publishing threshold.
    publishable = (
        score >= 0.70
        and "promotional_language" not in reasons
        and "too_generic" not in reasons
        and candidate.internal_evidence.confidence >= 0.75
    )

    return QualityDecision(
        publishable=publishable,
        score=round(score, 3),
        reasons=tuple(reasons),
    )
