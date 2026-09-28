# workbuddy-usage-mcp

把你的 **WorkBuddy 会话用量** 作为一个 [MCP](https://modelcontextprotocol.io) server 暴露出来，让 agent 能像调用其他工具一样调用它。

WorkBuddy 会把每个会话的用量实时写入本地的 `~/.workbuddy/workbuddy.db`（`session_usage` 表：`used` / `size` / `updated_at` / `credit_json`）。本 server **只读** 这个数据库，并暴露两个 MCP 工具。

## 工具

| 工具 | 参数 | 返回 |
| --- | --- | --- |
| `get_current_session_usage` | `workspace`（可选）— 工作区路径或目录名；不传则取最近活跃的会话 | `used`、`size`、`percent`、`credit_total`、`credit_models`、`top_credits`、`updated_at`、`title`、`session_id` |
| `list_session_usage` | `limit`（可选，默认 30） | 所有会话的 `{title, used, size, updated_at}` 数组，最新在前 |

## 环境要求

- Python 3.8+（仅用标准库，**无需 `pip install`**）
- 对运行 WorkBuddy 的机器上的 `~/.workbuddy/workbuddy.db` 有读取权限

## 安装

```bash
git clone https://github.com/a23bc/workbuddy-usage-mcp.git
cd workbuddy-usage-mcp
python test_mcp.py   # 可选：自测 MCP 握手流程
```

## 注册到 WorkBuddy

把 server 加进 `~/.workbuddy/mcp.json`（文件不存在就新建），合并进 `mcpServers`：

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

参考 `mcp.json.example`。然后：

1. 打开 WorkBuddy 的 **连接器管理** 界面。
2. 找到 `session-usage`，点击 **Trust** 启用。
3. **重启 WorkBuddy** —— 新增的 MCP server 只有在重启后才会在连接器界面显示。

之后，在任何新会话里 agent 都能调用 `get_current_session_usage` / `list_session_usage`。

## 工作原理

- 传输协议：基于 stdio 的 newline-delimited JSON-RPC 2.0（MCP 标准）。
- 数据库以 `mode=ro` 打开，因此即使 WorkBuddy 正在写入（WAL 模式），也不会干扰客户端。
- 按 `workspace` 查找时，用工作区目录名匹配 `sessions.cwd`；不传参数则回退到最近活跃的会话。

## 局限性

- `used` / `size` 是 WorkBuddy **内部的用量单位**（`size` 根据会话类型表现为 `192000` 或 `1000000`）。它们**不是** LLM 提供方 `usage` 字段里的标准 `prompt_tokens` / `completion_tokens` 拆分——该表里没有这一粒度。
- `workbuddy.db` 的 schema 是 WorkBuddy 内部实现，若发生变化，本 server 需相应更新。
- MCP server 在会话启动时加载；新增 / 信任一个 server 只影响重启后的**新** WorkBuddy 会话。

## 许可证

MIT —— 见 [LICENSE](./LICENSE)。
