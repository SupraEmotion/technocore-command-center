from agent.policy import classify


def assert_decision(text, action, reason):
    result = classify(text)

    assert result.action == action
    assert result.reason == reason


def test_direct_technical_question():
    assert_decision(
        "What happens to a signed write if the client times out "
        "after the network commits it?",
        "opportunity",
        "direct_technical_question",
    )


def test_technical_how_question():
    assert_decision(
        "How does Technocore assign sequence numbers to messages?",
        "opportunity",
        "direct_technical_question",
    )


def test_did_nonce_question():
    assert_decision(
        "Can anyone explain how DID and nonce verification works?",
        "opportunity",
        "direct_technical_question",
    )


def test_collector_question():
    assert_decision(
        "Why would a collector need long polling for the Technocore protocol?",
        "opportunity",
        "direct_technical_question",
    )


def test_embedded_technical_question():
    assert_decision(
        "The shared KV idea is interesting for durable coordination state. "
        "How are you handling authenticity and stale writes?",
        "opportunity",
        "direct_technical_question",
    )


def test_embedded_agent_question():
    assert_decision(
        "Clear goals and constraints help. I'm exploring lightweight agent "
        "coordination on Technocore — what interface or task are you testing?",
        "opportunity",
        "direct_technical_question",
    )


def test_casual_question_is_ignored():
    assert_decision(
        "Hey, what's up?",
        "ignored",
        "no_clear_engagement_opportunity",
    )


def test_general_flop_question_is_ignored():
    assert_decision(
        "Anyone else working on FLOP stuff today?",
        "ignored",
        "no_clear_engagement_opportunity",
    )


def test_poetic_technocore_question_is_not_opportunity():
    result = classify(
        "Among the hum of converging protocols, what patterns slip "
        "unnoticed beneath technocore's digital pulse tonight?"
    )

    assert result.action != "opportunity"


def test_presence_message_is_ignored():
    assert_decision(
        "Technocore protocol engagement active",
        "ignored",
        "presence_message",
    )


def test_promotion_is_ignored():
    assert_decision(
        "I published a Technocore contribution about signed writes.",
        "ignored",
        "promotion_or_contribution_announcement",
    )
