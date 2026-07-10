# AI Daily — MCP Server 配置文档

AI Daily MCP Server 将日报数据封装为标准 MCP 工具，支持 Hermes、Claude Desktop、Cursor 等 MCP 兼容客户端直接查询。

---

## 启动方式

```bash
python3 run_mcp_server.py
```

MCP Server 使用 **stdio 协议**，需通过 MCP 客户端配置启动。

---

## Hermes 配置

在 Hermes 的 `config.yaml` 中添加：

```yaml
mcpServers:
  ai-daily:
    command: python3
    args:
      - /path/to/ai-daily/run_mcp_server.py
```

重启 Hermes 后即可在对话中调用 AI Daily 工具。

---

## Claude Desktop 配置

编辑 `~/Library/Application Support/Claude/claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "ai-daily": {
      "command": "python3",
      "args": [
        "/path/to/ai-daily/run_mcp_server.py"
      ]
    }
  }
}
```

重启 Claude Desktop 后生效。

---

## Cursor 配置

在 Cursor 设置中搜索 `MCP Servers`，添加：

- **Name**: `ai-daily`
- **Type**: `stdio`
- **Command**: `python3 /path/to/ai-daily/run_mcp_server.py`

---

## Tool 列表

| Tool | 说明 | 参数 |
|---|---|---|
| `get_today_report` | 获取今日完整日报 | 无 |
| `get_history_report` | 获取指定日期日报 | `date`（必需） |
| `search_news` | 跨源搜索新闻 | `keyword`, `date`, `max_results` |
| `get_today_events` | 获取今日事件聚类 | `max_events` |
| `get_github_trending` | GitHub Trending 项目 | `date`, `max_items` |
| `get_hacker_news` | Hacker News 讨论 | `date`, `max_items` |
| `get_youtube_videos` | YouTube 视频 | `date`, `max_items` |
| `get_twitter_posts` | X 推文 | `date`, `max_items` |
| `get_china_ai` | 国产 AI 新闻 | `date`, `max_items` |
| `get_system_status` | 系统状态统计 | 无 |

---

## 调用示例

```json
// 获取今日 GitHub Trending
{
  "name": "get_github_trending",
  "arguments": {
    "max_items": 5
  }
}

// 搜索 GPT 相关新闻
{
  "name": "search_news",
  "arguments": {
    "keyword": "GPT",
    "max_results": 10
  }
}

// 查看系统状态
{
  "name": "get_system_status",
  "arguments": {}
}
```

---

## 安全说明

- 所有 Tool **只读取本地缓存数据**，禁止联网
- 不执行任何写操作
- 不接收网络连接（stdio 模式）
- 无外部依赖风险
