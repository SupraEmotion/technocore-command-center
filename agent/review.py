from __future__ import annotations

import sqlite3

from agent.db import connect
from agent.contribution import ContributionCandidate
from agent.evidence import Evidence
from agent.internal_evidence import collect_internal_evidence
from agent.quality import evaluate_quality


DB_PATH = "/opt/technocore-command-center/data/technocore.db"


def build_review_queue(limit: int = 20) -> list[dict]:
    db = connect(DB_PATH)

    try:
        rows = db.execute("""
            SELECT
                c.id,
                c.topic,
                c.source_seq,
                c.score,
                c.draft
            FROM agent_candidates c
            JOIN agent_approvals a
              ON a.candidate_id = c.id
            WHERE a.status IN ('pending', 'approved')
            ORDER BY c.id DESC
            LIMIT ?
        """, (limit,)).fetchall()
    finally:
        db.close()

    internal = collect_internal_evidence()
    queue: list[dict] = []

    for row in rows:

        support = next(
            (
                item for item in internal
                if item.topic == row["topic"]
            ),
            None,
        )

        if support is None:
            continue

        # Reconstruct the external evidence from the original source
        # message without running novelty again.
        db = connect(DB_PATH)

        source = db.execute("""
            SELECT seq, text
            FROM messages
            WHERE seq = ?
        """, (row["source_seq"],)).fetchone()

        db.close()

        if source is None:
            continue

        # The stored candidate already passed novelty when it was created.
        # Review must not call evaluate_candidate(), because that would
        # run novelty again and turn the candidate into a duplicate.
        external = Evidence(
            topic=row["topic"],
            fingerprint="stored",
            source_type="external_network_observation",
            supporting_messages=1,
            latest_seq=row["source_seq"],
            confidence=0.25,
            summary="Stored external observation.",
        )

        candidate = ContributionCandidate(
            candidate_id=int(row["id"]),
            source_seq=row["source_seq"],
            topic=row["topic"],
            score=float(row["score"]),
            reason="stored_candidate",
            draft=row["draft"],
            external_evidence=external,
            internal_evidence=support,
        )

        quality = evaluate_quality(candidate)

        if not quality.publishable:
            continue

        queue.append({
            "candidate_id": row["id"],
            "seq": candidate.source_seq,
            "topic": candidate.topic,
            "score": quality.score,
            "quality_reasons": quality.reasons,
            "draft": candidate.draft,
            "external_evidence": {
                "source_type":
                    candidate.external_evidence.source_type,
                "supporting_messages":
                    candidate.external_evidence.supporting_messages,
                "confidence":
                    candidate.external_evidence.confidence,
            },
            "internal_evidence": {
                "topic":
                    candidate.internal_evidence.topic,
                "confidence":
                    candidate.internal_evidence.confidence,
                "facts":
                    candidate.internal_evidence.facts,
            },
        })

    return queue


if __name__ == "__main__":
    queue = build_review_queue()

    print("TECHNOCORE CONTRIBUTION REVIEW")
    print("==============================")
    print("APPROVAL REQUIRED: YES")
    print()

    if not queue:
        print("No publishable candidates.")
        raise SystemExit(0)

    for index, item in enumerate(queue, 1):
        print(f"--- CANDIDATE {index} ---")
        print("ID:", item["candidate_id"])
        print("SEQ:", item["seq"])
        print("TOPIC:", item["topic"])
        print("QUALITY:", item["score"])
        print("REASONS:", ", ".join(item["quality_reasons"]))
        print("EXTERNAL:", item["external_evidence"])
        print("INTERNAL:", item["internal_evidence"])
        print("DRAFT:")
        print(item["draft"])
        print()
