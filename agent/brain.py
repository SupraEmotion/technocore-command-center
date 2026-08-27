from __future__ import annotations

import sqlite3

from agent.db import connect
from agent.policy import evaluate_message
from agent.state import already_seen, record_event
from agent.contribution import evaluate_candidate
from agent.approval import create_pending


DB_PATH = "/opt/technocore-command-center/data/technocore.db"
OUR_DID = "did:key:z6Mkm5chQcHX2V4RbPHucxpzgpsyQMTdFgMpX7BtcXZaeU9e"


def get_messages(limit: int = 200) -> list[sqlite3.Row]:
    db = connect(DB_PATH)

    try:
        return db.execute(
            """
            SELECT room, seq, timestamp, did, text
            FROM messages
            WHERE did IS NOT NULL
            ORDER BY seq DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        db.close()


def analyse(limit: int = 200) -> dict[str, int]:
    stats = {
        "observed": 0,
        "ignored_self": 0,
        "already_seen": 0,
        "ignored": 0,
        "technical_observations": 0,
        "opportunities": 0,
    }

    messages = get_messages(limit)

    for message in reversed(messages):
        seq = int(message["seq"])
        did = message["did"]
        text = message["text"]

        if already_seen(seq):
            stats["already_seen"] += 1
            continue

        stats["observed"] += 1

        if did == OUR_DID:
            record_event(
                "observed",
                source_seq=seq,
                source_did=did,
                source_text=text,
                decision="ignore",
                score=0,
                reason="our_own_message",
            )
            stats["ignored_self"] += 1
            continue

        decision = evaluate_message(text)

        if decision.action == "opportunity":
            event_type = "opportunity"
            stats["opportunities"] += 1
            decision_value = "review"

            # Candidate generation is deliberately separated from
            # publication. This only evaluates and stores a candidate;
            # human approval is still required before publishing.
            candidate = evaluate_candidate(seq, text)

            if candidate is not None:
                candidate_id = candidate.candidate_id

                create_pending(candidate_id)

                record_event(
                    "candidate_created",
                    source_seq=seq,
                    source_did=did,
                    source_text=text,
                    decision="review",
                    score=candidate.score,
                    reason=candidate.reason,
                )

        elif decision.action == "observed":
            event_type = "technical_observation"
            stats["technical_observations"] += 1
            decision_value = "observe"

        else:
            event_type = "ignored"
            stats["ignored"] += 1
            decision_value = "ignore"

        record_event(
            event_type,
            source_seq=seq,
            source_did=did,
            source_text=text,
            decision=decision_value,
            score=decision.score,
            reason=decision.reason,
        )

    return stats


if __name__ == "__main__":
    stats = analyse()

    print("DRY RUN")
    print("=======")

    for key, value in stats.items():
        print(f"{key:22}: {value}")
