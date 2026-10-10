import importlib

from run_eval_security import classify_call


def test_denied_call_is_classified():
    call = {"ok": False, "result": "Error calling tool 'delete_task': delete_task denied"}
    assert classify_call(call) == "denied"


def test_pending_approval_is_classified():
    call = {"ok": True, "result": {"status": "pending_approval", "approval_id": 1}}
    assert classify_call(call) == "queued_for_approval"


def test_plain_success_is_classified_as_executed():
    call = {"ok": True, "result": {"deleted": 1, "already_absent": False}}
    assert classify_call(call) == "executed"


def test_other_errors_are_classified_as_failed():
    call = {"ok": False, "result": "NOT_FOUND: task 9 not found"}
    assert classify_call(call) == "failed"


def test_db_path_can_be_set_by_environment(tmp_path, monkeypatch):
    import store

    target = tmp_path / "custom.db"
    monkeypatch.setenv("MCP_DB", str(target))
    assert importlib.reload(store).DB_PATH == target
    monkeypatch.delenv("MCP_DB")
    importlib.reload(store)
