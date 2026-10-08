# mcp-lab

Hands-on MCP lab built with FastMCP: tools, resources, prompts, gateway, authentication, policy engine and failure handling.

## Milestones
- M1: server with tools, resources and prompts over stdio and Streamable HTTP (docs/m1.md)
- M2: SQLite storage, token auth, policy engine (ALLOW, DENY, REQUIRE_APPROVAL), two-admin approval flow and audit log (docs/m2.md)
- M3: error classification, retry with backoff, idempotency keys, approval execution status and fault injection (docs/m3.md)

## Run

    uv sync
    uv run pytest
    uv run python m2_gateway/gateway.py
    uv run python m2_gateway/gateway_client.py writer-token create

## Fault injection

    $env:MCP_FAULTS = "complete_task:rate_limit:2,delete_task:timeout:5"
    uv run python m2_gateway/gateway.py
