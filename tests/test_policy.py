from auth import authenticate
from policy import Decision, authorize


def test_invalid_token_is_rejected():
    assert authenticate("nope") is None
    assert authenticate(None) is None
    assert authorize(None, "create_task", {}) == Decision.DENY


def test_reader_cannot_write():
    reader = authenticate("reader-token")
    assert authorize(reader, "create_task", {"title": "x"}) == Decision.DENY


def test_writer_can_write_but_not_delete():
    writer = authenticate("writer-token")
    assert authorize(writer, "create_task", {"title": "x"}) == Decision.ALLOW
    assert authorize(writer, "complete_task", {"task_id": 1}) == Decision.ALLOW
    assert authorize(writer, "delete_task", {"task_id": 1}) == Decision.DENY


def test_admin_delete_requires_approval():
    admin = authenticate("admin-token")
    assert authorize(admin, "delete_task", {"task_id": 1}) == Decision.REQUIRE_APPROVAL


def test_unknown_tool_is_denied():
    admin = authenticate("admin-token")
    assert authorize(admin, "drop_database", {}) == Decision.DENY