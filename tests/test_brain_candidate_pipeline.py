import agent.brain as brain


class FakeDecision:
    action = "opportunity"
    score = 0.8
    reason = "test opportunity"


class FakeCandidate:
    candidate_id = 123
    score = 0.9
    reason = "external_claim_with_internal_support"


def test_opportunity_creates_candidate_event(monkeypatch):
    recorded = []

    monkeypatch.setattr(
        brain,
        "get_messages",
        lambda limit=200: [
            {
                "room": "test",
                "seq": 999001,
                "timestamp": "2026-08-27T12:00:00Z",
                "did": "did:key:test",
                "text": "Test opportunity",
            }
        ],
    )

    monkeypatch.setattr(
        brain,
        "already_seen",
        lambda seq: False,
    )

    monkeypatch.setattr(
        brain,
        "evaluate_message",
        lambda text: FakeDecision(),
    )

    monkeypatch.setattr(
        brain,
        "evaluate_candidate",
        lambda seq, text: FakeCandidate(),
    )

    monkeypatch.setattr(
        brain,
        "record_event",
        lambda event_type, **kwargs: recorded.append(
            (event_type, kwargs)
        ),
    )

    stats = brain.analyse()

    assert stats["observed"] == 1
    assert stats["opportunities"] == 1

    event_types = [event_type for event_type, _ in recorded]

    assert "candidate_created" in event_types
    assert "opportunity" in event_types

    candidate_event = next(
        kwargs
        for event_type, kwargs in recorded
        if event_type == "candidate_created"
    )

    assert candidate_event["source_seq"] == 999001
    assert candidate_event["decision"] == "review"
    assert candidate_event["score"] == 0.9
    assert candidate_event["reason"] == (
        "external_claim_with_internal_support"
    )
