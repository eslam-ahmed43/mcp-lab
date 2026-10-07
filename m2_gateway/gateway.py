from fastmcp import Client, FastMCP
from fastmcp.server.dependencies import get_http_headers

from auth import authenticate
from policy import Decision, authorize

BACKEND_URL = "http://127.0.0.1:9000/mcp"

mcp = FastMCP("gateway")

PENDING: dict[int, dict] = {}
_next_approval = 1


def _principal():
    headers = get_http_headers(include_all=True)
    value = headers.get("authorization", "")
    token = value.removeprefix("Bearer ").strip() or None
    return authenticate(token)


def _guard(tool: str, arguments: dict):
    principal = _principal()
    decision = authorize(principal, tool, arguments)
    if decision == Decision.DENY:
        raise PermissionError(f"{tool} denied")
    return principal, decision


def _queue_approval(requester: str, tool: str, arguments: dict) -> dict:
    global _next_approval
    approval_id = _next_approval
    _next_approval += 1
    PENDING[approval_id] = {"requester": requester, "tool": tool, "arguments": arguments}
    return {"status": "pending_approval", "approval_id": approval_id}


async def _forward(tool: str, arguments: dict):
    async with Client(BACKEND_URL) as backend:
        result = await backend.call_tool(tool, arguments)
    return result.data


@mcp.tool
async def create_task(title: str, priority: str = "medium") -> dict:
    """Create a new task. priority must be low, medium, or high."""
    arguments = {"title": title, "priority": priority}
    _guard("create_task", arguments)
    return await _forward("create_task", arguments)


@mcp.tool
async def complete_task(task_id: int) -> dict:
    """Mark a task as done."""
    arguments = {"task_id": task_id}
    _guard("complete_task", arguments)
    return await _forward("complete_task", arguments)


@mcp.tool
async def delete_task(task_id: int) -> dict:
    """Permanently delete a task. Requires human approval."""
    arguments = {"task_id": task_id}
    principal, decision = _guard("delete_task", arguments)
    if decision == Decision.REQUIRE_APPROVAL:
        return _queue_approval(principal.name, "delete_task", arguments)
    return await _forward("delete_task", arguments)


@mcp.resource("tasks://all")
async def all_tasks() -> str:
    """All tasks, read-only context."""
    _guard("read_tasks", {})
    async with Client(BACKEND_URL) as backend:
        contents = await backend.read_resource("tasks://all")
    return contents[0].text


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8000)