import sqlite3
from pathlib import Path

import agent.approval as approval
import agent.publisher as publisher


def setup_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"

    monkeypatch.setattr(approval, "DB_PATH", db_path)
    monkeypatch.setattr(publisher, "DB_PATH", db_path)

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

    cursor = db.execute(
        """
        INSERT INTO agent_candidates
        (topic, source_seq, score, draft)
        VALUES (?, ?, ?, ?)
        """,
        (
            "signed_write",
            100,
            0.9,
            "Independent verification of a signed write.",
        ),
    )

    candidate_id = cursor.lastrowid
    db.commit()
    db.close()

    return db_path, candidate_id


def test_candidate_requires_approval_before_publish(
    monkeypatch,
    tmp_path,
):
    db_path, candidate_id = setup_db(monkeypatch, tmp_path)

    calls = []

    def fake_post(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("network POST must not happen")

    monkeypatch.setattr(
        publisher,
        "post_signed_message",
        fake_post,
    )

    try:
        publisher.publish(candidate_id)
    except ValueError as exc:
        assert "no approval record" in str(exc)
    else:
        raise AssertionError(
            "publisher accepted an unapproved candidate"
        )

    assert calls == []


def test_approved_candidate_reaches_network_once(
    monkeypatch,
    tmp_path,
):
    db_path, candidate_id = setup_db(monkeypatch, tmp_path)

    approval.create_pending(candidate_id)

    approval.decide(
        candidate_id,
        "approved",
        decided_by="test",
        reason="Explicit test approval.",
    )

    calls = []

    class FakeKey:
        pass

    monkeypatch.setattr(
        publisher,
        "load_identity",
        lambda *args, **kwargs: FakeKey(),
    )

    monkeypatch.setattr(
        publisher,
        "did_from_private_key",
        lambda key: "did:key:test",
    )

    monkeypatch.setattr(
        publisher,
        "next_nonce",
        lambda: "nonce-test-1",
    )

    def fake_post(key, room, text, nonce=None):
        calls.append(
            {
                "room": room,
                "text": text,
                "nonce": nonce,
            }
        )

        return {
            "posted": {
                "from": "did:key:test",
                "text": text,
                "nonce": nonce,
                "seq": 12345,
            }
        }

    monkeypatch.setattr(
        publisher,
        "post_signed_message",
        fake_post,
    )

    monkeypatch.setattr(
        publisher,
        "wait_for_committed_write",
        lambda did, nonce, expected_text, **kwargs: {
            "room": "technocore",
            "seq": 12345,
            "timestamp": "2026-08-27T12:00:00Z",
            "did": did,
            "nonce": nonce,
            "text": expected_text,
        },
    )

    publisher.publish(candidate_id)

    assert len(calls) == 1
    assert calls[0]["room"] == "technocore"
    assert calls[0]["nonce"] == "nonce-test-1"

    final = approval.get(candidate_id)

    assert final is not None
    assert final.status == "published"


def test_published_candidate_cannot_post_again(
    monkeypatch,
    tmp_path,
):
    db_path, candidate_id = setup_db(monkeypatch, tmp_path)

    approval.create_pending(candidate_id)

    approval.decide(
        candidate_id,
        "approved",
        decided_by="test",
    )

    approval.mark_published(candidate_id)

    calls = []

    monkeypatch.setattr(
        publisher,
        "post_signed_message",
        lambda *args, **kwargs: calls.append(True),
    )

    try:
        publisher.publish(candidate_id)
    except ValueError as exc:
        assert "already published" in str(exc)
    else:
        raise AssertionError(
            "published candidate was accepted for another POST"
        )

    assert calls == []
