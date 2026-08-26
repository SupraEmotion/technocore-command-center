from collector.analytics_v2 import (
    classify_message,
    extract_urls,
    message_hash,
)


def test_message_hash_is_deterministic():
    value1 = message_hash(
        "technocore",
        1,
        "did:key:test",
        "hello",
    )

    value2 = message_hash(
        "technocore",
        1,
        "did:key:test",
        "hello",
    )

    assert value1 == value2
    assert len(value1) == 64


def test_different_messages_have_different_hashes():
    value1 = message_hash(
        "technocore",
        1,
        "did:key:test",
        "hello",
    )

    value2 = message_hash(
        "technocore",
        2,
        "did:key:test",
        "hello",
    )

    assert value1 != value2


def test_url_extraction():
    text = (
        "Read https://technocore.chat/r/test "
        "and https://github.com/example/project"
    )

    urls = extract_urls(text)

    assert len(urls) == 2
    assert "https://github.com/example/project" in urls


def test_message_classification():
    assert (
        classify_message("Agent heartbeat — Technocore layer online.")
        == "heartbeat"
    )

    assert (
        classify_message(
            "Public contribution: research report"
        )
        == "contribution"
    )

    assert (
        classify_message(
            "Technocore protocol engagement active."
        )
        == "protocol"
    )
