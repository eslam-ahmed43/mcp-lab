# mcp-lab

Hands-on MCP lab built with FastMCP: tools, resources, prompts, gateway, authentication, policy engine and failure handling.

## Milestones
- M1: server with tools, resources and prompts over stdio and Streamable HTTP (docs/m1.md)

## Run
uv sync
uv run python m1_fundamentals/server.py http
uv run python m1_fundamentals/client_http.py
