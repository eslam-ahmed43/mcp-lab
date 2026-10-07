import asyncio

from fastmcp import Client


async def main():
    async with Client("http://127.0.0.1:8000/mcp") as client:
        tools = await client.list_tools()
        print([t.name for t in tools])

        result = await client.call_tool("create_task", {"title": "over http"})
        print(result.data)

        print(await client.read_resource("tasks://all"))


asyncio.run(main())