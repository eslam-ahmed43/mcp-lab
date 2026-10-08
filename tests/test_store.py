import store


def test_delete_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "t.db")
    task = store.create_task("x", "low")
    assert store.delete_task(task["id"]) is True
    assert store.delete_task(task["id"]) is False


def test_complete_missing_task_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "t.db")
    assert store.complete_task(999) is None