# MCP Security Lab

A permission-aware MCP server with risk levels, per-tool and per-argument
policies, an audit log, and two Gradio front ends: a permission-management client
and an AI host.

**Status: implemented educational lab; several security caveats are documented
below.**

Course 9: **Build AI Agents using MCP** (IBM RAG and Agentic AI Professional
Certificate). [Course overview](../README.md)

## Overview and objectives

- Annotate tools with risk levels (low → critical).
- Enforce `allow` / `ask` / `deny` policies in the client layer.
- Support both per-tool policies and per-call policies keyed by tool name plus
  sorted JSON arguments.
- Log every decision and every state-changing server operation to an audit log.
- Require explicit approval before executing `ask` tools.
- Demonstrate the *concept* of MCP elicitation.
- Expose resources and a prompt from a permission-aware server.

This lab is about policy and audit mechanics, not production security. See
**Limitations** before exposing it to anything untrusted.

## Architecture

```text
mcp_permission_server.py        FastMCP("Permission-Aware MCP Server")
  STDIO transport
        ▲
        │ stdio_client
        │
mcp_permission_client_base.py   MCPPermissionClient
  permissions + audit + approval
        ├── mcp_permission_client_app.py   Gradio client (port 7863)
        └── mcp_permission_host_app.py     Gradio AI host + OpenAI (port 7864)
```

The server is launched as a subprocess by the client (`StdioServerParameters`
with `command="python"` and the server script path). The client owns the
permission policy; the server owns the data and audit writes.

## Server capabilities

`mcp_permission_server.py` uses `BASE_DIR = <script dir>/data`.

| Type | Name | Risk (from docstring / host map) | Behavior |
| --- | --- | --- | --- |
| Tool | `read_file(filepath)` | low | Read a file under `data/` |
| Tool | `write_file(filepath, content)` | medium | Write a file and append `WRITE` to the audit log |
| Tool | `delete_file(filepath)` | high | Delete a file and append `DELETE` to the audit log |
| Tool | `execute_command(command)` | critical | **Simulated only**; appends `EXECUTE (simulated)` |
| Resource | `file://audit/log` | — | Return the audit log |
| Resource | `file://config/permissions` | — | Return `permissions.json` (or defaults) |
| Prompt | `security_review(operation, risk_level)` | — | Generate a security-review prompt |

Risk levels are declared in the tool docstrings and encoded in the host app's
`risk_levels` map. The server does not enforce risk or permission itself; it
trusts the client.

## Permission model

`mcp_permission_client_base.py` loads `data/permissions.json` and falls back to:

```json
{
  "read_file": "allow",
  "write_file": "ask",
  "delete_file": "deny",
  "execute_command": "deny"
}
```

Lookup order in `check_permission()`:

1. Exact call key `"<tool>:<json.dumps(args, sort_keys=True)>"`.
2. Tool name.
3. `"ask"` as the default.

`call_tool_with_permission()` then:

- `deny` → writes `DENIED` to the audit log and returns a denial message.
- `ask` without `approved=True` → writes `ASK` and returns an approval-request
  message.
- otherwise → writes `ALLOWED` and calls the tool.

The Gradio client exposes **Call Tool** (normal policy) and **Approve & Execute**
(`approved=True`). The current `data/permissions.json` has `delete_file` set to
`allow` (it was changed during the lab), so it differs from the fallback default
of `deny`.

## Concepts demonstrated

- Client-side permission enforcement around MCP tool calls.
- Tool-level and argument-specific policy keys.
- Human-in-the-loop approval.
- Audit logging of both policy decisions and server-side writes/deletes.
- Risk classification and risk-aware descriptions for an LLM.
- MCP resources and prompts in a security context.
- Conceptual elicitation (`request_elicitation`) — defined but **not called** by
  the retained code.

## Technologies and dependencies

- Python 3.10+ (uses `dict | None` annotations)
- `fastmcp`, `mcp`
- `gradio`
- `openai`
- `pydantic`

There is **no `requirements.txt`**. Install directly:

```bash
python -m pip install fastmcp mcp gradio openai pydantic
```

A local virtual environment named `mcp_security_env/` exists on the original
machine but is git-ignored; create your own.

## Project structure

```text
MCP_Security_Lab/
├── README.md
├── mcp_permission_server.py        # FastMCP permission-aware server (STDIO)
├── mcp_permission_client_base.py   # Permissions, audit, approval, MCP client
├── mcp_permission_client_app.py    # Gradio permission client (port 7863)
├── mcp_permission_host_app.py      # Gradio AI host with OpenAI (port 7864)
├── .gitignore
└── data/
    ├── permissions.json            # Active policy file
    └── audit.log                   # Audit trail
```

The modules use **flat imports** (`from mcp_permission_client_base import ...`),
so run them from inside `MCP_Security_Lab`.

## Prerequisites

- Python 3.10+.
- An OpenAI API key for the AI host.
- No external MCP server; the server is launched locally over STDIO.

## Installation

```bash
cd MCP_Security_Lab

python -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows

python -m pip install fastmcp mcp gradio openai pydantic
```

## Run

### Permission-management client

```bash
python mcp_permission_client_app.py mcp_permission_server.py
```

Opens `http://127.0.0.1:7863` with four tabs:

- **Tools** — list tools with permission status, call a tool, or approve and
  execute.
- **Resources** — list and read `file://audit/log` and
  `file://config/permissions`.
- **Prompts** — list and render `security_review`.
- **Permissions** — load tool names, set `allow`/`deny`/`ask`, save, and view the
  audit log.

### AI host

```bash
export OPENAI_API_KEY=sk-...
python mcp_permission_host_app.py mcp_permission_server.py
```

Opens `http://127.0.0.1:7864`. The host uses the hard-coded model `gpt-6-luna`
and appends permission and risk information to each tool description. It also
adds synthetic tools for resources and prompts.

### Server directly (optional)

```bash
python mcp_permission_server.py
```

Runs the server over STDIO; it is normally started by a client rather than used
directly.

## Expected behavior

- `read_file` under the default policy executes and logs `ALLOWED`.
- `write_file` under `ask` returns an approval-request message and logs `ASK`;
  approving executes it and logs `ALLOWED`, and the server appends `WRITE`.
- `delete_file` under `deny` returns a denial message and logs `DENIED`.
- `execute_command` never runs a real command; it returns a simulation notice
  and logs `EXECUTE (simulated)`.
- `file://audit/log` returns the accumulated log.
- `security_review` renders a structured review prompt.

The retained `data/audit.log` contains real entries from the original lab
session, including earlier `delete_file` denials and a later allowed delete.

## Important implementation details and limitations

- **Path containment is not enforced on the server.** `read_file`, `write_file`,
  and `delete_file` join `BASE_DIR / filepath` without resolving or checking the
  result. A path such as `../mcp_permission_server.py` reads outside `data/`; this
  was verified. Permissions gate the *tool call*, not the *path*. Do not treat
  this server as a sandbox.
- **`execute_command` is a simulation**, by design.
- **Elicitation is conceptual.** `request_elicitation()` only prints a schema and
  returns `{}`; it is not called anywhere in the retained code.
- **AI-host approval handling is fragile.** `execute_tool()` checks for a `dict`
  result, while `call_tool_with_permission()` returns a list (either content
  items or synthetic message objects). As a result, allowed results are
  stringified list objects and the pending-approval state may not be recorded.
  The Gradio client's **Approve & Execute** button is the reliable approval
  path.
- **Permissions are client-side.** A different client can call the server tools
  without consulting `permissions.json`.
- No authentication, encryption, rate limiting, or multi-user isolation.
- No automated tests.
- No dependency lockfile.
- A local `.env` exists but is **not** covered by this directory's `.gitignore`
  (which only ignores `mcp_security_env/`). Never commit real keys; add `.env` to
  your ignore rules before publishing this as a standalone repository.

## Security disclaimer

This is an **educational security lab**, not a hardened MCP deployment. The
permission layer is intentionally simple and bypassable, path containment is
absent, and command execution is only simulated. Do not expose these servers or
apps to untrusted users or networks.
