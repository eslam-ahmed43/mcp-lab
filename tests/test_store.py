import sqlite3

import pytest

import store


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "t.db")


def test_delete_is_idempotent():
    task = store.create_task("x", "low")
    assert store.delete_task(task["id"]) is True
    assert store.delete_task(task["id"]) is False


def test_complete_missing_task_returns_none():
    assert store.complete_task(999) is None


def test_same_key_returns_same_task_without_duplicate():
    first, replayed_first = store.create_task_with_status("a", "low", "k1")
    second, replayed_second = store.create_task_with_status("a", "low", "k1")
    assert replayed_first is False
    assert replayed_second is True
    assert first["id"] == second["id"]
    assert len(store.list_tasks()) == 1


def test_same_key_with_different_arguments_is_rejected():
    store.create_task_with_status("a", "low", "k1")
    with pytest.raises(store.KeyReuseError):
        store.create_task_with_status("b", "low", "k1")
    assert len(store.list_tasks()) == 1


def test_different_keys_create_different_tasks():
    store.create_task_with_status("a", "low", "k1")
    store.create_task_with_status("a", "low", "k2")
    assert len(store.list_tasks()) == 2


def test_no_key_always_creates_new_task():
    store.create_task_with_status("a", "low")
    store.create_task_with_status("a", "low")
    assert len(store.list_tasks()) == 2


def test_existing_database_without_key_column_is_migrated(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy.db"
    conn = sqlite3.connect(legacy)
    conn.execute(
        "CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT NOT NULL, priority TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute("INSERT INTO tasks (title, priority) VALUES ('old', 'low')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(store, "DB_PATH", legacy)
    task, replayed = store.create_task_with_status("new", "low", "k1")
    assert replayed is False
    assert len(store.list_tasks()) == 2
