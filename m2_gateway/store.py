import sqlite3
from contextlib import closing
from pathlib import Path

DB_PATH = Path(__file__).parent / "tasks.db"


class KeyReuseError(Exception):
    pass


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS tasks ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT NOT NULL, "
        "priority TEXT NOT NULL, "
        "done INTEGER NOT NULL DEFAULT 0)"
    )
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
    if "idempotency_key" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN idempotency_key TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_idempotency "
        "ON tasks(idempotency_key)"
    )
    return conn


def _to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "priority": row["priority"],
        "done": bool(row["done"]),
    }


def _find_by_key(conn: sqlite3.Connection, key: str):
    return conn.execute(
        "SELECT * FROM tasks WHERE idempotency_key = ?", (key,)
    ).fetchone()


def _replay(row: sqlite3.Row, title: str, priority: str) -> dict:
    if row["title"] != title or row["priority"] != priority:
        raise KeyReuseError("idempotency key was already used with different arguments")
    return _to_dict(row)


def create_task_with_status(
    title: str, priority: str, idempotency_key: str | None = None
) -> tuple[dict, bool]:
    with closing(_connect()) as conn, conn:
        if idempotency_key is not None:
            existing = _find_by_key(conn, idempotency_key)
            if existing is not None:
                return _replay(existing, title, priority), True
        try:
            cur = conn.execute(
                "INSERT INTO tasks (title, priority, idempotency_key) VALUES (?, ?, ?)",
                (title, priority, idempotency_key),
            )
        except sqlite3.IntegrityError:
            existing = (
                _find_by_key(conn, idempotency_key)
                if idempotency_key is not None
                else None
            )
            if existing is None:
                raise
            return _replay(existing, title, priority), True
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _to_dict(row), False


def create_task(title: str, priority: str, idempotency_key: str | None = None) -> dict:
    task, _ = create_task_with_status(title, priority, idempotency_key)
    return task


def get_task(task_id: int) -> dict | None:
    with closing(_connect()) as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _to_dict(row) if row else None


def list_tasks() -> list[dict]:
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()
    return [_to_dict(r) for r in rows]


def complete_task(task_id: int) -> dict | None:
    with closing(_connect()) as conn, conn:
        conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _to_dict(row) if row else None


def delete_task(task_id: int) -> bool:
    with closing(_connect()) as conn, conn:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return cur.rowcount > 0
