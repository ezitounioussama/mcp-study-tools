"""MCP client test: connect over stdio, list what the server offers, call tools.

Run it with the project venv so the SDK is importable:

    .venv/bin/python client_test.py

It starts server.py as a subprocess and speaks MCP to it, which is the same
thing an MCP host such as Claude Desktop does.
"""

import asyncio
import json
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

HERE = Path(__file__).resolve().parent
RULE = "=" * 78


def server_parameters():
    """Launch server.py with the interpreter running this script."""
    return StdioServerParameters(
        command=sys.executable,
        args=[str(HERE / "server.py")],
        cwd=str(HERE),
    )


def show(result):
    """Print a tool result as JSON, whatever shape the SDK wrapped it in."""
    if getattr(result, "structured_content", None):
        payload = result.structured_content
        # The SDK wraps a bare dict return under "result".
        if set(payload) == {"result"}:
            payload = payload["result"]
        print(json.dumps(payload, indent=2)[:1400])
        return payload

    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            print(text[:1400])
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"raw": text}
    return None


async def main():
    print(f"{RULE}\n MCP CLIENT TEST -- study-tools server over stdio\n{RULE}")

    async with Client(server_parameters()) as client:
        info = client.server_info
        print(f"\nConnected to: {info.name} v{info.version}")
        print(f"Protocol    : {client.protocol_version}")

        # ---------------------------------------------------------- discovery
        print(f"\n{RULE}\n 1. TOOLS THE SERVER ADVERTISES\n{RULE}")
        tools = (await client.list_tools()).tools
        for tool in tools:
            required = tool.input_schema.get("required", [])
            arguments = ", ".join(tool.input_schema.get("properties", {}))
            print(f"\n  - {tool.name}({arguments})")
            print(f"      required: {required or 'none'}")
            print(f"      {' '.join((tool.description or '').split())}")

        print(f"\n{RULE}\n 2. RESOURCES (read-only)\n{RULE}")
        resources = (await client.list_resources()).resources
        for resource in resources:
            print(f"  - {resource.uri}  [{resource.mime_type}]  {resource.name}")

        # ------------------------------------------------------------- calls
        print(f"\n{RULE}\n 3. CALL create_study_plan (days clamped 30 -> 14)\n{RULE}")
        plan = await client.call_tool(
            "create_study_plan", {"topic": "MCP resources", "days": 30, "hours_per_day": 1.5}
        )
        payload = show(plan)
        if payload:
            print(f"\n  -> days={payload['days']} requested={payload['days_requested']} "
                  f"clamped={payload['clamped']}")

        print(f"\n{RULE}\n 4. CALL generate_revision_checklist\n{RULE}")
        show(await client.call_tool(
            "generate_revision_checklist", {"topic": "MCP tools vs resources", "items": 4}
        ))

        print(f"\n{RULE}\n 5. CALL explain_topic\n{RULE}")
        show(await client.call_tool(
            "explain_topic", {"topic": "the difference between an MCP tool and an MCP resource"}
        ))

        # ------------------------------------------------- documented failure
        print(f"\n{RULE}\n 6. DOCUMENTED FAILURE -- empty topic\n{RULE}")
        failure = await client.call_tool("explain_topic", {"topic": "   "})
        print(f"  is_error flag from the protocol: {failure.is_error}")
        show(failure)

        print(f"\n{RULE}\n 7. READ THE RESOURCES\n{RULE}")
        for uri in ("project://course-outline", "project://status"):
            print(f"\n  {uri}")
            contents = (await client.read_resource(uri)).contents
            print("\n".join("    " + line for line in contents[0].text.splitlines()[:26]))

    print(f"\n{RULE}\n CLIENT TEST COMPLETE\n{RULE}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
