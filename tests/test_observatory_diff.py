from observatory.diff import classify_endpoint, json_diff


def test_identical_json_has_no_changes():
    body = '{"version":"0.10.0","writes":300}'

    assert json_diff(body, body) == []


def test_changed_value_is_detected():
    changes = json_diff(
        '{"writes":300}',
        '{"writes":500}',
    )

    assert changes == [
        {
            "type": "changed",
            "path": "writes",
            "old": 300,
            "new": 500,
        }
    ]


def test_added_value_is_detected():
    changes = json_diff(
        '{"writes":300}',
        '{"writes":300,"rooms":20}',
    )

    assert changes == [
        {
            "type": "added",
            "path": "rooms",
            "old": None,
            "new": 20,
        }
    ]


def test_removed_value_is_detected():
    changes = json_diff(
        '{"writes":300,"rooms":20}',
        '{"writes":300}',
    )

    assert changes == [
        {
            "type": "removed",
            "path": "rooms",
            "old": 20,
            "new": None,
        }
    ]


def test_nested_value_is_detected():
    changes = json_diff(
        '{"limits":{"writes":300,"reads":600}}',
        '{"limits":{"writes":500,"reads":600}}',
    )

    assert changes == [
        {
            "type": "changed",
            "path": "limits.writes",
            "old": 300,
            "new": 500,
        }
    ]


def test_endpoint_classification():
    assert classify_endpoint("config") == "protocol"
    assert classify_endpoint("agent_manifest") == "protocol"
    assert classify_endpoint("openapi") == "protocol"

    assert classify_endpoint("skill") == "documentation"
    assert classify_endpoint("patterns") == "documentation"
    assert classify_endpoint("interop") == "documentation"
