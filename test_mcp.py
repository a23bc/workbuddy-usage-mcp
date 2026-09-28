#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone test harness for session_usage_server.py (MCP stdio server).

Spawns the server from the same directory, drives it through the MCP
handshake (initialize -> tools/list -> tools/call) and asserts the
responses are well-formed. Run with:  python test_mcp.py
"""
import subprocess
import json
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "session_usage_server.py")
PY = sys.executable


def rpc(proc, method, params=None, mid=1):
    req = {"jsonrpc": "2.0", "id": mid, "method": method}
    if params is not None:
        req["params"] = params
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())


def main():
    proc = subprocess.Popen(
        [PY, SERVER],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        # 1) initialize
        r = rpc(proc, "initialize", {"protocolVersion": "2024-11-05"}, 1)
        assert "result" in r and "tools" in r["result"]["capabilities"], r
        print("[OK] initialize ->", r["result"]["serverInfo"])

        # 2) tools/list
        r = rpc(proc, "tools/list", None, 2)
        names = [t["name"] for t in r["result"]["tools"]]
        assert {"get_current_session_usage", "list_session_usage"} <= set(names), names
        print(f"[OK] tools/list -> {names}")

        # 3) get_current_session_usage (most recent session)
        r = rpc(proc, "tools/call",
                {"name": "get_current_session_usage", "arguments": {}}, 3)
        d = json.loads(r["result"]["content"][0]["text"])
        assert "used" in d and "size" in d, d
        print(f"[OK] current usage -> used={d['used']} size={d['size']} "
              f"pct={d['percent']}% title={d['title']!r}")

        # 4) list_session_usage
        r = rpc(proc, "tools/call",
                {"name": "list_session_usage", "arguments": {"limit": 3}}, 4)
        lst = json.loads(r["result"]["content"][0]["text"])
        assert isinstance(lst, list) and len(lst) > 0, lst
        print(f"[OK] list usage -> {len(lst)} rows; top: {lst[0]['title'][:30]!r}")

        print("\nALL CHECKS PASSED")
    except AssertionError as e:
        print("CHECK FAILED:", e)
        sys.exit(1)
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
