from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str
    score: float


PRESENCE_PATTERNS = (
    r"^agent node reporting in",
    r"^agent heartbeat",
    r"^continuous participation",
    r"^autonomous agent operational",
    r"^technocore protocol engagement active",
    r"^signed and present",
    r"^did identity active",
    r"^node online",
    r"^agentic infrastructure running",
)

PROMOTION_PATTERNS = (
    r"^i published a technocore contribution",
    r"^i published a .*thread",
    r"^i made a .*thread",
    r"^here'?s my .*thread",
    r"^check out my .*thread",
    r"^public contribution",
    r"^public contribution from",
    r"^made something for anyone",
    r"^shared .* to help .*discover technocore",
)

ACK_PATTERNS = (
    r"^peering ack",
    r"^@[\w-]+ confirmed your signal",
    r"^reply to [\w-]+:",
)

GENERIC_TEST_PATTERNS = (
    r"^technocore participation: this did is testing",
    r"^completed a coordination step",
    r"^contributed a task result",
)


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def matches(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def classify(text: str) -> Decision:
    value = normalize(text)

    if not value:
        return Decision("ignored", "empty_message", 0.0)

    if matches(value, PRESENCE_PATTERNS):
        return Decision("ignored", "presence_message", 0.0)

    if matches(value, PROMOTION_PATTERNS):
        return Decision("ignored", "promotion_or_contribution_announcement", 0.0)

    if matches(value, ACK_PATTERNS):
        return Decision("ignored", "coordination_or_peering_ack", 0.0)

    if matches(value, GENERIC_TEST_PATTERNS):
        return Decision("ignored", "generic_activity_report", 0.0)

    # A real engagement question must:
    #   1. contain a question mark outside a URL,
    #   2. begin with an actual interrogative construction,
    #   3. contain Technocore-relevant technical context.

    url_pattern = re.compile(r"https?://[^\s]+")
    without_urls = url_pattern.sub("", value).strip()

    technical_question_terms = (
        "technocore",
        "did",
        "signature",
        "signed",
        "nonce",
        "sequence",
        "protocol",
        "api",
        "http",
        "verify",
        "verification",
        "proof",
        "message",
        "room",
        "kv",
        "collector",
        "agent",
    )

    question_starts = (
        r"^what\b",
        r"^why\b",
        r"^how\b",
        r"^where\b",
        r"^when\b",
        r"^which\b",
        r"^who\b",
        r"^can\s+(someone|anyone|you)\b",
        r"^could\s+(someone|anyone|you)\b",
        r"^would\s+(someone|anyone|you)\b",
        r"^does\b",
        r"^do\b",
        r"^is\b",
        r"^are\b",
        r"^should\b",
    )

    has_question_mark = "?" in without_urls

    has_question_start = any(
        re.search(pattern, without_urls)
        for pattern in question_starts
    )

    # Real conversations often contain context before the actual
    # technical question, so interrogative detection must not require
    # the whole message to start with "what/how/why/etc.".
    question_clauses = re.split(r"[.!;\n]+|\s+[-—]\s+", without_urls)

    has_embedded_question = any(
        "?" in clause
        and any(
            re.search(pattern, clause.strip())
            for pattern in question_starts
        )
        for clause in question_clauses
    )

    has_technical_context = any(
        re.search(rf"\b{re.escape(term)}\b", without_urls)
        for term in technical_question_terms
    )

    if (
        has_question_mark
        and (has_question_start or has_embedded_question)
        and has_technical_context
    ):
        return Decision(
            "opportunity",
            "direct_technical_question",
            1.0,
        )

    # Concrete technical observations are worth recording,
    # but are NOT automatically engagement opportunities.
    technical_terms = (
        "protocol",
        "signed",
        "signature",
        "nonce",
        "sequence",
        "did",
        "http",
        "timeout",
        "reliability",
        "api",
        "verification",
        "proof",
    )

    technical = sum(term in value for term in technical_terms)

    if technical >= 1 and len(value) >= 70:
        return Decision(
            "observed",
            "substantive_technical_observation",
            0.5,
        )

    return Decision(
        "ignored",
        "no_clear_engagement_opportunity",
        0.0,
    )


# Backwards-compatible entry point for the existing dry-run brain.
def evaluate_message(text: str) -> Decision:
    return classify(text)
