#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP stdio server: WorkBuddy session usage as agent-callable tools.

Transport: newline-delimited JSON-RPC 2.0 over stdio (the MCP standard).
No third-party deps - pure stdlib. Reads ~/.workbuddy/workbuddy.db read-only.

Tools exposed to the agent:
  get_current_session_usage  -> usage of the current / most-recent session
  list_session_usage         -> usage of all sessions, newest first

Register in ~/.workbuddy/mcp.json:
  {
    "mcpServers": {
      "session-usage": {
        "command": "<managed python>",
        "args": ["<this file>"]
      }
    }
  }
Then Trust it in WorkBuddy's connector management UI.
"""
import sqlite3
import json
import os
import sys
import datetime

DB_PATH = os.path.expanduser("~/.workbuddy/workbuddy.db")


def log(msg):
    # stderr ONLY - stdout is the MCP channel and must stay clean
    print(f"[session-usage-mcp] {msg}", file=sys.stderr, flush=True)


def _connect():
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def _ts(ms):
    if not ms:
        return "n/a"
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def find_session(workspace=None):
    con = _connect()
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    if workspace:
        name = os.path.basename(workspace.rstrip("/\\"))
        rows = cur.execute(
            "SELECT id,title,cwd,last_activity_at FROM sessions "
            "WHERE cwd LIKE ? ORDER BY last_activity_at DESC",
            (f"%{name}%",),
        ).fetchall()
        if rows:
            con.close()
            return dict(rows[0])
    row = cur.execute(
        "SELECT id,title,cwd,last_activity_at FROM sessions "
        "ORDER BY last_activity_at DESC LIMIT 1"
    ).fetchone()
    con.close()
    return dict(row) if row else None


def get_usage(session_id):
    con = _connect()
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    row = cur.execute(
        "SELECT * FROM session_usage WHERE session_id=?", (session_id,)
    ).fetchone()
    con.close()
    return dict(row) if row else None


def current_usage(workspace=None):
    s = find_session(workspace)
    if not s:
        raise RuntimeError("no session found in workbuddy.db")
    u = get_usage(s["id"])
    if not u:
        raise RuntimeError(f"session '{s['title']}' has no usage record yet")
    used, size = u["used"], u["size"]
    pct = (used / size * 100) if size else 0.0
    credits = json.loads(u["credit_json"]) if u.get("credit_json") else {}
    return {
        "session_id": s["id"],
        "title": s["title"],
        "cwd": s["cwd"],
        "updated_at": _ts(u["updated_at"]),
        "used": used,
        "size": size,
        "percent": round(pct, 2),
        "credit_total": round(sum(credits.values()), 2),
        "credit_models": len(credits),
        "top_credits": [
            {"model": k, "credit": round(v, 2)}
            for k, v in sorted(credits.items(), key=lambda kv: -kv[1])[:5]
        ],
    }


def list_usage(limit=30):
    con = _connect()
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    rows = cur.execute(
        "SELECT s.id,s.title,u.used,u.size,u.updated_at FROM sessions s "
        "LEFT JOIN session_usage u ON s.id=u.session_id ORDER BY u.updated_at DESC"
    ).fetchall()
    con.close()
    out = []
    for r in rows[:limit]:
        out.append(
            {
                "title": r["title"],
                "used": r["used"] or 0,
                "size": r["size"] or 0,
                "updated_at": _ts(r["updated_at"]),
            }
        )
    return out


TOOLS = [
    {
        "name": "get_current_session_usage",
        "description": (
            "Return the usage (used/size/percent/credits) of the current or "
            "most-recently-active WorkBuddy session by reading the local "
            "workbuddy.db. Pass 'workspace' to target a specific session by "
            "its path or directory name; omit it to use the most recent one."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {
                    "type": "string",
                    "description": "Optional workspace path or directory name "
                    "to locate the session. Omit for most-recent session.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "list_session_usage",
        "description": "List usage (used/size/updated_at) for all WorkBuddy "
        "sessions, newest first.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max rows to return (default 30).",
                }
            },
            "required": [],
        },
    },
]


def handle_call(name, args):
    args = args or {}
    if name == "get_current_session_usage":
        data = current_usage(args.get("workspace"))
        return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}]}
    if name == "list_session_usage":
        data = list_usage(int(args.get("limit", 30)))
        return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}]}
    raise RuntimeError(f"unknown tool: {name}")


def send(mid, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}) + "\n")
    sys.stdout.flush()


def main():
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except Exception as e:
            log(f"bad json: {e} :: {raw[:200]}")
            continue
        if "id" not in msg:
            # notification (e.g. notifications/initialized) -> no reply
            continue
        method = msg.get("method")
        mid = msg["id"]
        if method == "initialize":
            pv = msg.get("params", {}).get("protocolVersion", "2024-11-05")
            send(
                mid,
                {
                    "protocolVersion": pv,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "session-usage", "version": "1.0.0"},
                },
            )
        elif method == "tools/list":
            send(mid, {"tools": TOOLS})
        elif method == "tools/call":
            params = msg.get("params", {})
            try:
                send(mid, handle_call(params.get("name"), params.get("arguments")))
            except Exception as e:
                send(mid, {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True})
        elif method == "ping":
            send(mid, {})
        else:
            send(mid, {"content": [{"type": "text", "text": f"unsupported method {method}"}], "isError": True})


if __name__ == "__main__":
    main()
