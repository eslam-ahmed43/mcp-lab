import asyncio
import sys

from fastmcp import Client

URL = "http://127.0.0.1:8000/mcp"


async def attempt(label, coro):
    try:
        result = await coro
        print(label, "->", getattr(result, "data", result))
    except Exception as exc:
        print(label, "-> ERROR:", exc)


async def main():
    token = sys.argv[1]
    async with Client(URL, auth=token) as client:
        await attempt("create", client.call_tool("create_task", {"title": "via gateway"}))
        await attempt("delete", client.call_tool("delete_task", {"task_id": 1}))
        await attempt("read", client.read_resource("tasks://all"))


asyncio.run(main())