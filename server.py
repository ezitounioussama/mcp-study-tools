"""Local MCP server exposing study tools over stdio.

Three tools -- explain_topic, create_study_plan, generate_revision_checklist --
and two read-only resources, project://course-outline and project://status.

Run it directly (`python server.py`) and it speaks MCP on stdin/stdout, which
is how client_test.py and any MCP-capable host connect to it.
"""

import json
import time
import urllib.error
import urllib.request

import study_tools

SERVER_NAME = "study-tools"
SERVER_VERSION = "1.0.0"

# Optional local model. The server works fully without it: explain_topic falls
# back to a deterministic study frame and labels the source.
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2:3b"
OLLAMA_TIMEOUT = 45

STARTED_AT = time.time()
CALL_COUNTS = {"explain_topic": 0, "create_study_plan": 0, "generate_revision_checklist": 0}

# --------------------------------------------------------------------------
# SDK import
#
# mcp 2.x renamed FastMCP to MCPServer. The checkpoint brief was written
# against 1.x, so both names are tried and the server reports which one it
# found on the status resource.
# --------------------------------------------------------------------------
try:
    from mcp.server.mcpserver import MCPServer as ServerClass

    SDK_CLASS = "mcp.server.mcpserver.MCPServer (mcp 2.x)"
except ImportError:  # pragma: no cover - only on mcp 1.x
    from mcp.server.fastmcp import FastMCP as ServerClass

    SDK_CLASS = "mcp.server.fastmcp.FastMCP (mcp 1.x)"

server = ServerClass(
    name=SERVER_NAME,
    version=SERVER_VERSION,
    instructions=(
        "Study tools for a learning assistant. Ask for an explanation of a topic, a "
        "day-by-day study plan, or a revision checklist. Every tool returns structured "
        "JSON; failures come back as {'ok': false, 'error': {...}} rather than as an "
        "exception."
    ),
)


def _ollama_generate(prompt):
    """One call to a local Ollama model. Raises on any problem."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 260},
    }
    request = urllib.request.Request(
        OLLAMA_HOST + "/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT) as response:
        return (json.loads(response.read()).get("response") or "").strip()


def _model_available():
    try:
        with urllib.request.urlopen(OLLAMA_HOST + "/api/tags", timeout=2) as response:
            installed = [model["name"] for model in json.loads(response.read()).get("models", [])]
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False
    return any(name.startswith(OLLAMA_MODEL.split(":")[0]) for name in installed)


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

@server.tool(
    description=(
        "Explain a study topic at beginner, intermediate or advanced level. "
        "Returns the explanation and whether it came from the local model or the "
        "built-in study frame."
    )
)
def explain_topic(topic: str, level: str = "beginner") -> dict:
    CALL_COUNTS["explain_topic"] += 1
    return study_tools.explain_topic(topic, level, generate=_ollama_generate)


@server.tool(
    description=(
        "Build a day-by-day study plan for a topic. days is clamped to 1-14 and "
        "hours_per_day to 0.5-8; the response reports any clamping."
    )
)
def create_study_plan(topic: str, days: int = 7, hours_per_day: float = 1.0) -> dict:
    CALL_COUNTS["create_study_plan"] += 1
    return study_tools.create_study_plan(topic, days, hours_per_day)


@server.tool(
    description="Generate a revision checklist for a topic. items is clamped to 3-15."
)
def generate_revision_checklist(topic: str, items: int = 6) -> dict:
    CALL_COUNTS["generate_revision_checklist"] += 1
    return study_tools.generate_revision_checklist(topic, items)


# --------------------------------------------------------------------------
# Read-only resources
# --------------------------------------------------------------------------

COURSE_OUTLINE = {
    "course": "AI Agents and the Model Context Protocol",
    "modules": [
        {"module": 1, "title": "Agent concepts", "topics": ["perception", "planning", "memory", "action"]},
        {"module": 2, "title": "Tool use", "topics": ["tool schemas", "routing", "fallback logic"]},
        {"module": 3, "title": "MCP basics", "topics": ["hosts", "clients", "servers", "stdio transport"]},
        {"module": 4, "title": "MCP primitives", "topics": ["tools", "resources", "prompts"]},
        {"module": 5, "title": "Safety", "topics": ["input validation", "clamping", "tool allowlists"]},
    ],
}


@server.resource(
    "project://course-outline",
    name="course-outline",
    description="The course this study server supports. Read-only.",
    mime_type="application/json",
)
def course_outline() -> str:
    """Read-only: returns data, takes no arguments, changes nothing."""
    return json.dumps(COURSE_OUTLINE, indent=2)


@server.resource(
    "project://status",
    name="status",
    description="Server name, version, uptime, tool list and per-tool call counts. Read-only.",
    mime_type="application/json",
)
def status() -> str:
    return json.dumps(
        {
            "server": SERVER_NAME,
            "version": SERVER_VERSION,
            "sdk_class": SDK_CLASS,
            "transport": "stdio",
            "uptime_seconds": round(time.time() - STARTED_AT, 1),
            "tools": sorted(CALL_COUNTS),
            "call_counts": dict(CALL_COUNTS),
            "model": OLLAMA_MODEL if _model_available() else None,
            "model_available": _model_available(),
            "limits": {
                "max_topic_length": study_tools.MAX_TOPIC_LENGTH,
                "days": [study_tools.MIN_DAYS, study_tools.MAX_DAYS],
                "hours_per_day": [study_tools.MIN_HOURS_PER_DAY, study_tools.MAX_HOURS_PER_DAY],
                "checklist_items": [study_tools.MIN_CHECKLIST_ITEMS, study_tools.MAX_CHECKLIST_ITEMS],
            },
        },
        indent=2,
    )


if __name__ == "__main__":
    server.run(transport="stdio")
