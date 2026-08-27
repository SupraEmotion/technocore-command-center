import sqlite3

import agent.review as review
from agent.contribution import ContributionCandidate
from agent.evidence import Evidence
from agent.internal_evidence import InternalEvidence
from agent.quality import evaluate_quality


def candidate(
    *,
    draft,
    external_confidence,
    internal_confidence,
    score=0.9,
):
    return ContributionCandidate(
        candidate_id=1,
        source_seq=100,
        topic="signed_write",
        score=score,
        reason="test_candidate",
        draft=draft,
        external_evidence=Evidence(
            topic="signed_write",
            fingerprint="test",
            source_type="external_network_observation",
            supporting_messages=2,
            latest_seq=100,
            confidence=external_confidence,
            summary="External test evidence.",
        ),
        internal_evidence=InternalEvidence(
            topic="signed_write",
            confidence=internal_confidence,
            summary="Independent internal verification of the test observation.",
            facts={
                "verified": True,
                "sequence": 100,
                "signature": "test",
            },
        ),
    )


def test_weak_candidate_is_not_publishable():
    result = evaluate_quality(
        candidate(
            draft="A generic protocol update.",
            external_confidence=0.25,
            internal_confidence=0.50,
            score=0.40,
        )
    )

    assert result.publishable is False
    assert result.score < 0.70


def test_strong_candidate_is_publishable():
    result = evaluate_quality(
        candidate(
            draft=(
                "Collector independently verified a signed write "
                "with sequence and nonce evidence. "
                "The observation was measured and verified "
                "against the protocol API."
            ),
            external_confidence=0.75,
            internal_confidence=0.90,
            score=0.90,
        )
    )

    assert result.publishable is True
    assert result.score >= 0.70


def test_promotional_candidate_is_rejected():
    result = evaluate_quality(
        candidate(
            draft=(
                "I published my thread about this verified "
                "protocol observation. Check out my thread."
            ),
            external_confidence=0.90,
            internal_confidence=0.90,
            score=0.95,
        )
    )

    assert result.publishable is False
    assert "promotional_language" in result.reasons


def test_review_queue_requires_quality_gate(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"

    monkeypatch.setattr(review, "DB_PATH", db_path)

    db = sqlite3.connect(db_path)

    db.execute("""
        CREATE TABLE agent_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            source_seq INTEGER NOT NULL,
            score REAL NOT NULL,
            draft TEXT NOT NULL
        )
    """)

    db.execute("""
        CREATE TABLE agent_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            decided_by TEXT,
            reason TEXT
        )
    """)

    db.execute("""
        CREATE TABLE messages (
            room TEXT NOT NULL,
            seq INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            did TEXT,
            text TEXT NOT NULL,
            nonce TEXT,
            PRIMARY KEY (room, seq)
        )
    """)

    db.execute("""
        INSERT INTO agent_candidates
        (topic, source_seq, score, draft)
        VALUES (?, ?, ?, ?)
    """, (
        "signed_write",
        100,
        0.9,
        "Generic protocol activity.",
    ))

    db.execute("""
        INSERT INTO agent_approvals
        (candidate_id, status)
        VALUES (1, 'pending')
    """)

    db.execute("""
        INSERT INTO messages
        (room, seq, timestamp, did, text, nonce)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "test",
        100,
        "2026-08-27T12:00:00Z",
        "did:key:test",
        "Generic protocol activity.",
        "nonce",
    ))

    db.commit()
    db.close()

    monkeypatch.setattr(
        review,
        "collect_internal_evidence",
        lambda: [
            type(
                "Support",
                (),
                {
                    "topic": "signed_write",
                    "confidence": 0.50,
                    "facts": (),
                },
            )()
        ],
    )

    queue = review.build_review_queue()

    assert queue == []
