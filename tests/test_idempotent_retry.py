import pytest

import store
from retry import call_with_retry


async def no_sleep(_):
    return None


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "t.db")


def lossy_backend(key, lose_first_n):
    state = {"calls": 0}

    async def call():
        state["calls"] += 1
        task, _ = store.create_task_with_status("a", "low", key)
        if state["calls"] <= lose_first_n:
            raise TimeoutError("response lost after the task was created")
        return task

    return call, state


@pytest.mark.asyncio
async def test_retry_with_key_creates_exactly_one_task():
    call, state = lossy_backend("k1", 2)
    task = await call_with_retry(call, sleep=no_sleep)
    assert state["calls"] == 3
    assert len(store.list_tasks()) == 1
    assert task["id"] == store.list_tasks()[0]["id"]


@pytest.mark.asyncio
async def test_retry_without_key_creates_duplicates():
    call, state = lossy_backend(None, 2)
    await call_with_retry(call, sleep=no_sleep)
    assert len(store.list_tasks()) == 3
