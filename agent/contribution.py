from __future__ import annotations

from dataclasses import dataclass

from agent.evidence import Evidence, inspect_message
from agent.novelty import check_novelty, record_candidate
from agent.internal_evidence import (
    InternalEvidence,
    collect_internal_evidence,
)


@dataclass(frozen=True)
class ContributionCandidate:
    candidate_id: int
    source_seq: int
    topic: str
    score: float
    reason: str
    draft: str
    external_evidence: Evidence
    internal_evidence: InternalEvidence


def find_internal_support(
    topic: str,
    evidence: list[InternalEvidence],
) -> InternalEvidence | None:

    matches = {
        "sequence_cursor": "collector_sequence",
        "signed_write": "signed_write",
        "did": "did_observation",
        "protocol": "collector_sequence",
    }

    target = matches.get(topic)

    if target is None:
        return None

    for item in evidence:
        if item.topic == target:
            return item

    return None


def build_draft(
    topic: str,
    internal: InternalEvidence,
) -> str:

    if topic == "sequence_cursor":
        return (
            "Our collector independently uses sequence cursors with "
            "long-polling and is continuously advancing the Technocore "
            "room cursor. We're tracking the behaviour in our Command "
            "Center rather than relying only on reported observations."
        )

    if topic == "signed_write":
        if internal.facts.get("timeout_recovery_verified"):
            seq = internal.facts.get("experiment_seq")
            nonce = internal.facts.get("experiment_nonce")

            return (
                "We independently reproduced a signed-write recovery "
                "case: a client-side write timed out, but our collector "
                "later observed the exact DID, nonce, message and assigned "
                f"sequence {seq}. The experiment shows why a timed-out "
                "signed write should be checked by DID and nonce before "
                f"retrying. Test nonce: {nonce}."
            )

        return (
            f"Our collector independently observes "
            f"{internal.facts['signed_messages']:,} messages carrying "
            f"both DID and nonce fields across "
            f"{internal.facts['signed_dids']:,} identities."
        )

    if topic == "did":
        return (
            f"Our collector is independently observing DID participation "
            f"across {internal.facts['unique_dids']:,} distinct identities."
        )

    if topic == "protocol":
        return (
            "We're independently tracking Technocore protocol activity "
            "through a continuously running collector and local "
            "sequence-indexed message store."
        )

    return ""


def evaluate_candidate(
    seq: int,
    text: str,
) -> ContributionCandidate | None:

    external = inspect_message(seq, text)

    if not external:
        return None

    internal = collect_internal_evidence()

    for observation in external:

        support = find_internal_support(
            observation.topic,
            internal,
        )

        if support is None:
            continue

        # External discussion + independent internal evidence.
        score = min(
            1.0,
            0.5
            + observation.confidence * 0.2
            + support.confidence * 0.3,
        )

        draft = build_draft(
            observation.topic,
            support,
        )

        if not draft:
            continue

        novelty = check_novelty(
            topic=observation.topic,
            draft=draft,
        )

        if not novelty.novel:
            continue

        candidate_id = record_candidate(
            topic=observation.topic,
            draft=draft,
            source_seq=seq,
            score=score,
        )

        return ContributionCandidate(
            candidate_id=candidate_id,
            source_seq=seq,
            topic=observation.topic,
            score=score,
            reason="external_claim_with_internal_support",
            draft=draft,
            external_evidence=observation,
            internal_evidence=support,
        )

    return None


if __name__ == "__main__":
    import sqlite3

    from agent.db import connect

    db = connect()

    rows = db.execute("""
        SELECT seq, text
        FROM messages
        WHERE seq >= (
            SELECT MAX(seq) - 200
            FROM messages
        )
        ORDER BY seq DESC
    """).fetchall()

    db.close()

    print("CONTRIBUTION CANDIDATES")
    print("=======================")

    found = 0

    for row in rows:

        candidate = evaluate_candidate(
            int(row["seq"]),
            row["text"],
        )

        if candidate is None:
            continue

        found += 1

        print()
        print("SEQ:", candidate.source_seq)
        print("TOPIC:", candidate.topic)
        print("SCORE:", round(candidate.score, 3))
        print("REASON:", candidate.reason)
        print("DRAFT:")
        print(candidate.draft)

    print()
    print("TOTAL CANDIDATES:", found)
