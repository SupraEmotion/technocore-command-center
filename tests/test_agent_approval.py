import tempfile
from pathlib import Path

import agent.approval as approval


def isolated_db(monkeypatch):
    tmp = tempfile.TemporaryDirectory()
    db_path = Path(tmp.name) / "test.db"

    monkeypatch.setattr(approval, "DB_PATH", db_path)

    import sqlite3

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

    cursor = db.execute(
        """
        INSERT INTO agent_candidates
        (topic, source_seq, score, draft)
        VALUES (?, ?, ?, ?)
        """,
        ("test", 1, 0.9, "test candidate"),
    )

    candidate_id = cursor.lastrowid
    db.commit()
    db.close()

    return tmp, candidate_id


def test_create_pending_is_idempotent(monkeypatch):
    tmp, candidate_id = isolated_db(monkeypatch)

    try:
        first = approval.create_pending(candidate_id)
        second = approval.create_pending(candidate_id)

        assert first.id == second.id
        assert first.status == "pending"
    finally:
        tmp.cleanup()


def test_pending_can_be_approved(monkeypatch):
    tmp, candidate_id = isolated_db(monkeypatch)

    try:
        approval.create_pending(candidate_id)

        result = approval.decide(
            candidate_id,
            "approved",
            decided_by="test",
            reason="test approval",
        )

        assert result.status == "approved"
        assert result.decided_by == "test"
    finally:
        tmp.cleanup()


def test_pending_can_be_rejected(monkeypatch):
    tmp, candidate_id = isolated_db(monkeypatch)

    try:
        approval.create_pending(candidate_id)

        result = approval.decide(
            candidate_id,
            "rejected",
            decided_by="test",
            reason="test rejection",
        )

        assert result.status == "rejected"
    finally:
        tmp.cleanup()


def test_decision_cannot_be_changed(monkeypatch):
    tmp, candidate_id = isolated_db(monkeypatch)

    try:
        approval.create_pending(candidate_id)

        approval.decide(
            candidate_id,
            "approved",
            decided_by="test",
        )

        try:
            approval.decide(
                candidate_id,
                "rejected",
                decided_by="test",
            )
        except ValueError as exc:
            assert "already approved" in str(exc)
        else:
            raise AssertionError("second decision was accepted")
    finally:
        tmp.cleanup()


def test_published_requires_approval(monkeypatch):
    tmp, candidate_id = isolated_db(monkeypatch)

    try:
        approval.create_pending(candidate_id)

        try:
            approval.mark_published(candidate_id)
        except ValueError as exc:
            assert "not approved" in str(exc)
        else:
            raise AssertionError("pending candidate was marked published")
    finally:
        tmp.cleanup()


def test_approved_can_be_marked_published(monkeypatch):
    tmp, candidate_id = isolated_db(monkeypatch)

    try:
        approval.create_pending(candidate_id)

        approval.decide(
            candidate_id,
            "approved",
            decided_by="test",
        )

        result = approval.mark_published(candidate_id)

        assert result.status == "published"
        assert result.decided_by == "publisher"
    finally:
        tmp.cleanup()


def test_published_cannot_be_published_again(monkeypatch):
    tmp, candidate_id = isolated_db(monkeypatch)

    try:
        approval.create_pending(candidate_id)

        approval.decide(
            candidate_id,
            "approved",
            decided_by="test",
        )

        approval.mark_published(candidate_id)

        try:
            approval.mark_published(candidate_id)
        except ValueError as exc:
            assert "not approved" in str(exc)
        else:
            raise AssertionError("published candidate was published again")
    finally:
        tmp.cleanup()
