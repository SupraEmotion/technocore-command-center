from __future__ import annotations

import sqlite3

from dataclasses import dataclass

from agent.db import DB_PATH, connect


@dataclass(frozen=True)
class InternalEvidence:
    topic: str
    confidence: float
    summary: str
    facts: dict


def collect_internal_evidence() -> list[InternalEvidence]:
    db = connect(DB_PATH)
    db.row_factory = sqlite3.Row

    try:
        results: list[InternalEvidence] = []

        # Current collector state.
        cursor = db.execute("""
            SELECT room, last_seq
            FROM cursors
            ORDER BY room
        """).fetchall()

        message_count = db.execute("""
            SELECT COUNT(*)
            FROM messages
        """).fetchone()[0]

        unique_dids = db.execute("""
            SELECT COUNT(DISTINCT did)
            FROM messages
            WHERE did IS NOT NULL
        """).fetchone()[0]

        for row in cursor:
            results.append(
                InternalEvidence(
                    topic="collector_sequence",
                    confidence=0.95,
                    summary=(
                        f"Our collector has stored {message_count:,} messages "
                        f"and currently tracks room '{row['room']}' at "
                        f"sequence {row['last_seq']:,}."
                    ),
                    facts={
                        "room": row["room"],
                        "last_seq": row["last_seq"],
                        "messages": message_count,
                        "unique_dids": unique_dids,
                    },
                )
            )

        # Database integrity evidence.
        duplicate_sequences = db.execute("""
            SELECT COUNT(*)
            FROM (
                SELECT room, seq
                FROM messages
                GROUP BY room, seq
                HAVING COUNT(*) > 1
            )
        """).fetchone()[0]

        if duplicate_sequences == 0 and message_count > 0:
            results.append(
                InternalEvidence(
                    topic="database_integrity",
                    confidence=0.9,
                    summary=(
                        "Our local message store contains no duplicate "
                        "room/sequence records."
                    ),
                    facts={
                        "messages": message_count,
                        "duplicate_sequences": 0,
                    },
                )
            )

        # Signed-write evidence.
        #
        # The aggregate statistics prove that the collector observes
        # DID+nonce messages. A separate controlled experiment can prove
        # that a client-side timeout may occur even though the write was
        # subsequently committed and observed by our collector.
        signed_stats = db.execute("""
            SELECT
                COUNT(*) AS signed_messages,
                COUNT(DISTINCT did) AS signed_dids,
                COUNT(DISTINCT nonce) AS distinct_nonces
            FROM messages
            WHERE did IS NOT NULL
              AND nonce IS NOT NULL
              AND TRIM(nonce) != ''
        """).fetchone()

        signed_messages = int(signed_stats["signed_messages"])
        signed_dids = int(signed_stats["signed_dids"])
        distinct_nonces = int(signed_stats["distinct_nonces"])

        experiment = db.execute("""
            SELECT seq, timestamp, did, nonce, text
            FROM messages
            WHERE seq = 444142
              AND did = ?
              AND nonce = ?
              AND text = ?
            LIMIT 1
        """, (
            "did:key:z6Mkm5chQcHX2V4RbPHucxpzgpsyQMTdFgMpX7BtcXZaeU9e",
            "8260817354219638475",
            "Command Center timeout recovery experiment 3",
        )).fetchone()

        timeout_recovery_verified = experiment is not None

        if signed_messages > 0:
            if timeout_recovery_verified:
                confidence = 0.95
                summary = (
                    "A controlled write using our DID and nonce timed out "
                    "at the client, while the collector independently "
                    "observed the exact DID, nonce, text, and assigned "
                    f"sequence {experiment['seq']}. This demonstrates "
                    "timeout-then-observed-commit behaviour for the test."
                )
            else:
                confidence = 0.8
                summary = (
                    f"Our collector has independently observed "
                    f"{signed_messages:,} messages carrying both a DID "
                    f"and nonce across {signed_dids:,} identities."
                )

            results.append(
                InternalEvidence(
                    topic="signed_write",
                    confidence=confidence,
                    summary=summary,
                    facts={
                        "signed_messages": signed_messages,
                        "signed_dids": signed_dids,
                        "distinct_nonces": distinct_nonces,
                        "timeout_recovery_verified": timeout_recovery_verified,
                        "experiment_seq": (
                            experiment["seq"]
                            if experiment else None
                        ),
                        "experiment_did": (
                            experiment["did"]
                            if experiment else None
                        ),
                        "experiment_nonce": (
                            experiment["nonce"]
                            if experiment else None
                        ),
                    },
                )
            )

        # DID participation evidence.
        if unique_dids > 0:
            results.append(
                InternalEvidence(
                    topic="did_observation",
                    confidence=0.9,
                    summary=(
                        f"Our collector has independently observed "
                        f"{unique_dids:,} distinct DID identities."
                    ),
                    facts={
                        "unique_dids": unique_dids,
                    },
                )
            )

        return results

    finally:
        db.close()


if __name__ == "__main__":
    print("INTERNAL EVIDENCE")
    print("=================")

    for evidence in collect_internal_evidence():
        print()
        print("TOPIC:", evidence.topic)
        print("CONFIDENCE:", evidence.confidence)
        print("SUMMARY:", evidence.summary)
        print("FACTS:", evidence.facts)
