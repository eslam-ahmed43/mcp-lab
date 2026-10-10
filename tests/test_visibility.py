import re
from pathlib import Path
from types import SimpleNamespace

from auth import authenticate
from policy import TOOL_PERMISSION
from visibility import filter_tools

ALL = [
    SimpleNamespace(name=name)
    for name in (
        "create_task",
        "complete_task",
        "delete_task",
        "list_pending_approvals",
        "review_approval",
        "retry_approval",
    )
]


def names(token):
    return {tool.name for tool in filter_tools(authenticate(token), ALL)}


def test_reader_sees_no_tools():
    assert names("reader-token") == set()


def test_writer_sees_only_write_tools():
    assert names("writer-token") == {"create_task", "complete_task"}


def test_admin_sees_every_tool():
    assert names("admin-token") == {tool.name for tool in ALL}


def test_unauthenticated_client_sees_nothing():
    assert filter_tools(None, ALL) == []


def test_unknown_tool_is_hidden_from_everyone():
    tools = [SimpleNamespace(name="drop_database")]
    assert filter_tools(authenticate("admin-token"), tools) == []


def test_every_gateway_tool_has_a_permission_entry():
    source = (Path(__file__).parent.parent / "m2_gateway" / "gateway.py").read_text(
        encoding="utf-8"
    )
    declared = re.findall(r"@mcp\.tool\s+async def (\w+)", source)
    assert declared
    assert set(declared) <= set(TOOL_PERMISSION)
