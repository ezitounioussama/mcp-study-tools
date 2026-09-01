# Local MCP Study Tools Server

An MCP server that gives a study assistant three tools — explain a topic, build a study plan,
generate a revision checklist — plus two read-only resources, `project://course-outline` and
`project://status`. It runs over stdio, so the client starts it as a child process and nothing
listens on a network port.

The interesting half is what the tools do with bad input. A failure is *returned*, not raised:
an empty topic comes back as `{"ok": false, "error": {"code": "EMPTY_TOPIC", "field": "topic",
"hint": "..."}}`, because an exception inside a tool reaches the agent as a stack trace it can't
branch on. Out-of-range values aren't errors at all — `days=30` is clamped to 14 and the response
says it was clamped, since a caller that silently gets 14 can't tell a limit from a bug. And a
topic that reads as an instruction rather than a subject never reaches the model.

```bash
uv venv
uv pip install -r requirements.txt

.venv/bin/python client_test.py     # connect over stdio, list tools, call them
.venv/bin/python agent_demo.py      # choose a tool, check it's allowed, then call it
.venv/bin/python tests.py           # 47 tests, no server or model needed
```

A local Ollama model (`qwen3:8b`) is used for explanations if it's running, and the response
labels which source answered. Everything works without it.

## Also in this repo

- **[docs/mcp-checkpoint-report.md](docs/mcp-checkpoint-report.md)** — the MCP architecture, every
  tool and resource, the client test output, the documented failure, the security notes, and two
  things measured while building (including a prompt guard sentence that became the topic, 6 runs
  out of 6)
- [`docs/output.txt`](docs/output.txt) — raw log of the client test, the agent demo and the tests

---

Author: **Oussama Ezitouni**
