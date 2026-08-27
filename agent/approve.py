from __future__ import annotations

import sqlite3
import sys

from agent.db import connect
from agent.approval import decide
from agent.db import DB_PATH


def show_candidate(candidate_id: int) -> sqlite3.Row:
    db = connect(DB_PATH)

    try:
        row = db.execute(
            """
            SELECT
                id,
                topic,
                source_seq,
                score,
                draft
            FROM agent_candidates
            WHERE id = ?
            """,
            (candidate_id,),
        ).fetchone()

        if row is None:
            raise SystemExit(
                f"Candidate {candidate_id} does not exist."
            )

        return row

    finally:
        db.close()


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m agent.approve <candidate_id>")
        return 2

    try:
        candidate_id = int(sys.argv[1])
    except ValueError:
        print("Candidate ID must be an integer.")
        return 2

    candidate = show_candidate(candidate_id)

    print()
    print("TECHNOCORE CONTRIBUTION APPROVAL")
    print("================================")
    print("CANDIDATE:", candidate["id"])
    print("TOPIC:", candidate["topic"])
    print("SOURCE SEQ:", candidate["source_seq"])
    print("QUALITY SCORE:", candidate["score"])
    print()
    print("DRAFT:")
    print(candidate["draft"])
    print()

    answer = input(
        "Type APPROVE to approve this candidate: "
    ).strip()

    if answer != "APPROVE":
        print()
        print("NOT APPROVED.")
        return 0

    approval = decide(
        candidate_id,
        "approved",
        decided_by="human",
        reason="Explicit human approval.",
    )

    print()
    print("APPROVED")
    print("========")
    print("CANDIDATE:", approval.candidate_id)
    print("STATUS:", approval.status)
    print("DECIDED BY:", approval.decided_by)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
