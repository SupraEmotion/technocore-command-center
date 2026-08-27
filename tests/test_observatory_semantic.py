from observatory.semantic import classify_change, classify_changes, summarize_categories


def change(path, change_type="changed"):
    return {
        "type": change_type,
        "path": path,
        "old": None,
        "new": None,
    }


def test_limit_change():
    assert (
        classify_change(
            "config",
            change("limits.writes_per_minute"),
        )
        == "limit_changed"
    )


def test_identity_change():
    assert (
        classify_change(
            "config",
            change("identity.signature_algorithm"),
        )
        == "identity_changed"
    )


def test_capability_added():
    assert (
        classify_change(
            "openapi",
            change("paths./new-endpoint", "added"),
        )
        == "capability_added"
    )


def test_capability_removed():
    assert (
        classify_change(
            "openapi",
            change("paths./old-endpoint", "removed"),
        )
        == "capability_removed"
    )


def test_documentation_change():
    assert (
        classify_change(
            "skill",
            change("instructions.participation"),
        )
        == "documentation_changed"
    )


def test_compute_change():
    assert (
        classify_change(
            "config",
            change("inference.compute_budget"),
        )
        == "compute_changed"
    )


def test_category_summary():
    classified = classify_changes(
        "config",
        [
            change("limits.reads_per_minute"),
            change("limits.writes_per_minute"),
            change("identity.did_method"),
        ],
    )

    assert summarize_categories(classified) == {
        "identity_changed": 1,
        "limit_changed": 2,
    }
