from observatory.impact import assess_change, assess_changes, highest_priority


def make_change(old, new, change_type="changed", path="x"):
    return {
        "type": change_type,
        "path": path,
        "old": old,
        "new": new,
    }


def test_limit_expansion():
    result = assess_change("limit_changed", make_change(300, 500))
    assert result == {
        "severity": "medium",
        "direction": "expanded",
        "research_priority": "medium",
    }


def test_limit_restriction():
    result = assess_change("limit_changed", make_change(300, 50))
    assert result == {
        "severity": "medium",
        "direction": "restricted",
        "research_priority": "high",
    }


def test_identity_change():
    result = assess_change(
        "identity_changed",
        make_change("Ed25519", "Ed448"),
    )
    assert result["severity"] == "high"
    assert result["research_priority"] == "high"


def test_authentication_change():
    result = assess_change(
        "authentication_changed",
        make_change("old", "new"),
    )
    assert result["severity"] == "critical"
    assert result["research_priority"] == "critical"


def test_capability_added():
    result = assess_change(
        "capability_added",
        make_change(None, {}, "added"),
    )
    assert result == {
        "severity": "medium",
        "direction": "added",
        "research_priority": "medium",
    }


def test_capability_removed():
    result = assess_change(
        "capability_removed",
        make_change({}, None, "removed"),
    )
    assert result == {
        "severity": "high",
        "direction": "removed",
        "research_priority": "high",
    }


def test_documentation_change():
    result = assess_change(
        "documentation_changed",
        make_change("old", "new"),
    )
    assert result == {
        "severity": "low",
        "direction": "neutral",
        "research_priority": "low",
    }


def test_compute_change():
    result = assess_change(
        "compute_changed",
        make_change(100, 200),
    )
    assert result["severity"] == "high"
    assert result["research_priority"] == "high"


def test_assess_changes():
    result = assess_changes([
        {
            "type": "changed",
            "path": "limits.reads_per_minute",
            "old": 600,
            "new": 300,
            "category": "limit_changed",
        }
    ])

    assert result[0]["path"] == "limits.reads_per_minute"
    assert result[0]["direction"] == "restricted"
    assert result[0]["research_priority"] == "high"


def test_highest_priority():
    changes = [
        {"research_priority": "low"},
        {"research_priority": "medium"},
        {"research_priority": "critical"},
    ]

    assert highest_priority(changes) == "critical"


def test_empty_priority():
    assert highest_priority([]) == "low"
