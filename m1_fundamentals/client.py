import asyncio
from pathlib import Path

from fastmcp import Client

SERVER = Path(__file__).parent / "server.py"


async def main():
    async with Client(SERVER) as client:
        tools = await client.list_tools()
        for t in tools:
            print(t.name, "->", t.input_schema)

        result = await client.call_tool("create_task", {"title": "Prepare MCP lab"})
        print(result.data)

        print(await client.read_resource("tasks://all"))


asyncio.run(main())