import asyncio
import sys

from fastmcp import Client


async def main():
    async with Client("http://127.0.0.1:9000/mcp") as client:
        if len(sys.argv) > 1 and sys.argv[1] == "create":
            result = await client.call_tool("create_task", {"title": "persist me"})
            print(result.data)
        print(await client.read_resource("tasks://all"))


asyncio.run(main())