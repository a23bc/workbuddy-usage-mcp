# workbuddy-usage-mcp

> 中文文档：[README.zh-CN.md](./README.zh-CN.md)

Expose your **WorkBuddy session usage** as an [MCP](https://modelcontextprotocol.io) server, so an agent can call it like any other tool.

WorkBuddy writes per-session usage locally into `~/.workbuddy/workbuddy.db`
(`session_usage` table: `used` / `size` / `updated_at` / `credit_json`). This
server reads that database **read-only** and exposes two MCP tools.

## Tools

| Tool | Args | Returns |
| --- | --- | --- |
| `get_current_session_usage` | `workspace` *(optional)* — path or dir name of a workspace; omit to use the most recently active session | `used`, `size`, `percent`, `credit_total`, `credit_models`, `top_credits`, `updated_at`, `title`, `session_id` |
| `list_session_usage` | `limit` *(optional, default 30)* | array of `{title, used, size, updated_at}` for all sessions, newest first |

## Requirements

- Python 3.8+ (standard library only — **no `pip install` needed**)
- Read access to `~/.workbuddy/workbuddy.db` on the machine running WorkBuddy

## Install

```bash
git clone https://github.com/a23bc/workbuddy-usage-mcp.git
cd workbuddy-usage-mcp
python test_mcp.py   # optional self-test of the MCP handshake
```

## Register with WorkBuddy

Add the server to `~/.workbuddy/mcp.json` (create the file if it does not
exist), merging into `mcpServers`:

```json
{
  "mcpServers": {
    "session-usage": {
      "command": "python",
      "args": ["/absolute/path/to/session_usage_server.py"]
    }
  }
}
```

See `mcp.json.example`. Then:

1. Open WorkBuddy's **connector management** UI.
2. Find `session-usage` and click **Trust** to enable it.
3. **Restart WorkBuddy** — a newly added MCP server only shows up after a restart.

After that, the agent can call `get_current_session_usage` /
`list_session_usage` in any new session.

## How it works

- Transport: newline-delimited JSON-RPC 2.0 over stdio (the MCP standard).
- The DB is opened with `mode=ro`, so it never disturbs the live client even
  while WorkBuddy is writing (WAL mode).
- Session lookup by `workspace` matches the workspace directory name against
  `sessions.cwd`; with no argument it falls back to the most recently active
  session.

## Limitations

- `used` / `size` are WorkBuddy's **internal usage units** (size appears as
  `192000` or `1000000` depending on the session type). They are **not** the
  standard `prompt_tokens` / `completion_tokens` split exposed by an LLM
  provider's `usage` field — that granularity is not present in this table.
- The schema of `workbuddy.db` is internal to WorkBuddy; if it changes, this
  server must be updated accordingly.
- An MCP server is loaded at session start; adding/trusting one only affects
  **new** WorkBuddy sessions after a restart.

## License

MIT — see [LICENSE](./LICENSE).
