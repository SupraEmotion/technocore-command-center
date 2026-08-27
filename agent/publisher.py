from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from agent.approval import get as get_approval, mark_published
from agent.state import DB_PATH, record_event

from sys import path as sys_path

DID_STARTER = Path("/opt/technocore-did-starter")

if str(DID_STARTER) not in sys_path:
    sys_path.insert(0, str(DID_STARTER))

from technocore_agent import (  # noqa: E402
    NetworkError,
    did_from_private_key,
    load_identity,
    post_signed_message,
    next_nonce,
)


ROOM = "technocore"
KEY_PATH = DID_STARTER / "identity.pem"


def get_candidate(candidate_id: int) -> sqlite3.Row:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    try:
        row = db.execute(
            """
            SELECT
                id,
                topic,
                source_seq,
                draft,
                score
            FROM agent_candidates
            WHERE id = ?
            """,
            (candidate_id,),
        ).fetchone()

        if row is None:
            raise ValueError(
                f"candidate {candidate_id} does not exist"
            )

        return row

    finally:
        db.close()


def find_committed_write(
    did: str,
    nonce: str,
    expected_text: str,
) -> sqlite3.Row | None:
    """
    Look for an uncertain write already observed by our collector.

    Matching requires DID + nonce + exact text.
    """
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    try:
        return db.execute(
            """
            SELECT
                room,
                seq,
                timestamp,
                did,
                nonce,
                text
            FROM messages
            WHERE did = ?
              AND nonce = ?
              AND text = ?
            ORDER BY seq DESC
            LIMIT 1
            """,
            (did, nonce, expected_text),
        ).fetchone()

    finally:
        db.close()


def wait_for_committed_write(
    did: str,
    nonce: str,
    expected_text: str,
    *,
    timeout: float = 10.0,
    interval: float = 0.5,
) -> sqlite3.Row | None:
    """
    Poll the local collector for a bounded period.

    Matching requires DID + nonce + exact text.
    Never retries the network write.
    """
    deadline = time.monotonic() + timeout

    while True:
        committed = find_committed_write(
            did,
            nonce,
            expected_text,
        )

        if committed is not None:
            return committed

        remaining = deadline - time.monotonic()

        if remaining <= 0:
            return None

        time.sleep(min(interval, remaining))


def publish(candidate_id: int) -> None:
    candidate = get_candidate(candidate_id)
    approval = get_approval(candidate_id)

    if approval is None:
        raise ValueError(
            f"candidate {candidate_id} has no approval record"
        )

    if approval.status == "published":
        raise ValueError(
            f"candidate {candidate_id} is already published; "
            "refusing to POST again"
        )

    if approval.status != "approved":
        raise ValueError(
            f"candidate {candidate_id} is not approved "
            f"(status={approval.status})"
        )

    text = candidate["draft"]

    key = load_identity(
        KEY_PATH,
        allow_prompt=True,
    )

    did = did_from_private_key(key)
    nonce = next_nonce()

    print("PUBLISHING APPROVED CONTRIBUTION")
    print("================================")
    print("CANDIDATE:", candidate_id)
    print("TOPIC:", candidate["topic"])
    print("DID:", did)
    print("NONCE:", nonce)
    print("TEXT:")
    print(text)
    print()

    record_event(
        "publish_started",
        source_seq=candidate["source_seq"],
        source_did=did,
        source_text=text,
        decision="approved",
        score=candidate["score"],
        reason="explicit_human_approval",
    )

    try:
        response = post_signed_message(
            key,
            ROOM,
            text,
            nonce=nonce,
        )

    except NetworkError as error:
        message = str(error)

        print("WRITE ERROR:")
        print(message)
        print()

        if "write timed out" in message.lower():
            print("WRITE OUTCOME: UNKNOWN")
            print("Checking collector for committed write...")

            # The publisher owns the nonce, so the uncertain write
            # can be recovered deterministically using DID + nonce.
            committed = wait_for_committed_write(
                did,
                nonce,
                text,
                timeout=10.0,
                interval=0.5,
            )

            if committed is not None:
                print("TIMEOUT BUT COMMIT CONFIRMED")
                print("SEQ:", committed["seq"])

                approval = mark_published(candidate_id)

                record_event(
                    "publish_uncertain",
                    source_seq=candidate["source_seq"],
                    source_did=did,
                    source_text=text,
                    decision="unknown",
                    score=candidate["score"],
                    reason=message,
                )

            if committed is not None:
                return

            raise RuntimeError(
                "write timed out; collector has not confirmed the "
                "commit; automatic retry is forbidden"
            ) from error

        record_event(
            "publish_failed",
            source_seq=candidate["source_seq"],
            source_did=did,
            source_text=text,
            decision="failed",
            score=candidate["score"],
            reason=message,
        )

        raise

    posted = response.get("posted")

    if not isinstance(posted, dict):
        raise RuntimeError(
            "publisher received no posted record"
        )

    posted_did = posted.get("from")
    posted_text = posted.get("text")
    posted_nonce = posted.get("nonce")
    posted_seq = posted.get("seq")

    if posted_did != did:
        raise RuntimeError(
            "publisher DID verification failed"
        )

    if posted_text != text:
        raise RuntimeError(
            "publisher text verification failed"
        )

    if posted_nonce is None:
        raise RuntimeError(
            "publisher response contained no nonce"
        )

    if not isinstance(posted_seq, int) or posted_seq <= 0:
        raise RuntimeError(
            "publisher response contained an invalid sequence"
        )

    # Verify independently against our collector.
    # The collector may legitimately lag behind the POST response,
    # so wait for catch-up instead of immediately declaring uncertainty.
    committed = wait_for_committed_write(
        did,
        str(posted_nonce),
        text,
        timeout=10.0,
        interval=0.5,
    )

    if committed is None:
        record_event(
            "publish_uncertain",
            source_seq=candidate["source_seq"],
            source_did=did,
            source_text=text,
            decision="response_ok_collector_pending",
            score=candidate["score"],
            reason=(
                f"POST returned seq {posted_seq}, but collector did not "
                "observe the exact record within 10 seconds"
            ),
        )

        raise RuntimeError(
            "POST succeeded but collector did not confirm the record "
            "within the verification window"
        )

    if committed["seq"] != posted_seq:
        raise RuntimeError(
            "collector sequence does not match POST response"
        )

    approval = mark_published(candidate_id)

    record_event(
        "published",
        source_seq=posted_seq,
        source_did=did,
        source_text=text,
        decision="published",
        score=candidate["score"],
        reason="human_approved_and_collector_verified",
    )

    print("PUBLISHED")
    print("=========")
    print("CANDIDATE:", candidate_id)
    print("SEQ:", posted_seq)
    print("DID:", did)
    print("NONCE:", posted_nonce)
    print("STATUS:", approval.status)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Publish an approved Technocore contribution."
    )

    parser.add_argument(
        "candidate_id",
        type=int,
    )

    args = parser.parse_args()

    publish(args.candidate_id)
