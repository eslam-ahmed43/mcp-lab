import pytest

from approvals import ApprovalError, ApprovalStore


def make_item(store):
    return store.submit("carol", "delete_task", {"task_id": 1})


def test_requester_cannot_approve_own_request():
    store = ApprovalStore()
    item = make_item(store)
    with pytest.raises(ApprovalError):
        store.decide(item.id, "carol", "admin", True)


def test_other_admin_can_approve():
    store = ApprovalStore()
    item = make_item(store)
    result = store.decide(item.id, "dave", "admin", True)
    assert result.status == "approved"
    assert result.reviewer == "dave"


def test_non_admin_cannot_review():
    store = ApprovalStore()
    item = make_item(store)
    with pytest.raises(ApprovalError):
        store.decide(item.id, "bob", "writer", True)


def test_cannot_decide_twice():
    store = ApprovalStore()
    item = make_item(store)
    store.decide(item.id, "dave", "admin", False)
    with pytest.raises(ApprovalError):
        store.decide(item.id, "dave", "admin", True)


def test_pending_only_lists_open_requests():
    store = ApprovalStore()
    first = make_item(store)
    make_item(store)
    store.decide(first.id, "dave", "admin", True)
    assert len(store.pending()) == 1


def test_execution_result_is_recorded():
    store = ApprovalStore()
    item = make_item(store)
    assert item.execution == "not_run"
    store.decide(item.id, "dave", "admin", True)
    done = store.record_execution(item.id, True)
    assert done.execution == "executed"
    assert done.error is None


def test_failed_execution_keeps_error():
    store = ApprovalStore()
    item = make_item(store)
    store.decide(item.id, "dave", "admin", True)
    done = store.record_execution(item.id, False, "NOT_FOUND: task 1 not found")
    assert done.status == "approved"
    assert done.execution == "failed"
    assert done.error == "NOT_FOUND: task 1 not found"


def test_cannot_record_execution_before_approval():
    store = ApprovalStore()
    item = make_item(store)
    with pytest.raises(ApprovalError):
        store.record_execution(item.id, True)


def test_only_failed_executions_are_retryable():
    store = ApprovalStore()
    item = make_item(store)
    with pytest.raises(ApprovalError):
        store.get_retryable(item.id)
    store.decide(item.id, "dave", "admin", True)
    with pytest.raises(ApprovalError):
        store.get_retryable(item.id)
    store.record_execution(item.id, False, "TIMEOUT: x")
    assert store.get_retryable(item.id).id == item.id
    store.record_execution(item.id, True)
    with pytest.raises(ApprovalError):
        store.get_retryable(item.id)
