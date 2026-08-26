from collector.database import Database


def test_database_cursor_and_duplicate_handling(tmp_path):
    db_path = tmp_path / "test.db"

    db = Database(db_path)

    message = {
        "seq": 100,
        "ts": "2026-08-26T00:00:00Z",
        "from": "did:key:test",
        "text": "hello",
        "nonce": 123,
    }

    assert db.save_message("technocore", message) is True
    assert db.save_message("technocore", message) is False

    db.set_cursor("technocore", 100)

    assert db.get_cursor("technocore") == 100

    db.close()
