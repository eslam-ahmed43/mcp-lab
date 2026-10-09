import json
import os

from dotenv import load_dotenv
from fastmcp import Client
from google import genai
from google.genai import types

from errors import ErrorCategory, ToolFailure
from retry import call_with_retry

load_dotenv()

GATEWAY_URL = "http://127.0.0.1:8000/mcp"
MAX_STEPS = 6

READ_TASKS = types.FunctionDeclaration(
    name="read_tasks",
    description="Read the list of all tasks.",
)


def model_name() -> str:
    name = os.environ.get("GEMINI_MODEL", "").strip()
    if not name:
        raise SystemExit("set GEMINI_MODEL in .env (run list_models.py to see options)")
    return name


def to_schema(node: dict) -> types.Schema:
    if "anyOf" in node:
        options = [o for o in node["anyOf"] if o.get("type") != "null"]
        base = options[0] if options else {"type": "string"}
        node = {**base, "description": node.get("description") or base.get("description")}
    kind = node.get("type", "string")
    if kind == "object":
        properties = {k: to_schema(v) for k, v in node.get("properties", {}).items()}
        return types.Schema(
            type="OBJECT",
            properties=properties,
            required=node.get("required") or None,
        )
    return types.Schema(type=kind.upper(), description=node.get("description"))


def declaration(tool) -> types.FunctionDeclaration:
    schema = tool.input_schema
    description = tool.description or ""
    if not schema.get("properties"):
        return types.FunctionDeclaration(name=tool.name, description=description)
    return types.FunctionDeclaration(
        name=tool.name, description=description, parameters=to_schema(schema)
    )


def clean_args(args: dict) -> dict:
    return {
        key: int(value) if isinstance(value, float) and value.is_integer() else value
        for key, value in args.items()
    }


def json_safe(value):
    return json.loads(json.dumps(value, default=str))


async def execute(gateway, name: str, args: dict) -> dict:
    try:
        if name == "read_tasks":
            contents = await gateway.read_resource("tasks://all")
            return {"ok": True, "result": json.loads(contents[0].text)}
        result = await gateway.call_tool(name, args)
        return {"ok": True, "result": json_safe(result.data)}
    except Exception as exc:
        return {"ok": False, "result": str(exc)}


def to_response(outcome: dict) -> dict:
    key = "output" if outcome["ok"] else "error"
    return {key: outcome["result"]}


async def generate(client, contents, config):
    async def attempt():
        try:
            return await client.aio.models.generate_content(
                model=model_name(), contents=contents, config=config
            )
        except Exception as exc:
            text = str(exc)
            if "429" in text or "RESOURCE_EXHAUSTED" in text:
                raise ToolFailure(ErrorCategory.RATE_LIMIT, text[:200]) from exc
            if "503" in text or "UNAVAILABLE" in text:
                raise ToolFailure(ErrorCategory.UNAVAILABLE, text[:200]) from exc
            raise

    return await call_with_retry(attempt, max_attempts=5, base_delay=2.0, max_delay=30.0)


async def run_agent(token: str, prompt: str, system: str) -> dict:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    calls = []
    final_text = ""
    async with Client(GATEWAY_URL, auth=token) as gateway:
        tools = await gateway.list_tools()
        declarations = [declaration(t) for t in tools] + [READ_TASKS]
        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=[types.Tool(function_declarations=declarations)],
            temperature=0,
        )
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
        for _ in range(MAX_STEPS):
            response = await generate(client, contents, config)
            if not response.candidates or response.candidates[0].content is None:
                final_text = "[no content returned]"
                break
            message = response.candidates[0].content
            contents.append(message)
            parts = message.parts or []
            requests = [p.function_call for p in parts if p.function_call]
            if not requests:
                final_text = "".join(p.text or "" for p in parts)
                break
            replies = []
            for call in requests:
                args = clean_args(dict(call.args or {}))
                outcome = await execute(gateway, call.name, args)
                calls.append(
                    {
                        "tool": call.name,
                        "args": args,
                        "ok": outcome["ok"],
                        "result": outcome["result"],
                    }
                )
                replies.append(
                    types.Part.from_function_response(
                        name=call.name, response=to_response(outcome)
                    )
                )
            contents.append(types.Content(role="user", parts=replies))
    return {"calls": calls, "final": final_text}
