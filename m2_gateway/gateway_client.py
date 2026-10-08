import asyncio
import sys

from fastmcp import Client

URL = "http://127.0.0.1:8000/mcp"


async def run(client, action):
    if action == "create":
        return await client.call_tool("create_task", {"title": "via gateway"})
    if action == "pending":
        return await client.call_tool("list_pending_approvals", {})
    if action == "read":
        return await client.read_resource("tasks://all")
    name, _, value = action.partition(":")
    if name == "complete":
        return await client.call_tool("complete_task", {"task_id": int(value)})
    if name == "delete":
        return await client.call_tool("delete_task", {"task_id": int(value)})
    if name == "approve":
        return await client.call_tool(
            "review_approval", {"approval_id": int(value), "approve": True}
        )
    if name == "reject":
        return await client.call_tool(
            "review_approval", {"approval_id": int(value), "approve": False}
        )
    raise SystemExit(f"unknown action {action}")


async def main():
    token = sys.argv[1]
    async with Client(URL, auth=token) as client:
        for action in sys.argv[2:]:
            try:
                result = await run(client, action)
                print(action, "->", getattr(result, "data", result))
            except Exception as exc:
                print(action, "-> ERROR:", exc)


asyncio.run(main())
